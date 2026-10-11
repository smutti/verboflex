#!/usr/bin/env python3
"""Fail-closed classifier for the two qualified Phase 5 RED suites."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_FILE = ROOT / "backend/tests/integration/test_review_workspace_schema.py"


@dataclass(frozen=True)
class PytestRedSuite:
    path: Path
    allowed_tests: frozenset[str]


SCHEMA_TESTS = frozenset(
    {
        "test_review_workspace_schema_invariant[review-tables-expected0]",
        "test_review_workspace_schema_invariant[proposal-key-language-expected1]",
        "test_review_workspace_schema_invariant[proposal-version-basis-state-expected2]",
        "test_review_workspace_schema_invariant[proposal-selector-ownership-expected3]",
        "test_review_workspace_schema_invariant[comment-key-language-expected4]",
        "test_review_workspace_schema_invariant[immutable-evidence-triggers-expected5]",
        "test_review_workspace_schema_invariant[notification-recipient-comment-kind-expected6]",
        "test_review_workspace_schema_invariant[deterministic-indexes-expected7]",
        "test_review_workspace_database_invariants",
        "test_review_workspace_migration_round_trip_preserves_prior_schema_and_data",
    }
)

SUITES = {
    "schema": {
        "pytest": PytestRedSuite(SCHEMA_FILE, SCHEMA_TESTS),
        "required_paths": (SCHEMA_FILE,),
    },
    "scalar-tracer": {
        "required_paths": (
            ROOT / "backend/tests/api/test_translation_reviews.py",
            ROOT / "frontend/src/features/translations/TranslationDetailPage.test.tsx",
        ),
        "pytest": PytestRedSuite(
            ROOT / "backend/tests/api/test_translation_reviews.py",
            frozenset(
                {
                    "test_scalar_proposal_save_preserves_imported_authority",
                    "test_scalar_proposal_save_rejects_viewer_and_foreign_authority",
                }
            ),
        ),
        "vitest": frozenset(
            {
                "renders published and pending scalar authorities separately",
                "keeps text browser-local until Save and discards it on Cancel",
                "hides proposal controls from a viewer",
            }
        ),
    },
}


class RedGateRejected(RuntimeError):
    pass


def _run(
    command: list[str],
    *,
    timeout: int = 120,
    cwd: Path = ROOT,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise RedGateRejected(f"timeout while running: {' '.join(command)}") from exc


def _require_paths(suite_name: str) -> None:
    missing = [
        str(path.relative_to(ROOT))
        for path in SUITES[suite_name]["required_paths"]
        if not path.is_file()
    ]
    if missing:
        raise RedGateRejected(
            f"suite {suite_name!r} is not yet created; missing paths: {', '.join(missing)}"
        )


def _collect_pytest(suite: PytestRedSuite) -> None:
    relative = str(suite.path.relative_to(ROOT))
    result = _run(
        [
            "uv",
            "run",
            "--project",
            "backend",
            "pytest",
            "-c",
            "backend/pyproject.toml",
            "--collect-only",
            "-q",
            relative,
        ]
    )
    if result.returncode != 0:
        raise RedGateRejected(
            f"pytest collection/configuration failed:\n{result.stdout}{result.stderr}"
        )
    collected = {
        line.rsplit("::", 1)[-1]
        for line in result.stdout.splitlines()
        if "::test_" in line
    }
    if not collected:
        raise RedGateRejected("pytest collection selected zero tests")
    if collected != suite.allowed_tests:
        raise RedGateRejected(
            "pytest collection did not match the closed manifest: "
            + json.dumps(
                {
                    "missing": sorted(suite.allowed_tests - collected),
                    "unexpected": sorted(collected - suite.allowed_tests),
                },
                sort_keys=True,
            )
        )


def _classify_pytest(
    suite: PytestRedSuite,
    *,
    failure_marker: str = "PHASE5_SCHEMA_MISSING[",
) -> dict[str, object]:
    relative = str(suite.path.relative_to(ROOT))
    with tempfile.TemporaryDirectory(prefix="verboflex-phase5-red-") as directory:
        report = Path(directory) / "pytest.xml"
        result = _run(
            [
                "uv",
                "run",
                "--project",
                "backend",
                "pytest",
                "-c",
                "backend/pyproject.toml",
                "-q",
                relative,
                f"--junitxml={report}",
            ]
        )
        if not report.is_file():
            raise RedGateRejected(
                f"pytest produced no machine-readable report:\n{result.stdout}{result.stderr}"
            )
        try:
            root = ET.parse(report).getroot()
        except ET.ParseError as exc:
            raise RedGateRejected(
                "pytest machine-readable report is malformed"
            ) from exc
    cases = root.findall(".//testcase")
    if not cases:
        raise RedGateRejected("pytest machine-readable report contains zero tests")
    observed: set[str] = set()
    failures: dict[str, str] = {}
    errors: dict[str, str] = {}
    skipped: set[str] = set()
    for case in cases:
        name = case.attrib.get("name", "")
        observed.add(name)
        failure = case.find("failure")
        error = case.find("error")
        if failure is not None:
            failures[name] = (
                failure.attrib.get("message", "") + "\n" + (failure.text or "")
            ).strip()
        if error is not None:
            errors[name] = (
                error.attrib.get("message", "") + "\n" + (error.text or "")
            ).strip()
        if case.find("skipped") is not None:
            skipped.add(name)
    if errors or skipped:
        raise RedGateRejected(
            "RED rejected due to infrastructure/error/skip outcome: "
            + json.dumps(
                {"errors": sorted(errors), "skipped": sorted(skipped)}, sort_keys=True
            )
        )
    if observed != suite.allowed_tests:
        raise RedGateRejected(
            "executed tests did not match the closed manifest: "
            + json.dumps(
                {
                    "missing": sorted(suite.allowed_tests - observed),
                    "unexpected": sorted(observed - suite.allowed_tests),
                },
                sort_keys=True,
            )
        )
    unexpected_passes = suite.allowed_tests - failures.keys()
    if unexpected_passes:
        raise RedGateRejected(
            f"RED rejected due to unexpected passes: {sorted(unexpected_passes)}"
        )
    bad_failures = {
        name: message
        for name, message in failures.items()
        if failure_marker not in message
    }
    if bad_failures:
        raise RedGateRejected(
            "RED rejected due to non-schema failures: "
            + json.dumps(
                {name: message[-500:] for name, message in bad_failures.items()},
                sort_keys=True,
            )
        )
    if result.returncode != 1:
        raise RedGateRejected(f"pytest RED must exit 1, found {result.returncode}")
    return {"collected": len(observed), "intended_failures": sorted(failures)}


def _schema_suite() -> dict[str, object]:
    suite = SUITES["schema"]["pytest"]
    assert isinstance(suite, PytestRedSuite)
    _collect_pytest(suite)
    return _classify_pytest(suite)


def _classify_vitest(allowed_tests: frozenset[str]) -> dict[str, object]:
    test_file = "src/features/translations/TranslationDetailPage.test.tsx"
    name_pattern = "|".join(sorted(allowed_tests))
    with tempfile.TemporaryDirectory(
        prefix="verboflex-phase5-red-vitest-"
    ) as directory:
        report = Path(directory) / "vitest.json"
        result = _run(
            [
                "npm",
                "test",
                "--",
                "--run",
                test_file,
                "--testNamePattern",
                name_pattern,
                "--reporter=json",
                f"--outputFile={report}",
            ],
            cwd=ROOT / "frontend",
        )
        if not report.is_file():
            raise RedGateRejected(
                "Vitest collection/configuration produced no report:\n"
                f"{result.stdout}{result.stderr}"
            )
        try:
            payload = json.loads(report.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise RedGateRejected(
                "Vitest machine-readable report is malformed"
            ) from exc

    assertions = [
        assertion
        for test_result in payload.get("testResults", [])
        for assertion in test_result.get("assertionResults", [])
    ]
    if not assertions:
        raise RedGateRejected(
            f"Vitest collection selected zero tests:\n{result.stdout}{result.stderr}"
        )
    selected = [
        assertion for assertion in assertions if assertion.get("status") != "skipped"
    ]
    observed = {str(assertion.get("title", "")) for assertion in selected}
    if observed != allowed_tests:
        raise RedGateRejected(
            "Vitest collection did not match the closed manifest: "
            + json.dumps(
                {
                    "missing": sorted(allowed_tests - observed),
                    "unexpected": sorted(observed - allowed_tests),
                },
                sort_keys=True,
            )
        )
    outcomes = {
        str(assertion.get("title", "")): str(assertion.get("status", ""))
        for assertion in selected
    }
    unexpected_passes = sorted(
        name for name, status in outcomes.items() if status == "passed"
    )
    non_failures = sorted(
        name for name, status in outcomes.items() if status != "failed"
    )
    if unexpected_passes:
        raise RedGateRejected(
            f"RED rejected due to unexpected passes: {unexpected_passes}"
        )
    if non_failures:
        raise RedGateRejected(
            "RED rejected due to infrastructure/error/skip outcome: "
            + json.dumps({"outcomes": outcomes}, sort_keys=True)
        )
    bad_failures = {}
    for assertion in selected:
        name = str(assertion.get("title", ""))
        messages = "\n".join(str(item) for item in assertion.get("failureMessages", []))
        if "PHASE5_SCALAR_MISSING[" not in messages:
            bad_failures[name] = messages[-500:]
    if bad_failures:
        raise RedGateRejected(
            "RED rejected due to non-scalar frontend failures: "
            + json.dumps(bad_failures, sort_keys=True)
        )
    if result.returncode != 1:
        raise RedGateRejected(f"Vitest RED must exit 1, found {result.returncode}")
    return {"collected": len(observed), "intended_failures": sorted(observed)}


def _scalar_suite() -> dict[str, object]:
    _require_paths("scalar-tracer")
    pytest_suite = SUITES["scalar-tracer"]["pytest"]
    vitest_suite = SUITES["scalar-tracer"]["vitest"]
    assert isinstance(pytest_suite, PytestRedSuite)
    assert isinstance(vitest_suite, frozenset)
    _collect_pytest(pytest_suite)
    backend = _classify_pytest(
        pytest_suite,
        failure_marker="PHASE5_SCALAR_MISSING[",
    )
    frontend = _classify_vitest(vitest_suite)
    return {"backend": backend, "frontend": frontend}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=sorted(SUITES), required=True)
    arguments = parser.parse_args()
    try:
        _require_paths(arguments.suite)
        result = _schema_suite() if arguments.suite == "schema" else _scalar_suite()
    except RedGateRejected as exc:
        print(
            json.dumps(
                {"qualified_red": False, "suite": arguments.suite, "error": str(exc)}
            )
        )
        return 2
    print(
        json.dumps(
            {"qualified_red": True, "suite": arguments.suite, **result}, sort_keys=True
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
