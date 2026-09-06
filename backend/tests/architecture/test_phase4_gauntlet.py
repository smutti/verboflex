"""The delivery runner must never certify partial, failed or changing sources."""

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize(
    "mode", ["full", "partial", "command-failure", "cleanup-failure", "source-drift"]
)
def test_gauntlet_certifies_only_complete_stable_success(tmp_path, monkeypatch, mode):
    spec = importlib.util.spec_from_file_location("phase4_gate", ROOT / "tools/phase4_gate.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    calls = []

    class ControlledGate:
        directory = tmp_path
        records = []

        def start_infrastructure(self):
            calls.append("infrastructure")

        def command(self, label, command, **kwargs):
            calls.append(label)
            if mode == "command-failure":
                raise ValueError("failed command")
            return b"[]"

        def cleanup(self):
            calls.append("cleanup")
            if mode == "cleanup-failure":
                raise ValueError("failed cleanup")

    digests = iter(
        ["sha256:" + "a" * 64, "sha256:" + ("b" if mode == "source-drift" else "a") * 64]
    )
    monkeypatch.setitem(
        sys.modules, "verify_phase4_closeout", SimpleNamespace(source_digest=lambda: next(digests))
    )
    monkeypatch.setattr(module, "Gate", ControlledGate)
    monkeypatch.setattr(module, "LAYERS", ("source-scope-closeout",))
    monkeypatch.setattr(
        sys,
        "argv",
        ["phase4_gate.py"] + (["--section", "source-scope-closeout"] if mode == "partial" else []),
    )
    if mode in {"command-failure", "cleanup-failure", "source-drift"}:
        with pytest.raises(ValueError):
            module.main()
        assert not (tmp_path / "result.json").exists()
    else:
        assert module.main() == 0
        result = json.loads((tmp_path / "result.json").read_text())
        assert result["status"] == ("partial" if mode == "partial" else "passed")
        assert result["gauntlet_exit"] == (None if mode == "partial" else 0)
    assert calls[0] == "infrastructure"
    assert calls[-1] == "cleanup"
