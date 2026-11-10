#!/usr/bin/env python3
"""Trusted Qt adapter: reviewed image, immutable sources, no network or host writes."""

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


def validate_profile(payload: dict, profile: dict) -> None:
    if payload.get("engine") != "qt" or payload.get("version") != 1:
        raise ValueError("Invalid Qt bundle")
    if (
        profile["repository_id"] != payload["repository_id"]
        or profile["source_digest"] != payload["source_digest"]
        or profile["manifest_digest"] != payload["manifest_digest"]
    ):
        raise ValueError("Qt application needs operator review")
    if not re.fullmatch(r"[a-f0-9]{40,64}", payload["commit"]):
        raise ValueError("Invalid source revision")
    if not re.fullmatch(
        r"(?:[a-zA-Z0-9_./:-]+@)?sha256:[a-f0-9]{64}", profile["image"]
    ):
        raise ValueError("Qt runner image must be pinned by digest")


def render(
    payload_bytes: bytes, profiles: dict, *, timeout: int = 900
) -> tuple[bytes, dict]:
    payload = json.loads(payload_bytes)
    profile = profiles[payload["manifest"]["runner_profile"]]
    validate_profile(payload, profile)
    mirror = Path(profile["mirror"]).resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix="qt-container-") as directory:
        archive = Path(directory) / "source.tar"
        # Executed only by the Celery capture runner, never an API request handler.
        archive.write_bytes(
            capture_output(
                [
                    "git",
                    f"--git-dir={mirror}",
                    "archive",
                    "--format=tar",
                    payload["commit"],
                    "--",
                    ".verboflex/qt-screenshots.json",
                    *sorted(payload["manifest"]["sources"]),
                ],
                min(timeout, 60),
                max_bytes=128 * 1024 * 1024,
            )
        )
        request = Path(directory) / "input.json"
        request.write_bytes(payload_bytes)
        archive.chmod(0o644)
        request.chmod(0o644)
        name = "verboflex-qt-" + uuid4().hex
        try:
            result = json.loads(
                capture_output(
                    [
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
                        "--pids-limit=128",
                        "--memory=1g",
                        "--cpus=2",
                        "--tmpfs=/tmp:rw,noexec,size=128m,mode=1777",
                        "--mount",
                        f"type=bind,source={archive},target=/source.tar,readonly",
                        "--mount",
                        f"type=bind,source={request},target=/input.json,readonly",
                        profile["image"],
                    ],
                    timeout,
                    max_bytes=12 * 1024 * 1024,
                )
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
    if (
        receipt["input_digest"] != hashlib.sha256(payload_bytes).hexdigest()
        or receipt["image_digest"] != hashlib.sha256(png).hexdigest()
    ):
        raise ValueError("Qt receipt does not match its inputs")
    # References are operator-owned device captures, never repository assertions.
    reference_key = ":".join(
        (
            payload["source_digest"],
            payload["request"]["scenario_id"],
            payload["language"],
            hashlib.sha256(payload["target_text"].encode()).hexdigest(),
        )
    )
    reference = profile.get("references", {}).get(reference_key)
    if reference is not None and reference != receipt["image_digest"]:
        raise ValueError("Qt capture differs from the device reference")
    receipt["reference_image_digest"] = reference
    return png, receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profiles", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    if args.input.stat().st_size > 4 * 1024 * 1024:
        raise ValueError("Qt bundle too large")
    png, receipt = render(
        args.input.read_bytes(),
        json.loads(args.profiles.read_bytes()),
        timeout=args.timeout,
    )
    args.output.write_bytes(png)
    args.output.with_suffix(".json").write_text(json.dumps(receipt))


if __name__ == "__main__":
    main()
