"""Exact multi-source closure guard for Phase 3.

The guard deliberately treats human-readable planning contracts as structured
inputs.  It checks semantic fingerprints, explicit Markdown/YAML ownership,
and TypeScript AST test ownership instead of accepting category-token grep
counts as evidence.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import re
import subprocess
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest
import yaml

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
PHASE_DIR = REPOSITORY_ROOT / ".planning" / "phases" / "03-bitbucket-import-integration"
CONTEXT_PATH = PHASE_DIR / "03-CONTEXT.md"
REQUIREMENTS_PATH = REPOSITORY_ROOT / ".planning" / "REQUIREMENTS.md"
COVERAGE_PATH = PHASE_DIR / "COVERAGE.md"

PLAN_PATHS = {
    "03-01-PLAN.md": PHASE_DIR / "03-01-PLAN.md",
    "03-07-PLAN.md": PHASE_DIR / "03-07-PLAN.md",
    "03-08-PLAN.md": PHASE_DIR / "03-08-PLAN.md",
}

UI_OWNER_PATHS = {
    "BitbucketConnectionPage.test.tsx": (
        REPOSITORY_ROOT / "frontend/src/features/admin/bitbucket/BitbucketConnectionPage.test.tsx"
    ),
    "PublishedMappingImports.test.tsx": (
        REPOSITORY_ROOT / "frontend/src/features/admin/imports/PublishedMappingImports.test.tsx"
    ),
    "useImportPolling.test.ts": (
        REPOSITORY_ROOT / "frontend/src/features/admin/imports/useImportPolling.test.ts"
    ),
    "ProductMappingsPage.test.tsx": (
        REPOSITORY_ROOT / "frontend/src/features/admin/mappings/ProductMappingsPage.test.tsx"
    ),
    "RewrittenBaselineDialog.test.tsx": (
        REPOSITORY_ROOT / "frontend/src/features/admin/imports/RewrittenBaselineDialog.test.tsx"
    ),
    "ProductConfiguration.test.tsx": (
        REPOSITORY_ROOT / "frontend/src/features/admin/products/ProductConfiguration.test.tsx"
    ),
    "admin-configuration.spec.ts": (REPOSITORY_ROOT / "frontend/e2e/admin-configuration.spec.ts"),
}

EXPECTED_UI_OWNERS = {
    "UI3-C01": "BitbucketConnectionPage.test.tsx",
    "UI3-C02": "PublishedMappingImports.test.tsx",
    "UI3-C03": "PublishedMappingImports.test.tsx",
    "UI3-C04": "RewrittenBaselineDialog.test.tsx",
    "UI3-C05": "BitbucketConnectionPage.test.tsx",
    "UI3-C06": "PublishedMappingImports.test.tsx",
    "UI3-C07": "useImportPolling.test.ts",
    "UI3-C08": "RewrittenBaselineDialog.test.tsx",
    "UI3-C09": "ProductMappingsPage.test.tsx",
    "UI3-C10": "BitbucketConnectionPage.test.tsx",
    "UI3-C11": "PublishedMappingImports.test.tsx",
    "UI3-C12": "RewrittenBaselineDialog.test.tsx",
    "UI3-C13": "BitbucketConnectionPage.test.tsx",
    "UI3-C14": "PublishedMappingImports.test.tsx",
    "UI3-C15": "RewrittenBaselineDialog.test.tsx",
    "UI3-C16": "RewrittenBaselineDialog.test.tsx",
    "UI3-C17": "BitbucketConnectionPage.test.tsx",
    "UI3-C18": "PublishedMappingImports.test.tsx",
    "UI3-C19": "PublishedMappingImports.test.tsx",
    "UI3-C20": "RewrittenBaselineDialog.test.tsx",
    "UI3-C21": "PublishedMappingImports.test.tsx",
    "UI3-C22": "PublishedMappingImports.test.tsx",
    "UI3-C23": "admin-configuration.spec.ts",
    "UI3-C24": "ProductConfiguration.test.tsx",
    "UI3-C25": "PublishedMappingImports.test.tsx",
    "UI3-C26": "admin-configuration.spec.ts",
}

EXPECTED_EDGE_OCCURRENCES = {
    "03-01-PLAN.md": Counter({"EDGE-BITB-02-concurrency": 1}),
    "03-07-PLAN.md": Counter(
        {
            "EDGE-BITB-02-concurrency": 1,
            "EDGE-BITB-05-adjacency": 1,
            "EDGE-BITB-05-empty": 1,
            "EDGE-BITB-05-ordering": 1,
            "EDGE-BITB-05-concurrency": 1,
            "EDGE-BITB-06-concurrency": 1,
        }
    ),
    "03-08-PLAN.md": Counter(
        {
            "EDGE-BITB-05-adjacency": 1,
            "EDGE-BITB-05-ordering": 1,
        }
    ),
}
EXPECTED_EDGE_OWNERS = {
    "EDGE-BITB-02-concurrency": "03-01-PLAN.md",
    "EDGE-BITB-05-adjacency": "03-07-PLAN.md",
    "EDGE-BITB-05-empty": "03-07-PLAN.md",
    "EDGE-BITB-05-ordering": "03-07-PLAN.md",
    "EDGE-BITB-05-concurrency": "03-07-PLAN.md",
    "EDGE-BITB-06-concurrency": "03-07-PLAN.md",
}
EXPECTED_PROHIBITIONS = (
    "The capability profile MUST NOT imply that Phase 3 performs provider writes or "
    "that a past successful capability check guarantees access to every configured "
    "repository.",
    "Administrator error guidance MUST NOT blame the user or claim that retry, "
    "reconnect, or configuration repair happened automatically when the server "
    "performed no such action.",
)

EXPECTED_DECISION_FINGERPRINTS = {
    "D-01": "1a0f6e53a7d8d2f31418",
    "D-02": "361552efe389610613eb",
    "D-03": "ca18391ed8c7cd83e06c",
    "D-04": "506073e5df0ec8147edc",
    "D-05": "71a0efd4cb1f5c3a35a2",
    "D-06": "08784f31dbe6eddb33aa",
    "D-07": "195f265b5d233da7ff4d",
    "D-08": "e4cb4156a55840c648ba",
    "D-09": "fd408c10648e858c81d5",
    "D-10": "91f6edb21eb45e07822a",
    "D-11": "2423ea50bb058b1dad7f",
    "D-12": "0e15d34583b73dc87d28",
    "D-13": "27d8ac5a72000b10c89b",
    "D-14": "c42e768a4e406d2e8a20",
    "D-15": "198a5b57f8fd8c669c7a",
    "D-16": "b236dd35f6e54af19739",
    "D-17": "8f4e018f2b65e9f08329",
    "D-18": "3751a6c973732ff9e27a",
}
EXPECTED_REQUIREMENT_FINGERPRINTS = {
    "BITB-02": "ce392101bcc9a2a918f2",
    "BITB-05": "89808ecff3351d586984",
    "BITB-06": "f47ff2edc8c85e3f064f",
}
EXPECTED_DEFERRED_FINGERPRINTS = {
    "180f0066323209bc8de9",
    "1bdac146214e93c05340",
    "1e96bd1d87791d245156",
    "57a770b7bcc4032bf36e",
    "c1fea296543ee46e4979",
}

UI_MARKER_RE = re.compile(r"UI3-C\d{2}")
EDGE_MARKER_RE = re.compile(r"EDGE-BITB-\d{2}-[a-z][a-z-]*")

NODE_UI_COLLECTOR = r"""
const fs = require("fs");
const ts = require("typescript");
const payload = JSON.parse(fs.readFileSync(0, "utf8"));
const marker = /UI3-C\d{2}/g;
const disabledNames = new Set(["skip", "todo", "fixme", "fails", "xfail"]);
const output = [];

function chain(node) {
  if (ts.isIdentifier(node)) return [node.text];
  if (ts.isPropertyAccessExpression(node)) return [...chain(node.expression), node.name.text];
  if (ts.isCallExpression(node)) return chain(node.expression);
  return [];
}

function text(node) {
  if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) return node.text;
  return null;
}

function markers(value) {
  return value ? (value.match(marker) || []) : [];
}

function parameterIds(node, owner, disabled) {
  function visit(current) {
    if (ts.isPropertyAssignment(current)) {
      const name = current.name.getText().replace(/^['\"]|['\"]$/g, "");
      if (name === "id") {
        for (const id of markers(text(current.initializer))) {
          output.push({owner, id, disabled, source: "parameter-id"});
        }
      }
    }
    ts.forEachChild(current, visit);
  }
  visit(node);
}

for (const [owner, source] of Object.entries(payload)) {
  const file = ts.createSourceFile(owner, source, ts.ScriptTarget.Latest, true,
    owner.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
  function visit(node) {
    if (ts.isCallExpression(node)) {
      const names = chain(node.expression);
      const base = names[0];
      const isTest = base === "it" || base === "test";
      if (isTest) {
        const disabled = names.some((name) => disabledNames.has(name));
        const outerEach = ts.isCallExpression(node.expression)
          && chain(node.expression.expression).includes("each");
        const direct = !ts.isCallExpression(node.expression);
        if (outerEach || direct) {
          for (const id of markers(text(node.arguments[0]))) {
            output.push({owner, id, disabled, source: "test-title"});
          }
          if (outerEach) {
            for (const argument of node.expression.arguments) {
              parameterIds(argument, owner, disabled);
            }
          }
        }
      }
    }
    ts.forEachChild(node, visit);
  }
  visit(file);
}
process.stdout.write(JSON.stringify(output));
"""


def _normalize(value: str) -> str:
    return " ".join(value.split())


def _fingerprint(value: str) -> str:
    return hashlib.sha256(_normalize(value).encode()).hexdigest()[:20]


def _frontmatter(text: str) -> dict[str, object]:
    parts = text.split("---", 2)
    assert len(parts) == 3, "planning source has no YAML frontmatter"
    parsed = yaml.safe_load(parts[1])
    assert isinstance(parsed, dict)
    return parsed


def _collect_ui_cases(sources: Mapping[str, str]) -> list[dict[str, object]]:
    result = subprocess.run(
        ["node", "-e", NODE_UI_COLLECTOR],
        cwd=REPOSITORY_ROOT / "frontend",
        input=json.dumps(sources),
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    parsed = json.loads(result.stdout)
    assert isinstance(parsed, list)
    return parsed


def _assert_ui_contract(sources: Mapping[str, str]) -> None:
    assert set(sources) == set(UI_OWNER_PATHS), "UI owner corpus changed"
    cases = _collect_ui_cases(sources)
    disabled = [(case["owner"], case["id"]) for case in cases if case["disabled"]]
    assert disabled == [], f"UI markers cannot be owned by skipped/xfail tests: {disabled}"

    active = [(str(case["id"]), str(case["owner"])) for case in cases]
    counts = Counter(marker for marker, _owner in active)
    assert all(count == 1 for count in counts.values()), f"duplicate UI markers: {counts}"
    assert set(counts) == set(EXPECTED_UI_OWNERS), "missing/extra/substituted UI identity"
    assert dict(active) == EXPECTED_UI_OWNERS, "UI identity owner substitution"
    assert len(active) == len(EXPECTED_UI_OWNERS) == 26


def _edge_occurrences(plan_texts: Mapping[str, str]) -> dict[str, Counter[str]]:
    occurrences: dict[str, Counter[str]] = {}
    for owner, text in plan_texts.items():
        frontmatter = _frontmatter(text)
        must_haves = frontmatter.get("must_haves")
        assert isinstance(must_haves, dict)
        truths = must_haves.get("truths")
        assert isinstance(truths, list) and all(isinstance(truth, str) for truth in truths)
        occurrences[owner] = Counter(
            marker for truth in truths for marker in EDGE_MARKER_RE.findall(str(truth))
        )
    return occurrences


def _assert_edge_contract(occurrences: Mapping[str, Counter[str]]) -> None:
    assert set(occurrences) == set(EXPECTED_EDGE_OCCURRENCES)
    assert dict(occurrences) == EXPECTED_EDGE_OCCURRENCES
    canonical = set().union(*(set(items) for items in occurrences.values()))
    assert canonical == set(EXPECTED_EDGE_OWNERS)
    for edge, owner in EXPECTED_EDGE_OWNERS.items():
        ordered_sources = tuple(EXPECTED_EDGE_OCCURRENCES)
        first_source = next(source for source in ordered_sources if occurrences[source][edge])
        assert first_source == owner, f"canonical EDGE owner changed for {edge}"
        assert occurrences[owner][edge] == 1


def _prohibitions(plan_texts: Mapping[str, str]) -> list[str]:
    statements: list[str] = []
    for text in plan_texts.values():
        frontmatter = _frontmatter(text)
        must_haves = frontmatter.get("must_haves")
        assert isinstance(must_haves, dict)
        values = must_haves.get("prohibitions", [])
        assert isinstance(values, list)
        for value in values:
            assert isinstance(value, dict) and set(value) >= {"statement", "status", "verification"}
            assert value["status"] == "resolved"
            assert value["verification"] == "judgment"
            statement = value["statement"]
            assert isinstance(statement, str)
            statements.append(_normalize(statement))
    return statements


def _assert_prohibitions(statements: Sequence[str]) -> None:
    normalized = [_normalize(statement) for statement in statements]
    assert Counter(normalized) == Counter(EXPECTED_PROHIBITIONS)
    assert len(normalized) == len(set(normalized)) == 2


def _label_fingerprints(text: str, pattern: re.Pattern[str]) -> dict[str, str]:
    rows = pattern.findall(text)
    labels = [label for label, _value in rows]
    assert len(labels) == len(set(labels)), f"duplicate semantic label: {labels}"
    return {label: _fingerprint(value) for label, value in rows}


def _coverage_rows(text: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) >= 2 and cells[1] in {"INTEGRATE", "OPT-OUT"}:
            rows.append((cells[0].strip("`"), cells[1]))
    return rows


def _assert_coverage_contract(rows: Sequence[tuple[str, str]]) -> None:
    provider = importlib.import_module("test_provider_boundaries")
    expected = {
        **{name: "INTEGRATE" for name in provider.EXPECTED_INTEGRATED_CAPABILITIES},
        **{name: "OPT-OUT" for name in provider.EXPECTED_OPTED_OUT_CAPABILITIES},
    }
    names = [name for name, _decision in rows]
    assert len(rows) == len(set(names)) == 56
    assert dict(rows) == expected


def _real_ui_sources() -> dict[str, str]:
    return {owner: path.read_text(encoding="utf-8") for owner, path in UI_OWNER_PATHS.items()}


def _real_plan_sources() -> dict[str, str]:
    return {owner: path.read_text(encoding="utf-8") for owner, path in PLAN_PATHS.items()}


def test_phase_three_ui_considerations_have_exact_executable_ownership() -> None:
    """All 26 stable identities have one active test owner, not a category comment."""
    _assert_ui_contract(_real_ui_sources())


def test_ui_guard_rejects_missing_duplicate_extra_disabled_and_substituted_markers() -> None:
    """Equal counts cannot conceal marker or owner changes."""
    baseline = _real_ui_sources()
    owner = "BitbucketConnectionPage.test.tsx"
    source = baseline[owner]
    mutants: list[dict[str, str]] = []

    def mutate_owner(old: str, new: str) -> dict[str, str]:
        mutant = dict(baseline)
        assert old in source
        mutant[owner] = source.replace(old, new, 1)
        return mutant

    mutants.append(mutate_owner("UI3-C01", "marker-removed"))
    duplicate = dict(baseline)
    duplicate[owner] = source + '\nit("UI3-C01 duplicate", () => undefined);\n'
    mutants.append(duplicate)
    extra = dict(baseline)
    extra[owner] = source + '\nit("UI3-C27 extra", () => undefined);\n'
    mutants.append(extra)
    mutants.append(
        mutate_owner("UI3-C01", "marker-removed")
        | {owner: source.replace("UI3-C01", "marker-removed", 1) + "\n// UI3-C01 comment only\n"}
    )
    mutants.append(mutate_owner('it("UI3-C01', 'it.skip("UI3-C01'))
    mutants.append(mutate_owner('it("UI3-C01', 'it.fails("UI3-C01'))
    mutants.append(mutate_owner("UI3-C01", "UI3-C00"))
    mutants.append(mutate_owner("UI3-C01", "UI3-C02"))

    wrong_owner = "PublishedMappingImports.test.tsx"
    owner_substitution = mutate_owner("UI3-C01", "marker-removed")
    owner_substitution[wrong_owner] += '\nit("UI3-C01 wrong owner", () => undefined);\n'
    mutants.append(owner_substitution)

    for mutant in mutants:
        with pytest.raises(AssertionError):
            _assert_ui_contract(mutant)


def test_phase_three_edges_and_descriptorless_prohibitions_are_exact() -> None:
    """Six canonical edges retain nine reviewed occurrences and two exact statements."""
    sources = _real_plan_sources()
    _assert_edge_contract(_edge_occurrences(sources))
    _assert_prohibitions(_prohibitions(sources))


def test_edge_and_prohibition_guards_reject_missing_extra_duplicate_and_substitution() -> None:
    """Multiplicity and full statement text fail closed independently of set size."""
    edges = _edge_occurrences(_real_plan_sources())
    edge_mutants: list[dict[str, Counter[str]]] = []
    for change in ("missing", "extra", "duplicate", "substituted"):
        mutant = {owner: Counter(values) for owner, values in edges.items()}
        if change == "missing":
            mutant["03-07-PLAN.md"]["EDGE-BITB-05-empty"] -= 1
        elif change == "extra":
            mutant["03-08-PLAN.md"]["EDGE-BITB-06-empty"] += 1
        elif change == "duplicate":
            mutant["03-01-PLAN.md"]["EDGE-BITB-02-concurrency"] += 1
        else:
            mutant["03-07-PLAN.md"]["EDGE-BITB-05-empty"] -= 1
            mutant["03-07-PLAN.md"]["EDGE-BITB-05-idempotency"] += 1
        edge_mutants.append(mutant)
    for mutant in edge_mutants:
        with pytest.raises(AssertionError):
            _assert_edge_contract(mutant)

    first, second = EXPECTED_PROHIBITIONS
    prohibition_mutants = (
        [first],
        [first, second, "Unexpected prohibition."],
        [first, second, first],
        [first, second.replace("automatically", "silently")],
    )
    for mutant in prohibition_mutants:
        with pytest.raises(AssertionError):
            _assert_prohibitions(mutant)


def test_decisions_requirements_deferred_fences_and_api_coverage_are_exact() -> None:
    """All semantic sources reconcile once with exact meaning and disposition."""
    context = CONTEXT_PATH.read_text(encoding="utf-8")
    decisions = _label_fingerprints(
        context,
        re.compile(r"^- \*\*(D-\d{2}):\*\*\s*(.+)$", re.MULTILINE),
    )
    assert decisions == EXPECTED_DECISION_FINGERPRINTS

    requirements = _label_fingerprints(
        REQUIREMENTS_PATH.read_text(encoding="utf-8"),
        re.compile(
            r"^- \[[ x]\] \*\*(BITB-(?:02|05|06))\*\*:\s*(.+)$",
            re.MULTILINE,
        ),
    )
    assert requirements == EXPECTED_REQUIREMENT_FINGERPRINTS

    deferred = context.split("<deferred>", 1)[1].split("</deferred>", 1)[0]
    deferred_rows = re.findall(r"^- (.+)$", deferred, re.MULTILINE)
    assert len(deferred_rows) == 5
    assert {_fingerprint(row) for row in deferred_rows} == EXPECTED_DEFERRED_FINGERPRINTS

    _assert_coverage_contract(_coverage_rows(COVERAGE_PATH.read_text(encoding="utf-8")))


def test_semantic_and_coverage_guards_reject_equal_count_substitutions() -> None:
    """Fingerprint and disposition changes fail even when totals remain unchanged."""
    decision_mutant = dict(EXPECTED_DECISION_FINGERPRINTS)
    decision_mutant["D-01"] = _fingerprint("substituted decision")
    assert decision_mutant != EXPECTED_DECISION_FINGERPRINTS

    rows = _coverage_rows(COVERAGE_PATH.read_text(encoding="utf-8"))
    missing = rows[1:]
    duplicate = [*rows, rows[0]]
    substituted = [
        (name, "OPT-OUT" if decision == "INTEGRATE" else "INTEGRATE")
        if index == 0
        else (name, decision)
        for index, (name, decision) in enumerate(rows)
    ]
    for mutant in (missing, duplicate, substituted):
        with pytest.raises(AssertionError):
            _assert_coverage_contract(mutant)


def test_provider_and_background_guards_expose_non_vacuous_negative_controls() -> None:
    """Architecture guards must reject a synthetic provider write and route task call."""
    provider = importlib.import_module("test_provider_boundaries")
    background = importlib.import_module("test_background_boundaries")

    assert hasattr(provider, "_assert_phase3_provider_tree")
    assert hasattr(background, "_assert_no_worker_boundary_violations")
    with pytest.raises(AssertionError):
        provider._assert_phase3_provider_tree(  # type: ignore[attr-defined]
            """
class BitbucketHttpAdapter:
    async def write_source(self):
        return await self._client.stream("POST", "https://api.bitbucket.org/2.0/repositories/a/b/src")
"""
        )
    with pytest.raises(AssertionError):
        background._assert_no_worker_boundary_violations(  # type: ignore[attr-defined]
            {
                "route.py": (
                    "from verboflex.worker.import_tasks import run_import_job\n"
                    "run_import_job.delay()"
                )
            }
        )
