#!/usr/bin/env python3
"""Run bounded, retried stages with an OS lock and a durable status record."""
from __future__ import annotations

import fcntl
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT = Path(os.environ.get("COTPY_PROJECT_DIR", "/Users/fox/Private/Projects/cotpy"))
STATUS = PROJECT / "logs/weekly-status.json"


def record(stage: str, state: str, **details) -> None:
    payload = dict(stage=stage, state=state, updated_at=datetime.now().astimezone().isoformat(), **details)
    temp = STATUS.with_suffix(".tmp")
    temp.write_text(json.dumps(payload, indent=2) + "\n")
    temp.replace(STATUS)
    print(f"{payload['updated_at']} {stage}: {state} {details}", flush=True)


def run_command(command: list[str], timeout: int) -> None:
    process = subprocess.Popen(command, cwd=PROJECT, start_new_session=True)
    try:
        code = process.wait(timeout=timeout)
    except BaseException:
        # Include children, so a timed-out attempt cannot keep publishing.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
        raise
    if code:
        raise RuntimeError(f"command exited {code}: {' '.join(command)}")


def check_downloads(started: float) -> None:
    # The CLI logs download errors without returning failure.
    for kind in ("legacy", "disaggregated"):
        path = PROJECT / f"data/{kind}_{datetime.now().year}.txt"
        if not path.is_file() or not path.stat().st_size or path.stat().st_mtime < started:
            raise RuntimeError(f"Current-year download was not refreshed: {path}")


def run_stage(name: str, commands: list[list[str]], timeout: int) -> None:
    for attempt in range(1, 4):
        started = time.time()
        record(name, "running", attempt=attempt)
        try:
            for command in commands:
                run_command(command, timeout)
            if name == "download":
                check_downloads(started)
            record(name, "completed", attempt=attempt)
            return
        except (RuntimeError, subprocess.TimeoutExpired, OSError) as exc:
            record(name, "failed", attempt=attempt, error=str(exc))
            if attempt == 3:
                raise
            delay = 60 if attempt == 1 else 300
            print(f"Retrying {name} in {delay}s", flush=True)
            time.sleep(delay)


def main() -> int:
    (PROJECT / "logs").mkdir(exist_ok=True)
    # flock is released even after a crash; do not unlink its inode.
    with (PROJECT / "logs/weekly.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("cotpy weekly job already running", flush=True)
            return 0
        if (PROJECT / ".cotpy-weekly.lock").exists():
            raise RuntimeError("Legacy weekly lock exists; check for an older running job")
        python = sys.executable
        record("weekly", "running")
        run_stage("download", [[python, "main.py", "--update", "--force"]], 2400)
        run_stage("reports", [
            [python, "main.py", "--analyze", "--signals", "--export", "--market-charts"],
            [python, "report.py"], [python, "summary_report.py"],
        ], 3600)
        if os.environ.get("COTPY_PUBLISH_REPORTS", "1") == "1":
            run_stage("publish", [[python, "scripts/publish_to_csfox_gh.py"]], 3600)
        record("weekly", "completed", published=os.environ.get("COTPY_PUBLISH_REPORTS", "1") == "1")
        return 0


if __name__ == "__main__":
    def terminate(signum, frame):
        raise KeyboardInterrupt(f"received signal {signum}")

    signal.signal(signal.SIGTERM, terminate)
    try:
        raise SystemExit(main())
    except (Exception, KeyboardInterrupt) as exc:
        print(f"cotpy weekly refresh FAILED: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(1)
