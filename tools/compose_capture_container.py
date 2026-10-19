#!/usr/bin/env python3
"""Trusted host adapter. Launch repository builds with no network or service secrets."""

import argparse
import hashlib
import json
import os
import re
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


def render(
    payload_bytes: bytes,
    profiles: dict,
    *,
    timeout: int = 900,
    exchange_root: Path | None = None,
) -> bytes:
    payload = json.loads(payload_bytes)
    name = payload["capture"]["runner_profile"]
    profile = profiles[name]
    if profile["repository_id"] != payload["code_repository_id"]:
        raise ValueError("Repository is not registered for this runner")
    if profile.get("commit") and profile["commit"] != payload.get("code_commit"):
        raise ValueError("Source revision is not prepared")
    if not re.fullmatch(
        r"(?:[a-zA-Z0-9_./:-]+@)?sha256:[a-f0-9]{64}", profile["image"]
    ):
        raise ValueError("Runner image must be pinned by digest")
    mirror = Path(profile["mirror"]).resolve(strict=True)
    patch = (
        Path(profile["patch"]).resolve(strict=True) if profile.get("patch") else None
    )
    if patch and (
        not profile.get("commit")
        or hashlib.sha256(patch.read_bytes()).hexdigest() != profile.get("patch_sha256")
    ):
        raise ValueError("Fixture patch is not bound to a reviewed revision")
    with tempfile.TemporaryDirectory(
        prefix="capture-container-", dir=exchange_root
    ) as directory:
        # Bind only the input file, read-only. Repository code has no writable
        # host mount; all its output lives in the memory-bounded /tmp filesystem.
        request = Path(directory) / "input.json"
        request.write_bytes(payload_bytes)
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
        ]
        if patch:
            command += [
                "--mount",
                f"type=bind,source={patch},target=/fixture.patch,readonly",
            ]
        command += [
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
        if profile.get("commit"):
            command += ["--commit", profile["commit"]]
        if patch:
            command += [
                "--fixture-patch",
                "/fixture.patch",
                "--fixture-patch-sha256",
                profile["patch_sha256"],
            ]
        try:
            content = capture_output(command, timeout=max(10, timeout - 20))
        finally:
            subprocess.run(
                ["docker", "rm", "--force", container_name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15,
                check=False,
            )
        return content


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profiles", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--exchange-root", type=Path)
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    args.output.write_bytes(
        render(
            args.input.read_bytes(),
            json.loads(args.profiles.read_bytes()),
            timeout=args.timeout,
            exchange_root=args.exchange_root,
        )
    )


if __name__ == "__main__":
    main()
