"""Literal semantic traceability for every Phase 2 SPEC edge row."""

from __future__ import annotations

import copy
import json
import re
import subprocess
import sys
from collections import Counter
from functools import cache
from pathlib import Path
from typing import Any

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
PHASE_DIR = REPOSITORY_ROOT / ".planning" / "phases" / "02-admin-configuration"
SPEC_PATH = PHASE_DIR / "02-SPEC.md"
PLAN_PATH = PHASE_DIR / "02-30-PLAN.md"
MATRIX_PATH = Path(__file__).with_name("phase2_spec_edge_matrix.json")

MATRIX_FIELDS = {
    "edge_id",
    "category",
    "requirement",
    "source_status",
    "source_resolution_or_reason",
    "phase_disposition",
    "must_have",
    "test_nodes",
}
SOURCE_UNRESOLVED = {
    "R4-encoding": "resolved-A-01",
    "R9-encoding": "resolved-A-02",
}
DISMISSED_EDGE_IDS = {
    "R7-ordering",
    "R8-ordering",
    "R8-concurrency",
    "R10-ordering",
    "R11-adjacency",
}
RESOLVED_PLAN_TEXT = {
    "R4-encoding": (
        "NFKC, whitespace collapse, casefold, and persisted global name_key "
        "uniqueness define product-name equality."
    ),
    "R9-encoding": (
        "Preview uses the approved strict encoding matrix and exact JSON "
        "string-leaf/file-shape contract; unsupported forms fail closed."
    ),
}


def _normalize(value: str) -> str:
    """Normalize only Markdown/status spelling and insignificant whitespace."""
    value = value.replace("✅", "").replace("⚠", "").replace("⛔", "")
    return " ".join(value.split())


def _source_status(value: str) -> str:
    normalized = _normalize(value)
    if normalized.casefold() == "covered":
        return "covered"
    if normalized.casefold() == "dismissed":
        return "dismissed"
    if normalized.upper() == "UNRESOLVED":
        return "UNRESOLVED"
    raise AssertionError(f"unknown SPEC edge status: {value!r}")


def _markdown_rows(text: str, *, start: str, end: str) -> list[list[str]]:
    section = text.split(start, 1)[1].split(end, 1)[0]
    rows: list[list[str]] = []
    for line in section.splitlines():
        if not line.startswith("|"):
            continue
        cells = [_normalize(cell) for cell in line.strip("|").split("|")]
        if cells and cells[0] not in {"Category", "----------"}:
            rows.append(cells)
    return rows


def _spec_edges() -> list[dict[str, str]]:
    rows = _markdown_rows(
        SPEC_PATH.read_text(encoding="utf-8"),
        start="## Edge Coverage",
        end="## Prohibitions (must-NOT)",
    )
    assert all(len(row) == 4 for row in rows), "malformed SPEC edge table"
    return [
        {
            "edge_id": f"{requirement}-{category}",
            "category": category,
            "requirement": requirement,
            "source_status": _source_status(status),
            "source_resolution_or_reason": reason,
        }
        for category, requirement, status, reason in rows
    ]


def _load_matrix() -> list[dict[str, Any]]:
    assert MATRIX_PATH.is_file(), "literal 54-row edge matrix registry is missing"
    payload = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, list), "edge matrix must be a JSON array"
    assert all(isinstance(row, dict) for row in payload)
    return payload


def _keyed(rows: list[dict[str, Any]], *, label: str) -> dict[str, dict[str, Any]]:
    edge_ids = [str(row.get("edge_id", "")) for row in rows]
    duplicates = sorted(edge_id for edge_id, count in Counter(edge_ids).items() if count != 1)
    assert not duplicates, f"{label} has missing/duplicate semantic keys: {duplicates}"
    return {edge_id: row for edge_id, row in zip(edge_ids, rows, strict=True)}


def _assert_source_matrix_equal(matrix: list[dict[str, Any]]) -> None:
    assert all(set(row) == MATRIX_FIELDS for row in matrix), "matrix schema drifted"
    source = _keyed(_spec_edges(), label="SPEC")
    actual = _keyed(matrix, label="matrix")
    assert actual.keys() == source.keys(), "matrix omitted or renamed a SPEC edge"
    for edge_id, expected in source.items():
        row = actual[edge_id]
        projected = {field: row[field] for field in expected}
        assert projected == expected, f"semantic source drift for {edge_id}"
        assert row["must_have"] == f"EDGE-{edge_id}"
        assert isinstance(row["test_nodes"], list) and row["test_nodes"]
        assert all(isinstance(node, str) and "::" in node for node in row["test_nodes"])

        if expected["source_status"] == "UNRESOLVED":
            assert row["phase_disposition"] == SOURCE_UNRESOLVED[edge_id]
        elif expected["source_status"] == "dismissed":
            assert row["phase_disposition"] == "dismissed"
        else:
            assert row["phase_disposition"] == "tested"


def _plan_edge_truths() -> dict[str, dict[str, str]]:
    pattern = re.compile(
        r'^\s*- "\[EDGE-(?P<edge_id>R\d+-(?:adjacency|empty|encoding|ordering|idempotency|concurrency))'
        r" source=(?P<source>covered|dismissed|UNRESOLVED)"
        r'(?: disposition=(?P<disposition>[^\]]+))?\](?P<text>.*)"$'
    )
    truths: list[dict[str, str]] = []
    for line in PLAN_PATH.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if match:
            truths.append({key: _normalize(value or "") for key, value in match.groupdict().items()})
    return _keyed(truths, label="PLAN must-have")


def _assert_plan_links(matrix: list[dict[str, Any]]) -> None:
    truths = _plan_edge_truths()
    matrix_by_id = _keyed(matrix, label="matrix")
    assert truths.keys() == matrix_by_id.keys(), "PLAN EDGE must-haves are not one-to-one"
    for edge_id, row in matrix_by_id.items():
        truth = truths[edge_id]
        assert truth["source"] == row["source_status"]
        if row["source_status"] == "UNRESOLVED":
            assert truth["disposition"] == row["phase_disposition"]
            assert truth["text"] == RESOLVED_PLAN_TEXT[edge_id]
        elif row["source_status"] == "dismissed":
            assert truth["disposition"] == ""
            assert truth["text"] == row["source_resolution_or_reason"]
        else:
            assert truth["disposition"] == ""
            assert truth["text"], f"covered edge {edge_id} has no semantic must-have"


def _split_node(node: str) -> tuple[Path, str]:
    path_text, title = node.split("::", 1)
    path = REPOSITORY_ROOT / path_text
    assert path.is_file(), f"named test path does not exist: {path_text}"
    return path, title


@cache
def _collected_backend_nodes(nodes: tuple[str, ...]) -> set[str]:
    relative_nodes = [node.removeprefix("backend/") for node in nodes]
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", *relative_nodes],
        cwd=REPOSITORY_ROOT / "backend",
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return {
        f"backend/{line.strip()}"
        for line in result.stdout.splitlines()
        if "::" in line and not line.startswith("=")
    }


@cache
def _listed_frontend_nodes(files: tuple[str, ...]) -> set[str]:
    relative_files = [path.removeprefix("frontend/") for path in files]
    result = subprocess.run(
        ["npx", "vitest", "list", *relative_files],
        cwd=REPOSITORY_ROOT / "frontend",
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    listed: set[str] = set()
    for line in result.stdout.splitlines():
        if " > " not in line:
            continue
        path, _, title = line.partition(" > ")
        listed.add(f"frontend/{path}::{title.rsplit(' > ', 1)[-1]}")
    return listed


def _assert_nodes_collect(matrix: list[dict[str, Any]]) -> None:
    nodes = sorted({node for row in matrix for node in row["test_nodes"]})
    backend_nodes = tuple(node for node in nodes if node.startswith("backend/") and ".py::" in node)
    frontend_nodes = tuple(node for node in nodes if node.startswith("frontend/"))
    assert len(backend_nodes) + len(frontend_nodes) == len(nodes), "unsupported test-node syntax"

    for node in nodes:
        _split_node(node)
    assert _collected_backend_nodes(backend_nodes) == set(backend_nodes)
    frontend_files = tuple(sorted({node.split("::", 1)[0] for node in frontend_nodes}))
    assert set(frontend_nodes).issubset(_listed_frontend_nodes(frontend_files))


def test_phase2_literal_spec_edge_contract() -> None:
    """All 54 literal edge semantics reach one must-have and collectable test."""
    matrix = _load_matrix()
    _assert_source_matrix_equal(matrix)
    _assert_plan_links(matrix)
    _assert_nodes_collect(matrix)

    assert set(SOURCE_UNRESOLVED) == {
        row["edge_id"] for row in matrix if row["source_status"] == "UNRESOLVED"
    }
    assert DISMISSED_EDGE_IDS == {
        row["edge_id"] for row in matrix if row["source_status"] == "dismissed"
    }


def test_edge_contract_rejects_count_preserving_semantic_mutations() -> None:
    """Counts and labels cannot conceal renamed meaning, status, or duplicate keys."""
    matrix = _load_matrix()
    mutations: list[list[dict[str, Any]]] = []
    for field, replacement in (
        ("source_resolution_or_reason", "semantically substituted reason"),
        ("source_status", "covered"),
        ("category", "ordering"),
        ("requirement", "R12"),
    ):
        mutant = copy.deepcopy(matrix)
        target = next(row for row in mutant if row["edge_id"] == "R4-encoding")
        target[field] = replacement
        mutations.append(mutant)
    duplicate = copy.deepcopy(matrix)
    duplicate[-1]["edge_id"] = duplicate[0]["edge_id"]
    mutations.append(duplicate)

    for mutant in mutations:
        with pytest.raises(AssertionError):
            _assert_source_matrix_equal(mutant)
