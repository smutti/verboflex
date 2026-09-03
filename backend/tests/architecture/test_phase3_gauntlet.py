"""Fail-closed contract for the Phase 3 pre-closeout gauntlet."""

from __future__ import annotations

import ast
import os
import re
import shutil
import subprocess
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
GAUNTLET_PATH = REPOSITORY_ROOT / "tools" / "phase3_gauntlet.sh"
MANIFEST_PATH = REPOSITORY_ROOT / "tools" / "phase3_source_manifest.txt"
MUTATION_PATH = REPOSITORY_ROOT / "tools" / "verify_import_job_mutants.py"
EVIDENCE_PATH = REPOSITORY_ROOT / "docs" / "evidence" / "phase-03.md"
SOURCE_STATE_PATH = REPOSITORY_ROOT / "tools" / "source_state.sh"
PLAYWRIGHT_SPEC_PATH = REPOSITORY_ROOT / "frontend" / "e2e" / "admin-configuration.spec.ts"
EDGE_MATRIX_PATH = (
    REPOSITORY_ROOT / "backend" / "tests" / "architecture" / "phase2_spec_edge_matrix.json"
)

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

EXPECTED_PLAYWRIGHT_IDS = ("UI3-C23", "UI3-C26", "PW3-C27")

EXPECTED_FRONTEND_MUTATION_MARKERS = {
    (
        "src/features/admin/imports/mutationAuthority.ts",
        "published-live-authority",
    ),
    (
        "src/features/admin/imports/mutationAuthority.ts",
        "published-request-token-ownership",
    ),
    (
        "src/features/admin/imports/mutationAuthority.ts",
        "rewrite-live-authority-request-token",
    ),
    (
        "src/features/admin/imports/mutationAuthority.ts",
        "rewrite-uncommitted-finalization",
    ),
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


def test_phase3_browser_layer_selects_every_owned_responsive_regression() -> None:
    source = _read(GAUNTLET_PATH)
    spec = _read(PLAYWRIGHT_SPEC_PATH)
    grep = re.search(
        r"npm run e2e -- e2e/admin-configuration\.spec\.ts --grep '([^']+)'",
        source,
    )
    assert grep is not None
    assert tuple(grep.group(1).split("|")) == EXPECTED_PLAYWRIGHT_IDS
    for consideration_id in EXPECTED_PLAYWRIGHT_IDS:
        assert f'test("{consideration_id} ' in spec


def test_phase3_frontend_mutation_proof_owns_exact_semantic_markers() -> None:
    source = _read(GAUNTLET_PATH)
    registry = re.search(
        r'readonly FRONTEND_MUTATION_MARKERS="(?P<rows>.*?)"',
        source,
        flags=re.DOTALL,
    )
    assert registry is not None
    owners = {tuple(row.split("|", 1)) for row in registry.group("rows").splitlines() if row}
    assert owners == EXPECTED_FRONTEND_MUTATION_MARKERS
    for relative_path, marker in owners:
        implementation = _read(REPOSITORY_ROOT / "frontend" / relative_path)
        assert implementation.count(f"phase3-mutation:{marker}") == 1
    assert "resolve_frontend_mutation_markers" in source
    assert "expected_marker_locations" in source


def test_phase3_manifest_covers_sources_and_excludes_mutable_closeout_artifacts() -> None:
    rows = [line for line in _read(MANIFEST_PATH).splitlines() if line and not line.startswith("#")]
    includes = {line for line in rows if line.startswith("include|")}
    exclusions = {line for line in rows if line.startswith("exclude|")}
    required = {
        "include|implementation|:(glob)backend/src/**/*.py",
        "include|implementation|:(glob)frontend/src/**/*.ts",
        "include|implementation|:(glob)frontend/src/**/*.tsx",
        "include|tests|:(glob)backend/tests/**/*.py",
        "include|tests|backend/tests/architecture/phase2_spec_edge_matrix.json",
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


def test_source_state_digest_changes_when_executable_json_registry_changes(
    tmp_path: Path,
) -> None:
    """A tracked semantic registry is a digest-bearing executable test input."""
    fixture = tmp_path / "source-state-json-registry"
    for directory in (
        "app",
        "backend/tests/architecture",
        "config",
        "docs",
        "locks",
        "migrations",
        "tools",
    ):
        (fixture / directory).mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE_STATE_PATH, fixture / "tools" / "source_state.sh")
    shutil.copy2(
        EDGE_MATRIX_PATH,
        fixture / "backend/tests/architecture/phase2_spec_edge_matrix.json",
    )
    files = {
        "app/main.py": "implementation\n",
        "backend/tests/test_contract.py": "def test_contract(): assert True\n",
        "config/app.conf": "config\n",
        "docs/review.md": "review\n",
        "docs/smoke.md": "smoke\n",
        "locks/deps.lock": "lock\n",
        "migrations/001.sql": "migration\n",
    }
    for relative_path, content in files.items():
        target = fixture / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    manifest = fixture / "tools" / "phase3_source_manifest.txt"
    manifest.write_text(
        "\n".join(
            (
                "include|implementation|:(glob)app/**",
                "include|tests|:(glob)backend/tests/**/*.py",
                "include|tests|backend/tests/architecture/phase2_spec_edge_matrix.json",
                "include|config|:(glob)config/**",
                "include|lockfiles|:(glob)locks/**",
                "include|migrations|:(glob)migrations/**",
                "include|verifier-scripts|:(glob)tools/**",
                "include|deployment-contract|docs/smoke.md",
                "include|review|docs/review.md",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q"], cwd=fixture, check=True)
    subprocess.run(
        ["git", "config", "user.email", "nyquist@example.invalid"],
        cwd=fixture,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "nyquist-auditor"],
        cwd=fixture,
        check=True,
    )
    subprocess.run(["git", "add", "."], cwd=fixture, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=fixture, check=True)
    environment = {
        **os.environ,
        "VERBOFLEX_SOURCE_MANIFEST": "tools/phase3_source_manifest.txt",
    }

    baseline = subprocess.run(
        [str(fixture / "tools" / "source_state.sh"), "--digest"],
        cwd=fixture,
        check=True,
        capture_output=True,
        env=environment,
        text=True,
    ).stdout.strip()
    registry = fixture / "backend/tests/architecture/phase2_spec_edge_matrix.json"
    registry.write_text(registry.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    dirty_result = subprocess.run(
        [str(fixture / "tools" / "source_state.sh"), "--digest"],
        cwd=fixture,
        check=False,
        capture_output=True,
        env=environment,
        text=True,
    )
    assert dirty_result.returncode != 0
    assert "included source has unstaged changes" in dirty_result.stderr

    subprocess.run(["git", "add", str(registry)], cwd=fixture, check=True)
    subprocess.run(
        ["git", "commit", "-qm", "mutate executable registry"],
        cwd=fixture,
        check=True,
    )
    changed = subprocess.run(
        [str(fixture / "tools" / "source_state.sh"), "--digest"],
        cwd=fixture,
        check=True,
        capture_output=True,
        env=environment,
        text=True,
    ).stdout.strip()
    assert changed != baseline


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
