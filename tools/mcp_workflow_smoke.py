"""Real MCP stdio -> HTTP -> API -> owned PostgreSQL workflow proof.

Run with backend/.venv/bin/python tools/mcp_workflow_smoke.py after installing
mcp-server and starting a disposable PostgreSQL on port 55432. The fixture creates
and drops its own database. It never accesses application data or a Git provider.
"""

from __future__ import annotations

import importlib.util
import json
import os
import socket
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    path = ROOT / "backend/tests/api/test_translation_reviews.py"
    spec = importlib.util.spec_from_file_location("mcp_review_support", path)
    assert spec and spec.loader
    support = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(support)
    with (
        support._review_database() as factory,
        tempfile.TemporaryDirectory() as directory,
    ):
        fixture = support._seed_scalar_basis(factory, name="MCP isolated workflow")
        support.SUPPORT._configure_dependencies(factory)
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        for role in ("admin", "translator", "viewer"):
            token = support.SUPPORT._create_authority(factory, role_names=(role,))
            target = Path(directory) / f"{role}.json"
            target.write_text(
                json.dumps(
                    {
                        "api_url": f"http://127.0.0.1:{port}/api/v1",
                        "access_token": token,
                        "refresh_token": "unused-owned-fixture",
                        "expires_at": time.time() + 600,
                    }
                )
            )
            target.chmod(0o600)
        payload = support._payload(fixture, "MCP draft")
        (Path(directory) / "fixture.json").write_text(
            json.dumps(
                {
                    "group": str(fixture["group"]),
                    "payload": payload,
                }
            )
        )
        server = uvicorn.Server(
            uvicorn.Config(
                support.app,
                host="127.0.0.1",
                port=port,
                log_level="warning",
            )
        )
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 10
            while not server.started and time.monotonic() < deadline:
                time.sleep(0.05)
            assert server.started, "Isolated API failed to start"
            subprocess.run(
                [
                    str(ROOT / "mcp-server/.venv/bin/python"),
                    str(ROOT / "mcp-server/tests/probe_workflow.py"),
                    directory,
                ],
                check=True,
                timeout=60,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )
        finally:
            server.should_exit = True
            thread.join(timeout=10)


if __name__ == "__main__":
    main()
