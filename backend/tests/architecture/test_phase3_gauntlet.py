"""Fail-closed contract for the Phase 3 pre-closeout gauntlet."""

from __future__ import annotations

import ast
import re
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
GAUNTLET_PATH = REPOSITORY_ROOT / "tools" / "phase3_gauntlet.sh"
MANIFEST_PATH = REPOSITORY_ROOT / "tools" / "phase3_source_manifest.txt"
MUTATION_PATH = REPOSITORY_ROOT / "tools" / "verify_import_job_mutants.py"
EVIDENCE_PATH = REPOSITORY_ROOT / "docs" / "evidence" / "phase-03.md"

EXPECTED_LAYERS = (
    "source-state",
    "checker-negative-controls",
    "backend-tests-coverage",
    "backend-types-lint-format",
    "migrations-openapi",
    "frontend-tests-coverage",
    "frontend-types-lint-format-build",
    "targeted-mutation-proof",
    "playwright-responsive-accessibility",
    "supply-chain-license-secret-schema",
    "architecture-provider-audit",
    "mock-deployment-smoke",
    "api-coverage-preseal",
    "final-source-state",
)

EXPECTED_MUTATION_DOMAINS = {
    "capability",
    "state",
    "provenance",
    "ancestry",
    "rewrite",
    "error",
}


def _read(path: Path) -> str:
    assert path.is_file(), f"required Phase 3 closeout source is missing: {path.name}"
    return path.read_text(encoding="utf-8")


def test_phase3_gauntlet_declares_one_exact_ordered_fail_closed_layer_set() -> None:
    source = _read(GAUNTLET_PATH)
    match = re.search(
        r'readonly EXPECTED_LAYERS="(?P<layers>.*?)"',
        source,
        flags=re.DOTALL,
    )
    assert match is not None
    assert tuple(match.group("layers").splitlines()) == EXPECTED_LAYERS
    assert 'assert_exact_layers "$EXPECTED_LAYERS"' in source
    assert '"$GAUNTLET_DIR/phase3_smoke.sh" --mock-provider' in source
    assert "api-coverage.verify-pre" in source
    assert "--live-provider-read-only" not in source


def test_phase3_manifest_covers_sources_and_excludes_mutable_closeout_artifacts() -> None:
    rows = [line for line in _read(MANIFEST_PATH).splitlines() if line and not line.startswith("#")]
    includes = {line for line in rows if line.startswith("include|")}
    exclusions = {line for line in rows if line.startswith("exclude|")}
    required = {
        "include|implementation|:(glob)backend/src/**/*.py",
        "include|implementation|:(glob)frontend/src/**/*.ts",
        "include|implementation|:(glob)frontend/src/**/*.tsx",
        "include|tests|:(glob)backend/tests/**/*.py",
        "include|tests|:(glob)frontend/src/**/*.test.ts",
        "include|tests|:(glob)frontend/src/**/*.test.tsx",
        "include|tests|:(glob)frontend/e2e/**/*.ts",
        "include|verifier-scripts|:(glob)tools/**",
        "include|deployment-contract|tools/phase3_smoke.sh",
    }
    assert required <= includes
    assert any("docs/evidence/**" in row for row in exclusions)
    assert any("03-*-SUMMARY.md" in row for row in exclusions)
    assert any("03-REVIEW.md" in row for row in exclusions)
    assert any("03-VERIFICATION.md" in row for row in exclusions)


def test_import_mutation_proof_has_exact_nonempty_domain_ownership() -> None:
    source = _read(MUTATION_PATH)
    module = ast.parse(source)
    domains: list[str] = []
    for node in ast.walk(module):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        if node.func.id != "Mutation" or not node.args:
            continue
        first = node.args[0]
        assert isinstance(first, ast.Constant) and isinstance(first.value, str)
        domains.append(first.value.split(":", 1)[0])
    assert set(domains) == EXPECTED_MUTATION_DOMAINS
    assert len(domains) == len(set(domains))
    assert "surviving mutant" in source
    assert "mutation checker negative control: PASS" in source


def test_phase3_evidence_remains_bounded_and_excludes_mutable_authority() -> None:
    source = _read(EVIDENCE_PATH)
    assert "# Phase 3" in source
    assert "Gauntlet-status:" in source
    assert "Source-digest:" in source
    forbidden = (
        "Authorization: Bearer",
        "Authorization: Basic",
        "client_secret=",
        "access_token=",
        "refresh_token=",
    )
    assert not any(value in source for value in forbidden)
