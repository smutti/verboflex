#!/usr/bin/env python3
"""Repeatable isolated Phase 4 quality gate with digest-only command reporting."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
PHASE4_BASE = "d987d5f48273d49234b07aacb3fa185337a1b4f2"
LAYERS = (
    "source-scope-closeout",
    "backend-tests-migrations-parsers-worker",
    "backend-changed-line-parser-coverage",
    "backend-types-lint-format",
    "generated-client",
    "frontend-unit-accessibility-coverage",
    "frontend-types-lint-build",
    "python-vulnerabilities",
    "python-license-policy",
    "npm-vulnerabilities",
    "npm-lock-license-identity",
    "adversarial-mutations",
    "browser-responsive-smoke",
    "built-stack-smoke",
)


def terminate(process):
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=8)


class Gate:
    def __init__(self):
        os.umask(0o077)
        self.directory = Path(tempfile.mkdtemp(prefix="verboflex-phase04-gate-"))
        os.chmod(self.directory, 0o700)
        self.environment = dict(os.environ, PHASE4_RESULT_DIR=str(self.directory))
        self.environment["COVERAGE_FILE"] = str(
            self.directory / "backend-coverage-data"
        )
        self.containers = []
        self.processes = []
        self.records = []
        self.closed = False

    def command(self, label, command, *, cwd=ROOT, timeout=900):
        log = self.directory / (label + ".log")
        started = time.monotonic()
        started_at = datetime.now(UTC).isoformat()
        with log.open("wb") as stream:
            os.chmod(log, 0o600)
            process = subprocess.Popen(
                command,
                cwd=cwd,
                env=self.environment,
                stdout=stream,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            try:
                code = process.wait(timeout=timeout)
            except BaseException:
                terminate(process)
                raise
        raw = log.read_bytes()
        record = {
            "section": label,
            "command": command,
            "cwd": str(cwd.relative_to(ROOT)) or ".",
            "exit": code,
            "started_at": started_at,
            "completed_at": datetime.now(UTC).isoformat(),
            "duration_seconds": round(time.monotonic() - started, 3),
            "output_sha256": hashlib.sha256(raw).hexdigest(),
        }
        self.records.append(record)
        (self.directory / "commands.json").write_text(
            json.dumps(self.records, indent=2)
        )
        print(json.dumps(record), flush=True)
        if code != 0:
            raise ValueError("section failed: " + label)
        return raw

    def capture(self, command):
        return (
            subprocess.check_output(command, stderr=subprocess.DEVNULL, timeout=90)
            .decode()
            .strip()
        )

    def start_infrastructure(self):
        suffix = uuid.uuid4().hex[:12]
        for service, image, port, extra in [
            (
                "postgres",
                "postgres:18-alpine",
                "5432",
                ["-e", "POSTGRES_HOST_AUTH_METHOD=trust"],
            ),
            ("redis", "redis:7-alpine", "6379", []),
        ]:
            name = f"verboflex-phase04-{service}-{suffix}"
            self.containers.append(name)
            self.capture(
                [
                    "docker",
                    "run",
                    "-d",
                    "--rm",
                    "--name",
                    name,
                    "-p",
                    f"127.0.0.1::{port}",
                    *extra,
                    image,
                ]
            )
            deadline = time.monotonic() + 60
            ready = (
                # The entrypoint's bootstrap server accepts Unix-socket probes
                # before it restarts. TCP becomes ready only on the final server.
                ["pg_isready", "-h", "127.0.0.1", "-U", "postgres"]
                if service == "postgres"
                else ["redis-cli", "ping"]
            )
            while subprocess.run(
                ["docker", "exec", name, *ready],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=4,
            ).returncode:
                if time.monotonic() > deadline:
                    raise ValueError("isolated service readiness timeout")
                time.sleep(0.5)
            host_port = self.capture(["docker", "port", name, port + "/tcp"]).rsplit(
                ":", 1
            )[1]
            if service == "postgres":
                self.environment["VERBOFLEX_TEST_POSTGRES_ADMIN_URL"] = (
                    f"postgresql://postgres@127.0.0.1:{host_port}/postgres"
                )
                # Own only this disposable instance; template grants extension to test-created DBs.
                for database in ("postgres", "template1"):
                    self.capture(
                        [
                            "docker",
                            "exec",
                            name,
                            "psql",
                            "-U",
                            "postgres",
                            "-d",
                            database,
                            "-c",
                            "CREATE EXTENSION pg_trgm",
                        ]
                    )
            else:
                url = f"redis://127.0.0.1:{host_port}/0"
                self.environment.update(
                    VERBOFLEX_TEST_CELERY_REDIS_URL=url, VERBOFLEX_REDIS_URL=url
                )
        worker_log = (self.directory / "worker.log").open("wb")
        worker = subprocess.Popen(
            [
                str(BACKEND / ".venv/bin/celery"),
                "-A",
                "verboflex.worker.celery_app",
                "worker",
                "--pool=solo",
                "--concurrency=1",
                "--loglevel=WARNING",
            ],
            cwd=BACKEND,
            env=self.environment,
            stdout=worker_log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        worker_log.close()
        self.processes.append(worker)
        deadline = time.monotonic() + 60
        while True:
            probe = subprocess.run(
                [
                    str(BACKEND / ".venv/bin/celery"),
                    "-A",
                    "verboflex.worker.celery_app",
                    "inspect",
                    "ping",
                    "--timeout=1",
                ],
                cwd=BACKEND,
                env=self.environment,
                capture_output=True,
                timeout=20,
            )
            if probe.returncode == 0 and b"1 node online" in probe.stdout:
                break
            if worker.poll() is not None or time.monotonic() > deadline:
                raise ValueError("isolated worker readiness timeout")
            time.sleep(0.5)

    def browser(self):
        import urllib.request

        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        stream = (self.directory / "preview.log").open("wb")
        process = subprocess.Popen(
            [
                "node",
                "node_modules/vite/bin/vite.js",
                "preview",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--strictPort",
            ],
            cwd=ROOT / "frontend",
            stdout=stream,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        stream.close()
        self.processes.append(process)
        url = f"http://127.0.0.1:{port}"
        deadline = time.monotonic() + 30
        while True:
            try:
                with urllib.request.urlopen(
                    url + "/translations/opaque", timeout=2
                ) as response:
                    assert response.status == 200
                break
            except OSError:
                if process.poll() is not None or time.monotonic() > deadline:
                    raise ValueError("built SPA readiness timeout") from None
                time.sleep(0.25)
        self.environment.update(
            PLAYWRIGHT_BASE_URL=url,
            PLAYWRIGHT_OUTPUT_DIR=str(self.directory / "playwright"),
        )
        self.command(
            "browser-responsive-smoke",
            ["npm", "--prefix", "frontend", "run", "e2e", "--", "translations.spec.ts"],
            timeout=300,
        )

    def cleanup(self):
        if self.closed:
            return
        for process in reversed(self.processes):
            terminate(process)
        for name in reversed(self.containers):
            subprocess.run(
                ["docker", "stop", "--time", "5", name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30,
                check=True,
            )
        self.closed = True


def require_clean_source():
    changed = subprocess.check_output(
        [
            "git",
            "status",
            "--porcelain",
            "--untracked-files=all",
            "--",
            "backend",
            "frontend",
            "tools",
            "docker-compose.yml",
            ".env.example",
            "AGENTS.md",
        ],
        cwd=ROOT,
    )
    if changed.strip():
        raise ValueError("full evidence requires committed delivery sources")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--section", choices=LAYERS)
    args = parser.parse_args()
    if args.list:
        print("\n".join(LAYERS))
        return 0
    gate = Gate()
    from verify_phase4_closeout import source_digest

    digest = source_digest()
    try:
        if not args.section:
            require_clean_source()
        gate.start_infrastructure()
        for layer in LAYERS:
            if args.section and args.section != layer:
                continue
            if layer == "source-scope-closeout":
                gate.command(
                    layer,
                    [
                        "uv",
                        "run",
                        "pytest",
                        "tests/architecture/test_phase4_scope.py",
                        "tests/architecture/test_phase4_closeout_gate.py",
                        "tests/architecture/test_background_boundaries.py",
                        "-q",
                    ],
                    cwd=BACKEND,
                )
                gate.command(
                    "smoke-tooling-controls",
                    [
                        "uv",
                        "run",
                        "--project",
                        "backend",
                        "pytest",
                        "tools/tests/test_phase4_smoke.py",
                        "-q",
                    ],
                )
                gate.command(
                    "smoke-shell-controls", ["bash", "tools/tests/test_phase4_smoke.sh"]
                )
            elif layer == "backend-tests-migrations-parsers-worker":
                gate.command(
                    layer,
                    [
                        "uv",
                        "run",
                        "pytest",
                        "-q",
                        "--randomly-seed=419",
                        "--junitxml=" + str(gate.directory / "backend.xml"),
                        "--cov=verboflex",
                        "--cov-branch",
                        "--cov-report=term-missing",
                        "--cov-report=xml:"
                        + str(gate.directory / "backend-coverage.xml"),
                        # Whole-project coverage is diagnostic, as in Phase 3.
                        # The following layer enforces changed-line and parser thresholds.
                        "--cov-fail-under=0",
                    ],
                    cwd=BACKEND,
                )
            elif layer == "backend-changed-line-parser-coverage":
                gate.command(
                    "backend-changed-line-coverage",
                    [
                        "uv",
                        "run",
                        "diff-cover",
                        str(gate.directory / "backend-coverage.xml"),
                        "--compare-branch=" + PHASE4_BASE,
                        "--fail-under=100",
                    ],
                    cwd=BACKEND,
                )
                gate.command(
                    "parser-branch-coverage",
                    [
                        "uv",
                        "run",
                        "coverage",
                        "report",
                        "--include=*/localization/importing/*",
                        "--fail-under=100",
                    ],
                    cwd=BACKEND,
                )
            elif layer == "backend-types-lint-format":
                for command in (
                    ["mypy", "src"],
                    ["ruff", "check", "src", "tests"],
                    ["ruff", "format", "--check", "src", "tests", "alembic"],
                ):
                    gate.command(
                        layer
                        + "-"
                        + command[0]
                        + ("-format" if "format" in command else ""),
                        ["uv", "run", *command],
                        cwd=BACKEND,
                    )
            elif layer == "generated-client":
                gate.command(layer, ["npm", "--prefix", "frontend", "run", "api:check"])
            elif layer == "frontend-unit-accessibility-coverage":
                gate.command(
                    layer,
                    [
                        "npm",
                        "--prefix",
                        "frontend",
                        "run",
                        "test:coverage",
                        "--",
                        "--coverage.reportsDirectory="
                        + str(gate.directory / "frontend-coverage"),
                        "--coverage.reporter=text",
                        "--coverage.reporter=cobertura",
                    ],
                )
                gate.command(
                    "frontend-changed-line-coverage",
                    [
                        "uv",
                        "run",
                        "diff-cover",
                        str(
                            gate.directory / "frontend-coverage/cobertura-coverage.xml"
                        ),
                        "--compare-branch=" + PHASE4_BASE,
                        "--fail-under=100",
                    ],
                    cwd=BACKEND,
                )
            elif layer == "frontend-types-lint-build":
                for command in ("typecheck", "lint", "format:check", "build"):
                    gate.command(
                        layer + "-" + command,
                        ["npm", "--prefix", "frontend", "run", command],
                    )
            elif layer == "python-vulnerabilities":
                gate.command(layer, ["uv", "run", "pip-audit"], cwd=BACKEND)
            elif layer == "python-license-policy":
                licenses = gate.command(
                    layer + "-inventory",
                    ["uv", "run", "pip-licenses", "--format=json", "--with-urls"],
                    cwd=BACKEND,
                )
                destination = gate.directory / "licenses.json"
                destination.write_bytes(licenses)
                os.chmod(destination, 0o600)
                gate.command(
                    layer,
                    [
                        "bash",
                        "tools/phase4_parser_checkpoint.sh",
                        "--license-policy",
                        str(destination),
                    ],
                )
                gate.command(
                    "regex-exact-identity",
                    [
                        "uv",
                        "run",
                        "python",
                        "-c",
                        "import regex; assert regex.__version__ == '2026.9.3'; "
                        "print(regex.__version__)",
                    ],
                    cwd=BACKEND,
                )
            elif layer == "npm-vulnerabilities":
                gate.command(
                    layer,
                    ["npm", "--prefix", "frontend", "audit", "--audit-level=high"],
                )
            elif layer == "npm-lock-license-identity":
                gate.command(
                    layer + "-tree",
                    ["npm", "--prefix", "frontend", "ls", "--all", "--json"],
                )
                gate.command(layer, ["node", "tools/verify_phase4_npm.mjs"])
                gate.command(
                    layer + "-controls",
                    ["node", "tools/verify_phase4_npm.mjs", "--self-test"],
                )
            elif layer == "adversarial-mutations":
                gate.command(
                    layer,
                    [
                        str(BACKEND / ".venv/bin/python"),
                        "tools/verify_translation_mutants.py",
                    ],
                    timeout=1500,
                )
            elif layer == "browser-responsive-smoke":
                gate.browser()
            elif layer == "built-stack-smoke":
                gate.command(layer, ["bash", "tools/phase4_smoke.sh"], timeout=1800)
        if digest != source_digest():
            raise ValueError("source changed during gauntlet")
        result = {
            "status": "passed" if not args.section else "partial",
            "source_digest": digest,
            "gauntlet_exit": 0 if not args.section else None,
            "sections": list(LAYERS) if not args.section else [args.section],
            "records": gate.records,
        }
        gate.cleanup()
        (gate.directory / "result.json").write_text(json.dumps(result, indent=2))
        print(
            json.dumps(
                {
                    "status": result["status"],
                    "source_digest": digest,
                    "evidence": str(gate.directory),
                }
            ),
            flush=True,
        )
    finally:
        gate.cleanup()
        print(
            json.dumps({"retained_owner_only_evidence": str(gate.directory)}),
            flush=True,
        )
    return 0


if __name__ == "__main__":

    def stop(_signum, _frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        raise SystemExit(main())
    except ValueError, OSError, subprocess.SubprocessError:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "reason": "quality section or isolated service failed",
                }
            ),
            file=sys.stderr,
        )
        raise SystemExit(1) from None
