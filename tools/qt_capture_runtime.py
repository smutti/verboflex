#!/usr/bin/env python3
"""Run inside the pinned Qt image; verify source closure before invoking its binary.

Image contract: /opt/qt-manifest.json contains the reviewed manifest;
/opt/qt-capture-render takes --input and --output, writes PNG and JSON metadata
{qt_version, platform, width, height, text, location}. It must use the original
application widgets and fonts. This wrapper never executes archive contents.
"""

import base64
import hashlib
import json
import subprocess
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def verify_sources(archive: Path, payload: dict, reviewed: dict) -> None:
    manifest = payload["manifest"]
    if manifest != reviewed:
        raise ValueError("Qt image does not contain the reviewed application")
    expected = {
        **manifest["sources"],
        ".verboflex/qt-screenshots.json": payload["manifest_digest"],
    }
    if (
        hashlib.sha256(
            json.dumps(manifest["sources"], sort_keys=True).encode()
        ).hexdigest()
        != payload["source_digest"]
    ):
        raise ValueError("Qt source digest mismatch")
    seen = set()
    total = 0
    with tarfile.open(archive) as tar:
        for item in tar:
            if item.isdir():
                continue
            if item.name not in expected or item.name in seen or not item.isfile():
                raise ValueError("Unexpected Qt source archive entry")
            total += item.size
            if item.size > 32 * 1024 * 1024 or total > 128 * 1024 * 1024:
                raise ValueError("Qt source archive exceeds its budget")
            stream = tar.extractfile(item)
            if (
                stream is None
                or hashlib.sha256(stream.read()).hexdigest() != expected[item.name]
            ):
                raise ValueError("Qt application sources changed")
            seen.add(item.name)
    if seen != set(expected):
        raise ValueError("Qt application source is missing")


def main() -> None:
    raw = Path("/input.json").read_bytes()
    if len(raw) > 4 * 1024 * 1024:
        raise ValueError("Qt bundle too large")
    payload = json.loads(raw)
    manifest = payload["manifest"]
    verify_sources(
        Path("/source.tar"),
        payload,
        json.loads(Path("/opt/qt-manifest.json").read_bytes()),
    )
    scenario = next(
        s for s in manifest["scenarios"] if s["id"] == payload["request"]["scenario_id"]
    )
    if scenario != payload["scenario"]:
        raise ValueError("Qt scenario mismatch")
    with tempfile.TemporaryDirectory(prefix="qt-render-") as directory:
        output = Path(directory) / "image.png"
        environment = {
            "PATH": "/usr/bin:/bin",
            "HOME": directory,
            "XDG_RUNTIME_DIR": directory,
            "QT_QPA_PLATFORM": manifest["platform"],
            "QT_SCALE_FACTOR": "1",
            "QT_AUTO_SCREEN_SCALE_FACTOR": "0",
            "QT_ENABLE_HIGHDPI_SCALING": "0",
            "LANG": "C.UTF-8",
            "TZ": "UTC",
        }
        subprocess.run(
            [
                "/opt/qt-capture-render",
                "--input",
                "/input.json",
                "--output",
                str(output),
            ],
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=60,
            check=True,
        )
        if (
            output.stat().st_size > 8 * 1024 * 1024
            or output.with_suffix(".json").stat().st_size > 131072
        ):
            raise ValueError("Qt render output exceeds its budget")
        png = output.read_bytes()
        metadata = json.loads(output.with_suffix(".json").read_bytes())
        for key in ("width", "height", "qt_version", "platform"):
            if metadata[key] != manifest[key]:
                raise ValueError("Qt runtime differs from the reviewed profile")
        if metadata["text"] != payload["target_text"]:
            raise ValueError("Qt renderer did not use the requested text")
    receipt = {
        key: payload[key]
        for key in ("commit", "language", "manifest_digest", "source_digest")
    }
    receipt.update(
        {
            key: metadata[key]
            for key in ("width", "height", "qt_version", "platform", "text", "location")
        }
    )
    receipt.update(
        engine="qt",
        version=1,
        render_id=str(uuid4()),
        rendered_at=datetime.now(timezone.utc).isoformat(),
        application_commit=payload["commit"],
        scenario_id=scenario["id"],
        input_digest=hashlib.sha256(raw).hexdigest(),
        image_digest=hashlib.sha256(png).hexdigest(),
    )
    print(
        json.dumps({"png": base64.b64encode(png).decode("ascii"), "receipt": receipt})
    )


if __name__ == "__main__":
    main()
