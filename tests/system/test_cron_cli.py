"""CLI-level crontab install/status/remove without touching the user's real crontab."""

from __future__ import annotations

import json
import os

from agent_memory.cli.main import EXIT_OK, main

FAKE_CRONTAB = """#!/bin/sh
set -eu
if [ "$1" = "-l" ]; then
  if [ -f "$FAKE_CRONTAB_FILE" ]; then
    cat "$FAKE_CRONTAB_FILE"
    exit 0
  fi
  echo "no crontab for test" >&2
  exit 1
fi
if [ "$1" = "-" ]; then
  cat > "$FAKE_CRONTAB_FILE"
  exit 0
fi
exit 2
"""


def test_cli_manages_one_store_block_and_preserves_unrelated_jobs(tmp_path, monkeypatch, capsys):
    store = tmp_path / "Store With Spaces"
    crontab_file = tmp_path / "user.crontab"
    crontab_file.write_text("11 2 * * * /usr/bin/unrelated\n", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    crontab = bin_dir / "crontab"
    crontab.write_text(FAKE_CRONTAB, encoding="utf-8")
    crontab.chmod(0o755)
    mem = bin_dir / "mem"
    mem.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    mem.chmod(0o755)
    environment = tmp_path / "reasoner.env"
    environment.write_text("HTTPS_PROXY=https://example.test\n", encoding="utf-8")
    environment.chmod(0o600)
    monkeypatch.setenv("FAKE_CRONTAB_FILE", str(crontab_file))
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ.get('PATH', '')}")
    monkeypatch.setattr(
        "agent_memory.adapters.cron_schedule._scheduler_running", lambda: True
    )
    monkeypatch.setattr("agent_memory.adapters.cron_schedule._is_wsl", lambda: False)

    def run(*args):
        assert main(["--store", str(store), "--json", "cron", *args]) == EXIT_OK
        return json.loads(capsys.readouterr().out)

    assert main(["--store", str(store), "--json", "init"]) == EXIT_OK
    capsys.readouterr()
    installed = run(
        "install",
        "--interval-minutes",
        "15",
        "--mem-path",
        str(mem),
        "--env-file",
        str(environment),
    )
    unchanged = run(
        "install",
        "--interval-minutes",
        "15",
        "--mem-path",
        str(mem),
        "--env-file",
        str(environment),
    )
    current = run("status")
    removed = run("remove")

    assert installed["status"] == "installed"
    assert unchanged["status"] == "unchanged"
    assert current["installed"] is True
    assert current["entry"].startswith("*/15 * * * * ")
    assert "--json sleep --if-due --trigger-source cron" in current["entry"]
    assert str(environment) in current["entry"]
    assert removed["status"] == "removed"
    assert crontab_file.read_text("utf-8") == "11 2 * * * /usr/bin/unrelated\n"
