"""Qt screenshots fail closed on changed source, runtime and translation authority."""

import base64
import hashlib
import importlib.util
import io
import json
import tarfile
from pathlib import Path
from uuid import uuid4

import pytest

from verboflex.core.config import Settings
from verboflex.localization.qt_capture import QtManifest
from verboflex.worker import screenshot_tasks

ROOT = Path(__file__).resolve().parents[4]
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a7n8AAAAASUVORK5CYII="
)


def manifest():
    return QtManifest(
        runner_profile="synthetic",
        width=1,
        height=1,
        qt_version="5.15.8",
        platform="offscreen",
        sources={"screen.ui": hashlib.sha256(b"form").hexdigest()},
        scenarios=[{"id": "home", "label": "Home", "context": "Main", "source": "Hello"}],
    ).model_dump(mode="json")


@pytest.mark.parametrize(
    "damage",
    [
        None,
        "text",
        "commit",
        "application_commit",
        "source_digest",
        "manifest_digest",
        "input_digest",
        "image_digest",
        "scenario_id",
        "language",
        "qt_version",
        "platform",
        "dimensions",
        "reference_image_digest",
    ],
)
def test_worker_verifies_qt_receipt(monkeypatch, damage):
    payload = {
        "engine": "qt",
        "manifest": manifest(),
        "commit": "a" * 40,
        "request": {"scenario_id": "home"},
        "language": "it-IT",
        "target_text": "Ciao",
        "source_digest": "b" * 64,
        "manifest_digest": "c" * 64,
    }
    monkeypatch.setattr(
        screenshot_tasks, "get_settings", lambda: Settings(qt_screenshot_runner_command=["adapter"])
    )

    def adapter(command, **kwargs):
        assert set(kwargs["env"]) <= {"PATH", "TMPDIR"}
        output = Path(command[command.index("--output") + 1])
        request = Path(command[command.index("--input") + 1])
        receipt = {
            key: payload[key] for key in ("commit", "language", "source_digest", "manifest_digest")
        }
        receipt.update(
            engine="qt",
            version=1,
            render_id=str(uuid4()),
            rendered_at="2026-11-10T12:00:00Z",
            input_digest=hashlib.sha256(request.read_bytes()).hexdigest(),
            image_digest=hashlib.sha256(PNG).hexdigest(),
            application_commit="a" * 40,
            scenario_id="home",
            width=1,
            height=1,
            qt_version="5.15.8",
            platform="offscreen",
            location={"status": "unavailable", "regions": []},
            text="Ciao",
        )
        if damage and damage != "dimensions":
            receipt[damage] = "d" * (40 if damage in {"commit", "application_commit"} else 64)
        output.write_bytes(PNG)
        output.with_suffix(".json").write_text(json.dumps(receipt))

    monkeypatch.setattr(screenshot_tasks.subprocess, "run", adapter)
    if damage == "dimensions":
        payload["manifest"]["width"] = 2
    if damage:
        with pytest.raises(ValueError):
            screenshot_tasks.render_qt(payload)
    else:
        assert screenshot_tasks.render_qt(payload)[0] == PNG


@pytest.mark.parametrize(
    "damage", [None, "changed", "missing", "symlink", "duplicate", "extra", "profile"]
)
def test_runtime_checks_actual_archived_sources(tmp_path, damage):
    spec = importlib.util.spec_from_file_location(
        "qt_runtime", ROOT / "tools/qt_capture_runtime.py"
    )
    runtime = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runtime)
    reviewed = manifest()
    encoded = json.dumps(reviewed).encode()
    payload = {
        "manifest": reviewed,
        "manifest_digest": hashlib.sha256(encoded).hexdigest(),
        "source_digest": hashlib.sha256(
            json.dumps(reviewed["sources"], sort_keys=True).encode()
        ).hexdigest(),
    }
    files = {"screen.ui": b"form", ".verboflex/qt-screenshots.json": encoded}
    if damage == "changed":
        files["screen.ui"] = b"changed form"
    elif damage == "missing":
        del files["screen.ui"]
    elif damage == "extra":
        files["extra"] = b"other"
    path = tmp_path / "source.tar"
    with tarfile.open(path, "w") as tar:
        for name, content in files.items():
            item = tarfile.TarInfo(name)
            item.size = len(content)
            if damage == "symlink" and name == "screen.ui":
                item.type = tarfile.SYMTYPE
                item.linkname = "/outside"
            tar.addfile(item, io.BytesIO(content))
            if damage == "duplicate":
                tar.addfile(item, io.BytesIO(content))
    if damage == "profile":
        reviewed = {**reviewed, "qt_version": "5.12.0"}
    if damage:
        with pytest.raises(ValueError):
            runtime.verify_sources(path, payload, reviewed)
    else:
        runtime.verify_sources(path, payload, reviewed)
