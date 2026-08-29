"""Deterministic Phase 2 multi-source semantic closure audit."""

from __future__ import annotations


EXPECTED_KEYS = {
    "goal": {"GOAL"},
    "requirements": {
        "AUTH-02", "AUTH-03", "PROD-01", "PROD-02", "PROD-03",
        "PROD-04", "PROD-05", "PROD-06", "PROD-07", "PROD-08",
        "PROD-09", "BITB-01", "BITB-03", "BITB-04", "UI-03",
    },
    "decisions": {f"D-{number:02d}" for number in range(1, 24)},
    "assumptions": {"A-01", "A-02", "A-03"},
    "edges": {
        f"R{requirement}-{category}"
        for requirement, categories in {
            1: ("adjacency", "empty", "ordering", "idempotency", "concurrency"),
            2: ("adjacency", "empty", "encoding", "ordering", "idempotency", "concurrency"),
            3: ("idempotency", "concurrency"),
            4: ("empty", "encoding", "idempotency", "concurrency"),
            5: ("idempotency", "concurrency"),
            6: ("adjacency", "empty", "encoding", "ordering", "idempotency", "concurrency"),
            7: ("adjacency", "empty", "encoding", "ordering", "idempotency", "concurrency"),
            8: ("adjacency", "empty", "ordering", "idempotency", "concurrency"),
            9: ("adjacency", "empty", "encoding", "ordering", "idempotency", "concurrency"),
            10: ("adjacency", "empty", "ordering", "idempotency", "concurrency"),
            11: ("adjacency", "empty", "ordering", "idempotency", "concurrency"),
            12: ("idempotency", "concurrency"),
        }.items()
        for category in categories
    },
    "prohibitions": {f"P-{number:02d}" for number in range(1, 10)},
    "ui": {"empty", "loading", "error", "populated", "partial", "overflow", "zero-one-many", "long-text"},
    "capabilities": set(),
    "review": {*(f"CR-{number:02d}" for number in range(1, 11)), "WR-01", "WR-02"},
    "verifier": {f"G{number}" for number in range(1, 7)},
}


def _multi_source_inventory() -> dict[str, dict[str, object]]:
    raise AssertionError("multi-source semantic registry is not implemented")


def test_phase2_multi_source_coverage_contract() -> None:
    """Every canonical item retains meaning and reaches executable evidence."""
    inventory = _multi_source_inventory()
    assert inventory.keys() == EXPECTED_KEYS.keys()
    for source, expected in EXPECTED_KEYS.items():
        assert inventory[source].keys() == expected
