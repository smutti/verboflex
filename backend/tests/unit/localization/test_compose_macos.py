"""Local relay authentication, immutable profile binding and real sandbox boundaries."""

import hashlib
import importlib
import json
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "tools"))
client = importlib.import_module("compose_capture_http")
runner = importlib.import_module("compose_capture_macos")
bundle = importlib.import_module("tests.unit.localization.test_compose_capture").bundle


def profile(tmp_path):
    patch = tmp_path / "fixture.patch"
    patch.write_text("synthetic patch")
    return {
        "synthetic": {
            "repository_id": "synthetic-app",
            "commit": "a" * 40,
            "patch": str(patch),
            "patch_sha256": hashlib.sha256(patch.read_bytes()).hexdigest(),
        }
    }


def test_profile_rejects_wrong_repository_commit_and_changed_patch(tmp_path):
    profiles = profile(tmp_path)
    payload = bundle().model_dump(mode="json")
    runner.registered_profile(json.dumps(payload).encode(), profiles)
    for key, value in [("code_repository_id", "other"), ("code_commit", "c" * 40)]:
        with pytest.raises(ValueError, match="Unprepared"):
            runner.registered_profile(json.dumps({**payload, key: value}).encode(), profiles)
    Path(profiles["synthetic"]["patch"]).write_text("changed")
    with pytest.raises(ValueError, match="patch changed"):
        runner.registered_profile(json.dumps(payload).encode(), profiles)


def test_relay_requires_auth_bounds_input_and_returns_only_rendered_png(tmp_path, monkeypatch):
    profiles = profile(tmp_path)
    calls = []

    def render(payload, config):
        calls.append(payload)
        return b"synthetic-png"

    monkeypatch.setattr(runner, "render", render)
    server = ThreadingHTTPServer(("127.0.0.1", 0), runner.handler("synthetic-token", profiles))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}"
    payload = bundle().model_dump_json().encode()
    try:
        with pytest.raises(urllib.error.HTTPError) as error:
            client.request_capture(url, "wrong-token", payload, 5)
        assert error.value.code == 401 and not calls
        with pytest.raises(urllib.error.HTTPError) as error:
            client.request_capture(url, "synthetic-token", b"{}", 5)
        assert error.value.code == 400 and not calls
        assert client.request_capture(url, "synthetic-token", payload, 5) == b"synthetic-png"
        assert calls == [payload]
        with pytest.raises(ValueError, match="input"):
            client.request_capture(url, "synthetic-token", b"x" * (client.MAX_INPUT + 1), 5)
        monkeypatch.setattr(client, "MAX_OUTPUT", 3)
        with pytest.raises(ValueError, match="output"):
            client.request_capture(url, "synthetic-token", payload, 5)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS Seatbelt only")
def test_sandbox_denies_private_files_and_external_network(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    secret = tmp_path / "synthetic-private-token"
    secret.write_text("must not be visible")
    config = {name: str(workspace) for name in ("gradle_home", "java_home", "android_home")}
    policy = workspace / "capture.sb"
    policy.write_text(runner.sandbox_profile(workspace, config))

    def run(*command):
        return subprocess.run(
            ["/usr/bin/sandbox-exec", "-f", str(policy), *command],
            cwd=workspace,
            capture_output=True,
            timeout=10,
        )

    assert run("/bin/cat", str(secret)).returncode != 0
    assert run("/bin/cat", str(policy)).returncode == 0
    assert run("/usr/bin/touch", str(tmp_path / "outside")).returncode != 0
    assert run("/usr/bin/touch", str(workspace / "inside")).returncode == 0
    assert (
        run("/usr/bin/curl", "--noproxy", "*", "--max-time", "2", "http://192.0.2.1").returncode
        != 0
    )


def test_fixture_patch_applies_inside_an_unrelated_parent_worktree(tmp_path):
    subprocess.run(["git", "init", "--quiet", str(tmp_path)], check=True)
    workspace = tmp_path / "disposable"
    workspace.mkdir()
    (workspace / "Screen.kt").write_text("private fun Preview() {}\n")
    patch = tmp_path / "fixture.patch"
    patch.write_text(
        "diff --git a/Screen.kt b/Screen.kt\n"
        "--- a/Screen.kt\n+++ b/Screen.kt\n@@ -1 +1 @@\n"
        "-private fun Preview() {}\n+internal fun Preview() {}\n"
    )
    runner.apply_fixture_patch(workspace, str(patch))
    assert (workspace / "Screen.kt").read_text() == "internal fun Preview() {}\n"
    assert not (tmp_path / "Screen.kt").exists()
