"""Fail-closed contracts for the targeted preview-job mutation verifier."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

BACKEND_ROOT = Path(__file__).resolve().parents[2]
VERIFIER_PATH = BACKEND_ROOT.parent / "tools" / "verify_preview_job_mutants.py"


def _load_verifier() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "verboflex_preview_job_mutation_verifier",
        VERIFIER_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_every_preview_job_mutation_subject_is_unambiguous() -> None:
    """Each reviewed mutant must still select exactly one source fragment."""
    verifier = _load_verifier()

    for mutation in verifier.MUTATIONS:
        source = (BACKEND_ROOT / mutation.relative_path).read_text()
        assert source.count(mutation.original) == 1, mutation.label
