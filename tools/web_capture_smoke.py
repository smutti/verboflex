#!/usr/bin/env python3
"""Real synthetic web E2E: PostgreSQL, API, Redis, Celery, offline Angular and Chromium."""

import argparse
import os
import shutil
import signal
import subprocess
from pathlib import Path

from phase4_gate import BACKEND, Gate

ROOT = Path(__file__).resolve().parents[1]


def interrupted(signum, _frame):
    raise SystemExit(128 + signum)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, required=True)
    args = parser.parse_args()
    args.artifacts.mkdir(parents=True, exist_ok=True)
    runner = Gate()
    runner.environment = {
        k: v for k, v in runner.environment.items() if not k.startswith("VERBOFLEX_")
    }
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    try:
        runner.command(
            "web-image",
            [
                "docker",
                "build",
                "-f",
                "docker/web-capture.Dockerfile",
                "-t",
                "verboflex-web-synthetic:local",
                ".",
            ],
            cwd=ROOT,
            timeout=900,
        )
        image = subprocess.check_output(
            [
                "docker",
                "image",
                "inspect",
                "--format={{.Id}}",
                "verboflex-web-synthetic:local",
            ],
            text=True,
        ).strip()
        runner.command(
            "web-renderer-contracts",
            [
                "docker",
                "run",
                "--rm",
                "--network=none",
                "--read-only",
                "--user=65532:65532",
                "--cap-drop=ALL",
                "--security-opt=no-new-privileges",
                "--pids-limit=512",
                "--memory=2g",
                "--tmpfs=/tmp:rw,exec,size=1g,mode=1777",
                "--entrypoint",
                "node",
                image,
                "--test",
                "/opt/web-runtime/renderer.test.mjs",
            ],
            cwd=ROOT,
            timeout=120,
        )
        repo = runner.directory / "source"
        shutil.copytree(
            ROOT / "tools/fixtures/angular-web",
            repo,
            ignore=shutil.ignore_patterns("node_modules", "dist", ".angular", ".git"),
        )
        environment = {
            **os.environ,
            "GIT_AUTHOR_NAME": "Synthetic fixture",
            "GIT_AUTHOR_EMAIL": "fixture@example.test",
            "GIT_COMMITTER_NAME": "Synthetic fixture",
            "GIT_COMMITTER_EMAIL": "fixture@example.test",
            "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z",
            "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z",
        }
        for command in (
            ["git", "init", "--quiet"],
            ["git", "add", "."],
            [
                "git",
                "-c",
                "commit.gpgsign=false",
                "commit",
                "--quiet",
                "-m",
                "Synthetic Angular fixture",
            ],
        ):
            subprocess.run(
                command, cwd=repo, env=environment, check=True, capture_output=True
            )
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo, text=True
        ).strip()
        mirror = runner.directory / "source.git"
        subprocess.run(
            ["git", "clone", "--bare", str(repo), str(mirror)],
            check=True,
            capture_output=True,
        )
        runner.start_infrastructure()
        runner.environment.update(
            VERBOFLEX_TEST_WEB_IMAGE=image,
            VERBOFLEX_TEST_WEB_COMMIT=commit,
            VERBOFLEX_TEST_WEB_MIRROR=str(mirror),
            VERBOFLEX_TEST_WEB_EVIDENCE=str(args.artifacts.resolve()),
        )
        runner.command(
            "web-e2e",
            [
                str(BACKEND / ".venv/bin/pytest"),
                "tests/integration/test_web_screenshots.py",
                "tests/api/test_project_languages.py",
                "-q",
            ],
            cwd=BACKEND,
            timeout=1800,
        )
    finally:
        runner.cleanup()
        for path in runner.directory.iterdir():
            if path.is_file():
                shutil.copy2(path, args.artifacts / path.name)
        log = runner.directory / "web-e2e.log"
        if log.exists():
            print(log.read_text(errors="replace")[-6000:])
        print(f"Web evidence: {args.artifacts.resolve()}")
        shutil.rmtree(runner.directory)


if __name__ == "__main__":
    main()
