"""A trusted adapter result still has to match the worker's immutable authority."""

import base64
import hashlib
import json
from pathlib import Path
from uuid import uuid4

import pytest

from verboflex.core.config import Settings
from verboflex.worker import screenshot_tasks

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a7n8AAAAASUVORK5CYII="
)


@pytest.mark.parametrize(
    "damage",
    [
        None,
        "image_digest",
        "input_digest",
        "commit",
        "scenario_id",
        "language",
        "viewport",
        "source_digest",
        "manifest_digest",
        "dimensions",
    ],
)
def test_worker_rejects_mismatched_web_receipt(monkeypatch, damage):
    payload = {
        "engine": "web",
        "commit": "a" * 40,
        "request": {"scenario_id": "sites.list", "viewport": "desktop"},
        "language": "it",
        "source_digest": "b" * 64,
        "manifest_digest": "c" * 64,
        "viewport": {"width": 1, "height": 1},
    }
    monkeypatch.setattr(
        screenshot_tasks,
        "get_settings",
        lambda: Settings(web_screenshot_runner_command=["trusted-test-adapter"]),
    )

    def adapter(command, **kwargs):
        assert set(kwargs["env"]) <= {"PATH", "TMPDIR"}
        output = Path(command[command.index("--output") + 1])
        request = Path(command[command.index("--input") + 1])
        receipt = {
            "engine": "web",
            "version": 1,
            "render_id": str(uuid4()),
            "rendered_at": "2026-11-06T12:00:00Z",
            "input_digest": hashlib.sha256(request.read_bytes()).hexdigest(),
            "image_digest": hashlib.sha256(PNG).hexdigest(),
            "commit": payload["commit"],
            "scenario_id": "sites.list",
            "language": "it",
            "viewport": "desktop",
            "source_digest": payload["source_digest"],
            "manifest_digest": payload["manifest_digest"],
            "location": {"status": "found", "regions": [{"x": 0, "y": 0, "width": 1, "height": 1}]},
            "text": "Synthetic text",
        }
        if damage and damage != "dimensions":
            receipt[damage] = (
                "mobile"
                if damage == "viewport"
                else "z"
                if damage in {"language", "scenario_id"}
                else "d" * (40 if damage == "commit" else 64)
            )
        output.write_bytes(PNG)
        output.with_suffix(".json").write_text(json.dumps(receipt))

    monkeypatch.setattr(screenshot_tasks.subprocess, "run", adapter)
    if damage == "dimensions":
        payload["viewport"]["width"] = 2
    if damage:
        with pytest.raises(ValueError):
            screenshot_tasks.render_web(payload)
    else:
        image, receipt = screenshot_tasks.render_web(payload)
        assert image == PNG and receipt["language"] == "it"
