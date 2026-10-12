"""Detached automatic Dream launcher and one-shot worker."""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys

from agent_memory.core import dreaming
from agent_memory.core.config import EXECUTOR_ENV_VAR, STORE_ENV_VAR
from agent_memory.core.errors import LockTimeoutError
from agent_memory.core.locking import file_lock
from agent_memory.core.manage import Manage
from agent_memory.core.reasoning import Reasoner
from agent_memory.core.store import Store

LOG_FILENAME = "hooks.log"
EXECUTABLE = "mem"
COMMAND = "dream-worker"
CLAIM_FLAG = "--claim"
REASON_HOST_FLAG = "--reason-host"


def launch(store: Store, host: str) -> dreaming.ClaimResult:
    result = dreaming.claim_due(store, host)
    if result.claim is None:
        return result
    claim = result.claim
    binary = pathlib.Path(sys.executable).parent / EXECUTABLE
    command = str(binary) if binary.exists() else EXECUTABLE
    environment = {**os.environ, STORE_ENV_VAR: str(store.root), EXECUTOR_ENV_VAR: "1"}
    try:
        store.layout.state_dir.mkdir(parents=True, exist_ok=True)
        with (store.layout.state_dir / LOG_FILENAME).open("a", encoding="utf-8") as log:
            subprocess.Popen(
                [command, COMMAND, CLAIM_FLAG, claim.id, REASON_HOST_FLAG, claim.host],
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
    except OSError as error:
        dreaming.mark_failed(store, claim.id, f"worker launch failed: {error}")
        return dreaming.ClaimResult(None, "worker launch failed", result.sessions_since)
    return result


def run_worker(store: Store, claim_id: str, reasoner: Reasoner | None) -> dict[str, object]:
    """Run exactly one claimed Dream and exit. The report is the completion fence."""
    try:
        with file_lock(
            store.layout.dream_run_lock,
            timeout=store.config.storage.lock_timeout_seconds,
        ):
            claim = dreaming.current_claim(store, claim_id)
            if claim is None:
                status = dreaming.state(store)
                return {
                    "dreamed": status.get("status") == dreaming.STATUS_SUCCEEDED,
                    "claim": claim_id,
                    "reason": "claim already completed or superseded",
                }
            with file_lock(store.layout.maintenance_lock, timeout=None):
                claim = dreaming.current_claim(store, claim_id)
                if claim is None:
                    return {"dreamed": False, "claim": claim_id, "reason": "claim superseded"}
                report = Manage(store).sleep(reasoner=reasoner, dream_id=claim.id)
            dreaming.mark_succeeded(store, claim, report.path)
            return {"dreamed": True, "claim": claim.id, **report.as_dict()}
    except LockTimeoutError:
        return {
            "dreamed": False,
            "claim": claim_id,
            "reason": "another dream worker still owns the run lock",
        }
    except Exception as error:
        dreaming.mark_failed(store, claim_id, f"{type(error).__name__}: {error}")
        raise
