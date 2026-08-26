#!/usr/bin/env python3
"""Prove the reviewed post-limit rate mutant is killed by exact tests."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MUTATIONS = (
    (
        "local limiter",
        "allowed=current.attempts <= limit,",
        "allowed=current.attempts != limit + 1,",
    ),
    (
        "login limiter",
        "allowed=attempts <= LOGIN_LIMIT,",
        "allowed=attempts != LOGIN_LIMIT + 1,",
    ),
    (
        "sensitive-action limiter",
        "allowed=attempts <= limit,",
        "allowed=attempts != limit + 1,",
    ),
)

TEST_TARGETS = (
    "tests/auth/test_login.py::test_rate_limiter_uses_one_exact_atomic_redis_contract",
    "tests/auth/test_refresh.py::test_sensitive_action_limiter_hashes_authority_and_preserves_exact_window_state",
    "tests/api/test_rate_limits.py::test_local_limiter_accepts_exact_minima_and_reports_exact_window_state",
)

EXPECTED_FAILURES = {
    "tests/auth/test_login.py::test_rate_limiter_uses_one_exact_atomic_redis_contract[raw_state3-False-0-42]",
    "tests/auth/test_refresh.py::test_sensitive_action_limiter_hashes_authority_and_preserves_exact_window_state[32-False]",
    "tests/api/test_rate_limits.py::test_local_limiter_accepts_exact_minima_and_reports_exact_window_state",
}


class ProofError(RuntimeError):
    """The exact mutation proof drifted or failed for the wrong reason."""


def mutated_source(source: str) -> str:
    """Apply every exact reviewed mutation once, rejecting any scope drift."""
    result = source
    for label, original, mutant in MUTATIONS:
        if result.count(original) != 1:
            raise ProofError(f"{label} mutation subject drifted")
        if mutant in result:
            raise ProofError(f"{label} source already contains the divergent mutant")
        result = result.replace(original, mutant, 1)
    return result


def run_selected_tests(backend_root: Path) -> subprocess.CompletedProcess[str]:
    """Run only the exact behavioural tests attributed to this manual mutant."""
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(backend_root / "src")
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *TEST_TARGETS],
        cwd=backend_root,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


def failure_nodes(output: str) -> set[str]:
    """Extract pytest's terminal failure nodes without accepting other errors."""
    nodes: set[str] = set()
    for line in output.splitlines():
        if not line.startswith("FAILED "):
            continue
        nodes.add(line.removeprefix("FAILED ").split(" - ", maxsplit=1)[0])
    return nodes


def prove_mutant_killed(backend_root: Path) -> None:
    """Require baseline success and the three exact mutant failures."""
    source_path = backend_root / "src/verboflex/auth/rate_limits.py"
    tests_path = backend_root / "tests"
    pyproject_path = backend_root / "pyproject.toml"
    if not source_path.is_file() or not tests_path.is_dir() or not pyproject_path.is_file():
        raise ProofError("backend mutation proof inputs are incomplete")

    with tempfile.TemporaryDirectory(prefix="verboflex-rate-mutant-") as temporary:
        workspace = Path(temporary) / "backend"
        shutil.copytree(backend_root / "src", workspace / "src")
        shutil.copytree(tests_path, workspace / "tests")
        shutil.copy2(pyproject_path, workspace / "pyproject.toml")

        baseline = run_selected_tests(workspace)
        if baseline.returncode != 0 or "8 passed" not in baseline.stdout:
            raise ProofError("rate limit boundary baseline did not pass exactly")

        workspace_source = workspace / "src/verboflex/auth/rate_limits.py"
        workspace_source.write_text(
            mutated_source(workspace_source.read_text(encoding="utf-8")),
            encoding="utf-8",
        )
        mutant = run_selected_tests(workspace)
        combined_output = mutant.stdout + mutant.stderr
        if mutant.returncode != 1:
            raise ProofError("reviewed rate limit mutant did not fail as expected")
        if failure_nodes(combined_output) != EXPECTED_FAILURES:
            raise ProofError("reviewed rate limit mutant failed outside the exact attribution")
        if "3 failed, 5 passed" not in combined_output:
            raise ProofError("reviewed rate limit mutant result counts drifted")


def self_test(backend_root: Path) -> None:
    """Exercise the real proof plus missing and broadened-scope controls."""
    source = (backend_root / "src/verboflex/auth/rate_limits.py").read_text(encoding="utf-8")
    mutated_source(source)
    for drifted in (
        source.replace(MUTATIONS[0][1], "allowed=current.attempts < limit,", 1),
        source + f"\n{MUTATIONS[0][1]}\n",
    ):
        try:
            mutated_source(drifted)
        except ProofError:
            continue
        raise ProofError("rate limit mutation scope negative control unexpectedly passed")
    prove_mutant_killed(backend_root)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend-root", type=Path, required=True)
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.self_test:
            self_test(args.backend_root)
            print("rate limit boundary mutant controls: PASS")
        else:
            prove_mutant_killed(args.backend_root)
            print("rate limit boundary mutant proof: PASS")
    except (OSError, ProofError) as error:
        print(f"rate limit boundary mutant proof error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
