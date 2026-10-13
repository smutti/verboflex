#!/usr/bin/env python3
"""Trusted host adapter. Launch repository builds with no network or service secrets."""

import argparse
import json
import os
import selectors
import subprocess
import tempfile
import time
from pathlib import Path
from uuid import uuid4


def capture_output(command: list[str], timeout: float) -> bytes:
    """Bound even hostile stdout without giving repository code a host write mount."""
    deadline = time.monotonic() + timeout
    data = bytearray()
    with subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    ) as process:
        assert process.stdout is not None
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0 or not selector.select(remaining):
                        raise subprocess.TimeoutExpired(command, timeout)
                    block = os.read(process.stdout.fileno(), 65536)
                    if not block:
                        break
                    data.extend(block)
                    if len(data) > 8 * 1024 * 1024:
                        raise ValueError("Container output exceeds its limit")
            if process.wait(timeout=max(0, deadline - time.monotonic())) != 0:
                raise subprocess.CalledProcessError(process.returncode, command)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
    return bytes(data)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profiles", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    payload = json.loads(args.input.read_bytes())
    name = payload["capture"]["runner_profile"]
    profile = json.loads(args.profiles.read_bytes())[name]
    if profile["repository_id"] != payload["code_repository_id"]:
        raise ValueError("Repository is not registered for this runner")
    if "@sha256:" not in profile["image"]:
        raise ValueError("Runner image must be pinned by digest")
    mirror = Path(profile["mirror"]).resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix="capture-container-") as directory:
        # Bind only the input file, read-only. Repository code has no writable
        # host mount; all its output lives in the memory-bounded /tmp filesystem.
        request = Path(directory) / "input.json"
        request.write_bytes(args.input.read_bytes())
        request.chmod(0o644)
        container_name = "verboflex-capture-" + uuid4().hex
        command = [
            "docker",
            "run",
            "--name",
            container_name,
            "--rm",
            "--network=none",
            "--log-driver=none",
            "--read-only",
            "--user=65532:65532",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--pids-limit=512",
            "--memory=6g",
            "--cpus=2",
            "--tmpfs=/tmp:rw,exec,size=8g,mode=1777",
            "--mount",
            f"type=bind,source={mirror},target=/repositories/source,readonly",
            "--mount",
            f"type=bind,source={request},target=/input.json,readonly",
            profile["image"],
            "--input",
            "/input.json",
            "--output",
            "/tmp/preview.png",
            "--emit-png",
            "--mirror",
            "/repositories/source",
            "--repository-id",
            profile["repository_id"],
            "--profile",
            name,
        ]
        try:
            content = capture_output(command, timeout=max(10, args.timeout - 20))
        finally:
            subprocess.run(
                ["docker", "rm", "--force", container_name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15,
                check=False,
            )
        args.output.write_bytes(content)


if __name__ == "__main__":
    main()
