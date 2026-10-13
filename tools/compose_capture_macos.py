#!/usr/bin/env python3
"""Local development renderer using the installed macOS Android toolchain.

Run under launchd. Only the dedicated Celery worker knows the relay credential.
An operator pins each source commit and optional reviewed fixture patch. Gradle
runs offline inside a Seatbelt sandbox with a separate, credential-free cache.
This local developer service is not a multi-tenant production runner.
"""

import argparse
import hashlib
import hmac
import json
import os
import signal
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from compose_capture import apply_fixture_patch, capture, checkout
from verboflex.localization.code_keys.capture import CaptureBundle
from verboflex.worker.screenshot_tasks import validate_png

MAX_INPUT = 4 * 1024 * 1024


def registered_profile(payload: bytes, profiles: dict) -> tuple[CaptureBundle, dict]:
    bundle = CaptureBundle.model_validate_json(payload)
    profile = profiles[bundle.capture.runner_profile]
    if (
        bundle.code_repository_id != profile["repository_id"]
        or bundle.code_commit != profile["commit"]
    ):
        raise ValueError("Unprepared source revision")
    if profile.get("patch"):
        patch = Path(profile["patch"]).read_bytes()
        if hashlib.sha256(patch).hexdigest() != profile["patch_sha256"]:
            raise ValueError("Fixture patch changed")
    return bundle, profile


def sandbox_profile(workspace: Path, profile: dict) -> str:
    def subpath(path):
        return "(subpath " + json.dumps(str(Path(path).resolve())) + ")"

    reads = [
        "/System",
        "/usr",
        "/bin",
        "/sbin",
        "/private/etc",
        "/dev",
        "/Library/Java",
        "/Library/Fonts",
        "/private/var/db/timezone",
        profile["java_home"],
        profile["android_home"],
        profile["gradle_home"],
        workspace,
    ]
    writes = [workspace, profile["gradle_home"]]
    return "\n".join(
        [
            "(version 1)",
            "(deny default)",
            "(allow process-exec process-fork signal sysctl-read mach-lookup)",
            "(allow file-read-metadata)",
            '(allow file-read-data (literal "/"))',
            "(allow file-read* " + " ".join(subpath(p) for p in reads) + ")",
            "(allow file-write* "
            + " ".join(subpath(p) for p in writes)
            + ' (literal "/dev/null"))',
            # Gradle's single-use daemon/worker protocol requires loopback sockets.
            "(allow network-bind)",
            "(allow network-inbound)",
            '(allow network-outbound (remote ip "localhost:*"))',
            # Never let repository code call this service or the local application.
            (
                '(deny network-outbound (remote ip "localhost:8766") (remote ip "localhost:8000")'
                ' (remote ip "localhost:8080") (remote ip "localhost:8443"))'
            ),
        ]
    )


def render(payload: bytes, profiles: dict) -> bytes:
    bundle, profile = registered_profile(payload, profiles)
    work_root = Path(profile["work_root"])
    work_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="capture-", dir=work_root) as directory:
        workspace = Path(directory).resolve()
        checkout(Path(profile["mirror"]), bundle.code_commit, workspace)
        if profile.get("patch"):
            apply_fixture_patch(workspace, profile["patch"])
        (workspace / "local.properties").write_text(
            "sdk.dir=" + profile["android_home"] + "\n"
        )
        (workspace / "home").mkdir()
        (workspace / "tmp").mkdir()
        policy = workspace / "capture.sb"
        policy.write_text(sandbox_profile(workspace, profile))
        environment = {
            "PATH": profile["java_home"] + "/bin:/usr/bin:/bin:/usr/sbin:/sbin",
            "JAVA_HOME": profile["java_home"],
            "ANDROID_HOME": profile["android_home"],
            "GRADLE_USER_HOME": profile["gradle_home"],
            "HOME": str(workspace / "home"),
            "TMPDIR": str(workspace / "tmp"),
            "ANDROID_USER_HOME": str(workspace / "home/.android"),
            "LANG": "en_US.UTF-8",
            "ORG_GRADLE_PROJECT_artifactory_consumer_user": "offline",
            "ORG_GRADLE_PROJECT_artifactory_consumer_key": "offline",
            "JAVA_TOOL_OPTIONS": "-Djava.net.preferIPv4Stack=true -Djava.io.tmpdir="
            + str(workspace / "tmp")
            + " -Duser.home="
            + str(workspace / "home"),
        }

        def run_build(command: list[str], cwd: Path) -> None:
            with subprocess.Popen(
                ["/usr/bin/sandbox-exec", "-f", str(policy), *command],
                cwd=cwd,
                env=environment,
                start_new_session=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            ) as process:
                try:
                    if process.wait(timeout=840) != 0:
                        raise ValueError("Compose render failed")
                finally:
                    # Also stop single-use Gradle daemons if the wrapper has exited.
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait(timeout=10)

        output = workspace / "preview.png"
        capture(workspace, bundle, output, run_build=run_build)
        content = output.read_bytes()
        validate_png(content)
        return content


def handler(token: str, profiles: dict, *, render_fn=None):
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(10)

        def log_message(self, *args):
            pass

        def do_POST(self):
            if self.path != "/capture" or not hmac.compare_digest(
                self.headers.get("Authorization", ""),
                "Bearer " + token,
            ):
                self.send_error(401)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= MAX_INPUT:
                    self.send_error(413)
                    return
                payload = self.rfile.read(length)
                registered_profile(payload, profiles)
            except (ValueError, KeyError, OSError):
                self.send_error(400)
                return
            if not lock.acquire(blocking=False):
                self.send_error(503)
                return
            try:
                content = (render_fn or render)(payload, profiles)
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(content)
            except Exception:  # noqa: BLE001 — keep build diagnostics out of HTTP responses
                self.send_error(500, "Compose rendering failed")
            finally:
                lock.release()

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profiles", type=Path, required=True)
    parser.add_argument("--token-file", type=Path, required=True)
    args = parser.parse_args()
    server = ThreadingHTTPServer(
        ("127.0.0.1", 8766),
        handler(
            args.token_file.read_text().strip(),
            json.loads(args.profiles.read_text()),
        ),
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
