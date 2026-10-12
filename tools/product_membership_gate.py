#!/usr/bin/env python3
"""Reproduce product-team verification using only owned test infrastructure."""

import argparse
import hashlib
import os
import shutil
import signal
import socket
import subprocess
import time
import urllib.request
from pathlib import Path

from phase4_gate import Gate

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / "backend/.venv/bin/python"


def source_hash():
    files = (
        subprocess.check_output(
            ["git", "ls-files", "-co", "--exclude-standard", "-z"], cwd=ROOT
        )
        .decode()
        .split("\0")
    )
    digest = hashlib.sha256()
    for name in sorted(set(files)):
        if not name or name == "docs/product-membership-evidence.md":
            continue
        path = ROOT / name
        if path.is_file():
            digest.update(name.encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument(
        "--focused", action="store_true", help="Skip full suites and built-stack smoke"
    )
    parser.add_argument("--hash-only", action="store_true")
    args = parser.parse_args()
    args.artifacts.mkdir(parents=True, exist_ok=True)
    (args.artifacts / "source.sha256").write_text(source_hash() + "\n")
    if args.hash_only:
        print(source_hash())
        return
    environment = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("VERBOFLEX_", "BITBUCKET_"))
    }

    def run(name, command, *, cwd=ROOT, env=environment):
        print(name, flush=True)
        with (args.artifacts / (name + ".log")).open("w") as log:
            subprocess.run(
                list(map(str, command)),
                cwd=cwd,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=True,
                timeout=3000,
            )

    run(
        "backend-lint",
        [ROOT / "backend/.venv/bin/ruff", "check", "backend/src", "backend/tests"],
    )
    run("backend-types", [ROOT / "backend/.venv/bin/mypy", "backend/src"])
    run("frontend-lint", ["npm", "--prefix", "frontend", "run", "lint"])
    run("frontend-build", ["npm", "--prefix", "frontend", "run", "build"])
    run("contract", [PYTHON, "mcp-server/generate_contract.py", "--check"])
    run(
        "policy-mutation",
        [
            PYTHON,
            "tools/product_membership_mutation.py",
            "--properties-only",
            "--artifacts",
            args.artifacts / "mutation",
        ],
    )
    gate = Gate()
    gate.environment = {
        k: v for k, v in gate.environment.items() if not k.startswith("VERBOFLEX_")
    }
    try:
        gate.start_infrastructure()
        gate.command(
            "team-coverage",
            [
                str(ROOT / "backend/.venv/bin/pytest"),
                "tests/auth/test_product_access.py",
                "tests/api/test_product_team.py",
                "tests/api/test_product_team_edges.py",
                "tests/api/test_product_team_credentials.py",
                "--cov=verboflex.auth.product_access",
                "--cov=verboflex.services.product_team",
                "--cov=verboflex.api.v1.routes.product_team",
                "--cov-branch",
                "--cov-report=term-missing",
                "--cov-fail-under=100",
            ],
            cwd=ROOT / "backend",
            timeout=180,
        )
    finally:
        gate.cleanup()
        for path in gate.directory.iterdir():
            if path.is_file():
                shutil.copy2(path, args.artifacts / ("focused-" + path.name))
        shutil.rmtree(gate.directory)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    with (args.artifacts / "ui-server.log").open("w") as log:
        server = subprocess.Popen(
            [
                "node",
                "node_modules/vite/bin/vite.js",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--strictPort",
            ],
            cwd=ROOT / "frontend",
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            deadline = time.monotonic() + 30
            while True:
                if server.poll() is not None or time.monotonic() >= deadline:
                    raise RuntimeError("Isolated UI server failed to start")
                try:
                    with urllib.request.urlopen(
                        f"http://127.0.0.1:{port}", timeout=1
                    ) as response:
                        if response.status == 200:
                            break
                except OSError:
                    time.sleep(0.2)
            run(
                "team-browser",
                [
                    "node",
                    "tools/product_team_ui_smoke.mjs",
                    f"http://127.0.0.1:{port}",
                    args.artifacts / "ui",
                ],
            )
        finally:
            os.killpg(server.pid, signal.SIGTERM)
            server.wait(timeout=10)
    if not args.focused:
        run(
            "backend",
            [PYTHON, "tools/ci_backend.py", "--artifacts", args.artifacts / "backend"],
        )
        run(
            "frontend",
            [
                "npm",
                "--prefix",
                "frontend",
                "test",
                "--",
                "--run",
                "--sequence.shuffle",
                "--sequence.seed=11102026",
            ],
        )
        run(
            "mcp",
            [
                "uv",
                "run",
                "--project",
                "mcp-server",
                "pytest",
                "mcp-server/tests",
                "-q",
            ],
        )
        run(
            "built-smoke",
            ["bash", "tools/phase7_smoke.sh"],
            env={
                **environment,
                "PHASE8_HTTP_SETUP": "1",
                "PHASE7_EVIDENCE_DIR": str(args.artifacts / "smoke"),
            },
        )
    print("Verification complete: " + str(args.artifacts.resolve()))


if __name__ == "__main__":
    main()
