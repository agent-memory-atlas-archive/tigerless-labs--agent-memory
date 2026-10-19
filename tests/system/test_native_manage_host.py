"""A fake Codex process drives the real run-scoped Manage MCP adapter end to end."""

import json
import os
import pathlib
import sys

from agent_memory.cli.main import main
from agent_memory.core.config import OperationExecutorConfig
from agent_memory.core.manage import Manage
from agent_memory.core.manage_toolkit import TOOL_LIST, TOOL_READ, TOOL_SUBMIT
from agent_memory.core.store import Store

FAKE_CODEX = """#!{python}
import json, os, subprocess, sys, tomllib

argv = sys.argv[1:]
def after(flag):
    return argv[argv.index(flag) + 1]

overrides = tomllib.loads("\\n".join(argv[i + 1] for i, part in enumerate(argv) if part == "-c"))
server = next(iter(overrides["mcp_servers"].values()))
prompt = sys.stdin.read()
system = open(overrides["model_instructions_file"], encoding="utf-8").read()
child = subprocess.Popen(
    [server["command"], *server["args"]],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
)

def rpc(request_id, method, params=None):
    message = {{"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {{}}}}
    child.stdin.write(json.dumps(message) + "\\n")
    child.stdin.flush()
    return json.loads(child.stdout.readline())

rpc(0, "initialize")
listed = [tool["name"] for tool in rpc(1, "tools/list")["result"]["tools"]]
calls = []
menu_reply = rpc(2, "tools/call", {{"name": "list_proposals", "arguments": {{}}}})
calls.append(menu_reply)
menu = json.loads(menu_reply["result"]["content"][0]["text"])
request_id = 3
for proposal in menu:
    for source in proposal["sources"]:
        reply = rpc(request_id, "tools/call", {{
            "name": "read_evidence",
            "arguments": {{"proposal": proposal["id"], "name": source["name"]}},
        }})
        calls.append(reply)
        request_id += 1
verdicts = [{{"proposal": proposal["id"], "verdict": "reject"}} for proposal in menu]
calls.append(rpc(request_id, "tools/call", {{
    "name": "submit_verdicts", "arguments": {{"verdicts": verdicts}},
}}))
child.stdin.close()
child.wait()

with open(os.environ["FAKE_MANAGE_LOG"], "w", encoding="utf-8") as handle:
    json.dump({{"argv": argv, "prompt": prompt, "system": system, "listed": listed,
               "calls": calls, "executor": os.environ.get("AGENT_MEMORY_EXECUTOR")}}, handle)
open(after("--output-last-message"), "w", encoding="utf-8").write("review submitted")
print(json.dumps({{"type": "turn.completed", "usage": {{
    "input_tokens": 900, "cached_input_tokens": 600, "output_tokens": 90,
}}}}))
"""


def _fake_codex(tmp_path):
    binary = tmp_path / "bin" / "codex"
    binary.parent.mkdir()
    binary.write_text(FAKE_CODEX.format(python=sys.executable), encoding="utf-8")
    binary.chmod(0o755)
    return binary


def _seed(store):
    store.record(
        type="experience",
        name="drain-window-first",
        abstract="Queue drain timeout expires before the worker lease completes",
        body="The drain is 20 seconds and the worker lease is 30 seconds.",
    )
    store.record(
        type="experience",
        name="drain-window-second",
        abstract="Queue drain timeout expires before the worker lease completes on staging",
        body="The staging drain is 20 seconds and the worker lease is 30 seconds.",
    )


def test_mem_sleep_runs_native_codex_mcp_review_then_manage_validation(
    store, tmp_path, monkeypatch, capsys
):
    _seed(store)
    store.config.executor.manage = OperationExecutorConfig(
        reasoner="host",
        host="codex",
        host_model="test-model",
        tool_mode="native",
        timeout_seconds=30.0,
    )
    store.config.save(store.root)
    log = tmp_path / "manage-host.json"
    binary = _fake_codex(tmp_path)
    monkeypatch.setenv("PATH", str(binary.parent) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("FAKE_MANAGE_LOG", str(log))

    assert main(["--json", "--store", str(store.root), "sleep"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["review"]["mode"] == "native"
    assert payload["review"]["complete"] is True
    assert payload["review"]["tool_calls"] >= 3
    assert payload["review"]["agent_turns"] == 1
    assert payload["review"]["input_tokens"] == 900
    assert payload["review"]["cached_input_tokens"] == 600
    assert payload["review"]["output_tokens"] == 90
    assert payload["decisions"]
    assert all(decision["verdict"] == "rejected" for decision in payload["decisions"])

    trace = json.loads(log.read_text(encoding="utf-8"))
    assert set(trace["listed"]) == {TOOL_LIST, TOOL_READ, TOOL_SUBMIT}
    assert all(call["result"]["isError"] is False for call in trace["calls"])
    assert "submit_verdicts" in trace["system"]
    assert "The staging drain is 20 seconds" not in trace["prompt"]
    assert trace["executor"] == "1"
    assert "--ignore-user-config" in trace["argv"]
    assert trace["argv"][trace["argv"].index("--sandbox") + 1] == "read-only"
    assert any("memory_review" in part for part in trace["argv"])

    reopened = Store(store.root, agent="assert")
    assert all(
        reopened.find(name).is_active() for name in ("drain-window-first", "drain-window-second")
    )
    assert not Manage(reopened).proposals()
    report = pathlib.Path(payload["path"]).read_text(encoding="utf-8")
    assert "list_proposals" in report
    assert "read_evidence" in report
    assert "submit_verdicts" in report
