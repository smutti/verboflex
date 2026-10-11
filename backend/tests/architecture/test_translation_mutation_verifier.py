"""Failure, survivor, timeout and restoration controls for real mutation probes."""

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


def runner():
    spec = importlib.util.spec_from_file_location(
        "translation_mutants", ROOT / "tools/verify_translation_mutants.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("code,accepted", [(1, True), (0, False), (2, False), (5, False)])
def test_only_a_test_failure_kills_a_mutant_and_always_restores(tmp_path, code, accepted):
    module = runner()
    source = tmp_path / "source.py"
    source.write_bytes(b"value = 1\n")
    command = (
        sys.executable,
        "-c",
        "import pathlib,sys; assert pathlib.Path('source.py').read_text() == 'value = 2\\n'; "
        f"sys.exit({code})",
    )
    mutation = module.Mutation("control", "source.py", "value = 1", "value = 2", command)
    if accepted:
        assert module.run_mutation(mutation, tmp_path)["returncode"] == 1
    else:
        with pytest.raises(ValueError):
            module.run_mutation(mutation, tmp_path)
    assert source.read_bytes() == b"value = 1\n"


def test_timeout_and_invalid_mutations_restore_exactly(tmp_path):
    module = runner()
    source = tmp_path / "source.py"
    source.write_bytes(b"value = 1\n")
    command = (sys.executable, "-c", "import time; time.sleep(2)")
    for original, replacement in [
        ("value = 1", "value = 2"),
        ("missing", "value = 2"),
        ("value = 1", "value = ("),
    ]:
        with pytest.raises(ValueError):
            module.run_mutation(
                module.Mutation("control", "source.py", original, replacement, command),
                tmp_path,
                timeout=0.05,
            )
        assert source.read_bytes() == b"value = 1\n"


def test_inventory_names_every_required_adversary():
    mutations = runner().MUTATIONS
    assert {m.label for m in mutations} == {
        "unsafe-xml",
        "input-bound",
        "selector-collision",
        "partial-activation",
        "stale-execution",
        "offset-pagination",
        "unbound-cursor",
        "literal-wildcard",
        "cross-product-scope",
        "role-bypass",
        "client-length-authority",
        "code-point-count",
    }
    assert all(m.command for m in mutations)
