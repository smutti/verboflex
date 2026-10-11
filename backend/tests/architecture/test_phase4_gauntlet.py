"""The delivery runner must never certify partial, failed or changing sources."""

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize(
    "changed", [b" M backend/a.py", b"A  tools/a.py", b" D frontend/a.ts", b"?? tools/new.py"]
)
def test_final_gate_rejects_uncommitted_delivery_inputs(monkeypatch, changed):
    import runpy

    namespace = runpy.run_path(str(ROOT / "tools/phase4_gate.py"))
    calls = []

    def git_status(command, **kwargs):
        calls.append(command)
        return changed

    monkeypatch.setattr(namespace["subprocess"], "check_output", git_status)
    with pytest.raises(ValueError, match="committed delivery"):
        namespace["require_clean_source"]()
    assert "--untracked-files=all" in calls[0]
    assert {"backend", "frontend", "tools", "AGENTS.md"} <= set(calls[0])
    assert ".planning" not in calls[0]


def test_gate_requires_changed_line_coverage_for_both_applications():
    import ast

    source = (ROOT / "tools/phase4_gate.py").read_text()
    tree = ast.parse(source)
    commands = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "command"
    ]
    coverage = {
        node.args[0].value: node
        for node in commands
        if node.args
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value
        in {"backend-changed-line-coverage", "frontend-changed-line-coverage"}
    }
    assert set(coverage) == {"backend-changed-line-coverage", "frontend-changed-line-coverage"}
    for command in coverage.values():
        literal_args = {
            node.value
            for node in ast.walk(command)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
        assert {"diff-cover", "--fail-under=100", "--compare-branch="} <= literal_args
        assert any(
            isinstance(node, ast.Name) and node.id == "PHASE4_BASE" for node in ast.walk(command)
        )


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
    monkeypatch.setattr(module, "require_clean_source", lambda: None)
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
