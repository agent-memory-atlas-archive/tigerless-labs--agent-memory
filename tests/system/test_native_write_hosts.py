"""End to end and offline: a fake host CLI starts the configured MCP adapter and drives it."""

import json
import pathlib
import sys

import pytest
from agent_memory.core import distill, sessions, toolkit
from agent_memory.core.errors import ValidationError
from agent_memory.core.watermark import Watermark
from agent_memory.executor import hosts
from agent_memory.executor.reasoners import ToolHostReasoner

FAKE_HOST = """#!{python}
import json, os, subprocess, sys, tomllib

argv = sys.argv[1:]
prompt = sys.stdin.read()

def after(flag):
    return argv[argv.index(flag) + 1]

if "--mcp-config" in argv:
    server = next(iter(json.loads(after("--mcp-config"))["mcpServers"].values()))
    system = after("--system-prompt")
else:
    overrides = tomllib.loads(
        "\\n".join(argv[i + 1] for i, part in enumerate(argv) if part == "-c")
    )
    server = next(iter(overrides["mcp_servers"].values()))
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
replies = []
for index, (name, arguments) in enumerate(json.loads(os.environ["FAKE_HOST_SCRIPT"])):
    replies.append(rpc(index + 2, "tools/call", {{"name": name, "arguments": arguments}}))
child.stdin.close()
child.wait()

with open(os.environ["FAKE_HOST_LOG"], "w", encoding="utf-8") as log:
    json.dump({{"argv": argv, "stdin": prompt, "system": system, "listed": listed,
               "replies": replies, "executor": os.environ.get("AGENT_MEMORY_EXECUTOR")}}, log)
if "--output-last-message" in argv:
    open(after("--output-last-message"), "w", encoding="utf-8").write("done")
print("done")
"""


def _fake_host(tmp_path, name):
    binary = tmp_path / "bin" / name
    binary.parent.mkdir(exist_ok=True)
    binary.write_text(FAKE_HOST.format(python=sys.executable), encoding="utf-8")
    binary.chmod(0o755)
    return binary


def _reasoner(name, binary):
    spec = hosts.HostSpec(name=name, binary=str(binary), model="a-model", attempts=1)
    return ToolHostReasoner(host=hosts.Host(spec))


def _batch(store):
    old = store.record(
        type="fact",
        fields={"project": "pipeline", "subject": "queue timeout"},
        abstract="Queue timeout is 20 seconds",
        body="Set in infra/queue.yaml.",
    )
    lines = ["user: Our queue timeout is 30 seconds now, raised from 20.", "assistant: Noted."]
    pointer = store.archive.append_session("boundary", lines)
    return old, sessions.resolve(store.layout, pointer)


def _supersede(handle):
    return {
        "type": "fact",
        "op": "supersede",
        "handle": handle,
        "fields": {"project": "pipeline", "subject": "queue timeout 30s"},
        "abstract": "Queue timeout is 30 seconds",
        "provenance": ["0"],
    }


@pytest.mark.parametrize("name", [hosts.HOST_CLAUDE_CODE, hosts.HOST_CODEX])
def test_a_host_distills_a_batch_through_the_toolkit_adapter(name, store, tmp_path, monkeypatch):
    old, messages = _batch(store)
    log = tmp_path / "host-log.json"
    script = [
        [toolkit.TOOL_RECALL, {toolkit.ARG_QUERY: "queue timeout"}],
        [toolkit.TOOL_READ, {toolkit.ARG_NAME: old.name}],
        [toolkit.TOOL_SUBMIT, {toolkit.ARG_OPERATIONS: [_supersede(old.name)]}],
    ]
    monkeypatch.setenv("FAKE_HOST_SCRIPT", json.dumps(script))
    monkeypatch.setenv("FAKE_HOST_LOG", str(log))

    report = distill.distill(
        store, "boundary", messages, _reasoner(name, _fake_host(tmp_path, name))
    )

    assert report.batches[0].written == ("queue-timeout-30s",)
    assert report.batches[0].rounds == len(script)
    assert not store.find(old.name).is_active()
    seen = json.loads(log.read_text(encoding="utf-8"))
    assert set(seen["listed"]) == {toolkit.TOOL_RECALL, toolkit.TOOL_READ, toolkit.TOOL_SUBMIT}
    assert all(reply["result"]["isError"] is False for reply in seen["replies"])
    assert "our queue timeout is 30 seconds" in seen["stdin"].lower()
    assert "our queue timeout is 30 seconds" not in seen["system"].lower()
    assert toolkit.TOOL_SUBMIT in seen["system"]
    assert seen["executor"] == "1"


def test_a_host_run_without_a_submission_writes_nothing(store, tmp_path, monkeypatch):
    old, messages = _batch(store)
    monkeypatch.setenv(
        "FAKE_HOST_SCRIPT", json.dumps([[toolkit.TOOL_RECALL, {toolkit.ARG_QUERY: "queue"}]])
    )
    monkeypatch.setenv("FAKE_HOST_LOG", str(tmp_path / "host-log.json"))
    reasoner = _reasoner(hosts.HOST_CODEX, _fake_host(tmp_path, hosts.HOST_CODEX))
    before = sorted(pathlib.Path(store.root).rglob("*.md"))
    with pytest.raises(ValidationError):
        distill.distill(store, "boundary", messages, reasoner)
    assert sorted(pathlib.Path(store.root).rglob("*.md")) == before
    assert store.find(old.name).is_active()
    assert Watermark(store.layout, store.clock).read("boundary").distilled == 0
