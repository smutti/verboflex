#!/usr/bin/env python3
"""Run the complete backend suite against owned, disposable PostgreSQL/Redis."""

from __future__ import annotations

import argparse
import shutil
import signal
from pathlib import Path

from phase4_gate import BACKEND, Gate


def interrupted(signum, _frame):
    raise SystemExit(128 + signum)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, required=True)
    args = parser.parse_args()
    # Reuse the tested lifecycle, not the historical phase's test selection/gates.
    runner = Gate()
    # In particular, Alembic prefers VERBOFLEX_DATABASE_URL over fixture URLs.
    # Never inherit application/provider authority from a developer's shell.
    runner.environment = {
        key: value for key, value in runner.environment.items() if not key.startswith("VERBOFLEX_")
    }
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    try:
        runner.start_infrastructure()
        runner.command(
            "pytest",
            [
                str(BACKEND / ".venv/bin/pytest"),
                "--junitxml=" + str(runner.directory / "pytest.xml"),
            ],
            cwd=BACKEND,
            timeout=2400,
        )
    finally:
        try:
            runner.cleanup()
        finally:
            args.artifacts.mkdir(parents=True, exist_ok=True)
            for path in runner.directory.iterdir():
                if path.is_file():
                    shutil.copy2(path, args.artifacts / path.name)
            print(f"Backend evidence: {args.artifacts.resolve()}", flush=True)
            log = runner.directory / "pytest.log"
            if log.exists():
                print(log.read_text(errors="replace")[-16000:], flush=True)
            shutil.rmtree(runner.directory)


if __name__ == "__main__":
    main()
