#!/usr/bin/env python3
"""Trusted web isolation adapter; repository builds never run on the host."""

import argparse
import base64
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path
from uuid import uuid4

from compose_capture_container import capture_output


def application_revision(payload: dict, profile: dict) -> str:
    """An operator may reuse reviewed code with new, frozen locale catalogs.

    The complete imported source/manifest set must match the reviewed digest.
    The container independently hashes every archived source before building.
    The receipt distinguishes the catalog commit from the reviewed application.
    """
    if profile["repository_id"] != payload["repository_id"]:
        raise ValueError("Repository revision is not prepared")
    revision = profile["commit"]
    if not re.fullmatch(r"[a-f0-9]{40,64}", revision):
        raise ValueError("Invalid prepared revision")
    if revision == payload["commit"]:
        return revision
    if profile.get("catalog_overlays") is not True:
        raise ValueError("Repository revision is not prepared")
    sources = payload.get("sources", [])
    hashes = {source["path"]: source["sha256"] for source in sources}
    digest = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    if (
        not hashes
        or len(hashes) != len(sources)
        or digest != profile.get("source_digest")
        or digest != payload.get("source_digest")
    ):
        raise ValueError("Application sources need operator review")
    return revision


def render(
    payload_bytes: bytes, profiles: dict, *, timeout: int = 900
) -> tuple[bytes, dict]:
    payload = json.loads(payload_bytes)
    if payload.get("engine") != "web" or payload.get("version") != 2:
        raise ValueError("Invalid web bundle")
    profile = profiles[payload["capture"]["runner_profile"]]
    build_commit = application_revision(payload, profile)
    if not re.fullmatch(
        r"(?:[a-zA-Z0-9_./:-]+@)?sha256:[a-f0-9]{64}", profile["image"]
    ):
        raise ValueError("Runner image must be pinned by digest")
    if not re.fullmatch(r"[a-f0-9]{40,64}", payload["commit"]):
        raise ValueError("Invalid source revision")
    mirror = Path(profile["mirror"]).resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix="web-container-") as directory:
        archive = Path(directory) / "source.tar"
        archive.write_bytes(
            capture_output(
                [
                    "git",
                    f"--git-dir={mirror}",
                    "archive",
                    "--format=tar",
                    build_commit,
                ],
                min(timeout, 60),
                max_bytes=128 * 1024 * 1024,
            )
        )
        archive.chmod(0o644)
        request = Path(directory) / "input.json"
        request.write_bytes(payload_bytes)
        request.chmod(0o644)
        name = "verboflex-web-" + uuid4().hex
        command = [
            "docker",
            "run",
            "--name",
            name,
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
            "--tmpfs=/tmp:rw,exec,size=4g,mode=1777",
            "--mount",
            f"type=bind,source={archive},target=/source.tar,readonly",
            "--mount",
            f"type=bind,source={request},target=/input.json,readonly",
            profile["image"],
        ]
        try:
            result = json.loads(
                capture_output(command, timeout, max_bytes=12 * 1024 * 1024)
            )
        finally:
            subprocess.run(
                ["docker", "rm", "--force", name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=20,
                check=False,
            )
    png = base64.b64decode(result["png"], validate=True)
    receipt = result["receipt"]
    receipt["application_commit"] = build_commit
    if (
        receipt["input_digest"] != hashlib.sha256(payload_bytes).hexdigest()
        or receipt["image_digest"] != hashlib.sha256(png).hexdigest()
    ):
        raise ValueError("Capture receipt does not match its inputs")
    return png, receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profiles", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    if args.input.stat().st_size > 4 * 1024 * 1024:
        raise ValueError("Bundle too large")
    png, receipt = render(
        args.input.read_bytes(),
        json.loads(args.profiles.read_bytes()),
        timeout=args.timeout,
    )
    args.output.write_bytes(png)
    args.output.with_suffix(".json").write_text(json.dumps(receipt))


if __name__ == "__main__":
    main()
