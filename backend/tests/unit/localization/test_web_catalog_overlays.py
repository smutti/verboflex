"""New locale catalogs cannot authorize a different application or scenario."""

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture
def adapter(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "tools"))
    spec = importlib.util.spec_from_file_location(
        "web_adapter", ROOT / "tools/web_capture_container.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def inputs():
    hashes = {"src/app.ts": "a" * 64, "capture.json": "b" * 64}
    digest = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    payload = {
        "repository_id": "fixture",
        "commit": "c" * 40,
        "source_digest": digest,
        "sources": [{"path": p, "sha256": h} for p, h in hashes.items()],
    }
    profile = {
        "repository_id": "fixture",
        "commit": "d" * 40,
        "catalog_overlays": True,
        "source_digest": digest,
    }
    return payload, profile


def test_catalog_update_keeps_explicitly_reviewed_application_revision(adapter):
    payload, profile = inputs()
    assert adapter.application_revision(payload, profile) == "d" * 40


@pytest.mark.parametrize(
    "damage",
    ["repository", "code", "manifest", "omit", "duplicate", "digest", "policy", "revision"],
)
def test_overlays_fail_closed_on_changed_application_authority(adapter, damage):
    payload, profile = inputs()
    if damage == "repository":
        payload["repository_id"] = "another-project"
    elif damage == "code":
        payload["sources"][0]["sha256"] = "e" * 64
    elif damage == "manifest":
        payload["sources"][1]["sha256"] = "e" * 64
    elif damage == "omit":
        payload["sources"].pop()
    elif damage == "duplicate":
        payload["sources"].append(payload["sources"][0])
    elif damage == "digest":
        payload["source_digest"] = "e" * 64
    elif damage == "policy":
        profile.pop("catalog_overlays")
    elif damage == "revision":
        profile["commit"] = "main"
    with pytest.raises(ValueError):
        adapter.application_revision(payload, profile)
