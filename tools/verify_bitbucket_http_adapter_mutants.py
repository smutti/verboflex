#!/usr/bin/env python3
"""Fail-closed targeted mutation proof for the Bitbucket read-only HTTP adapter."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"
COVERAGE_SOURCE = (
    REPOSITORY_ROOT / ".planning" / "phases" / "02-admin-configuration" / "COVERAGE.md"
)
TEST_SELECTION = (
    "tests/integration/test_bitbucket_http_adapter.py",
    "tests/architecture/test_provider_boundaries.py",
)


class MutationProofError(RuntimeError):
    """The checker could not establish one exact killed mutation."""


@dataclass(frozen=True, slots=True)
class Mutation:
    """One reviewed source transformation representing a plausible boundary defect."""

    label: str
    relative_path: str
    original: str
    replacement: str


MUTATIONS = (
    Mutation(
        "redirect-following-enabled",
        "src/verboflex/integrations/bitbucket/client.py",
        "follow_redirects=False",
        "follow_redirects=True",
    ),
    Mutation(
        "ambient-proxy-trust-enabled",
        "src/verboflex/integrations/bitbucket/client.py",
        "trust_env=False",
        "trust_env=True",
    ),
    Mutation(
        "automatic-retry-enabled",
        "src/verboflex/integrations/bitbucket/client.py",
        "httpx.AsyncHTTPTransport(retries=0)",
        "httpx.AsyncHTTPTransport(retries=1)",
    ),
    Mutation(
        "provider-read-changed-to-post",
        "src/verboflex/integrations/bitbucket/client.py",
        '                "GET",\n                validated_url,',
        '                "POST",\n                validated_url,',
    ),
    Mutation(
        "pre-request-generation-check-removed",
        "src/verboflex/integrations/bitbucket/client.py",
        "        try:\n"
        "            self._credential_leases.require_current_repository_read_lease("
        "session, lease)\n"
        "            async with self._client.stream(",
        "        try:\n            async with self._client.stream(",
    ),
    Mutation(
        "post-response-generation-check-removed",
        "src/verboflex/integrations/bitbucket/client.py",
        "                payload = await response.aread()\n"
        "            self._credential_leases.require_current_repository_read_lease("
        "session, lease)\n"
        "            decoded = json.loads(payload)",
        "                payload = await response.aread()\n"
        "            decoded = json.loads(payload)",
    ),
    Mutation(
        "effective-scope-comparison-inverted",
        "src/verboflex/integrations/bitbucket/client.py",
        'if response.headers.get("x-oauth-scopes") != REPOSITORY_SCOPE:',
        'if response.headers.get("x-oauth-scopes") == REPOSITORY_SCOPE:',
    ),
    Mutation(
        "endpoint-family-allowlist-broadened",
        "src/verboflex/integrations/bitbucket/urls.py",
        "or not any(pattern.fullmatch(parsed.path) for pattern in _ALLOWED_READ_PATHS)",
        'or not parsed.path.startswith("/2.0/")',
    ),
    Mutation(
        "explicit-port-accepted",
        "src/verboflex/integrations/bitbucket/urls.py",
        "or port is not None",
        "or False",
    ),
    Mutation(
        "lease-generation-comparison-inverted",
        "src/verboflex/services/bitbucket_oauth.py",
        "if connection.generation != lease.generation:",
        "if connection.generation == lease.generation:",
    ),
)


def replace_once(path: Path, original: str, replacement: str) -> None:
    """Apply one reviewed transformation or fail before invoking pytest."""
    source = path.read_text()
    occurrence_count = source.count(original)
    if occurrence_count != 1:
        raise MutationProofError(
            f"mutation subject drifted for {path}: expected 1 occurrence, found {occurrence_count}"
        )
    if original == replacement:
        raise MutationProofError("mutation replacement must change the subject")
    path.write_text(source.replace(original, replacement, 1))


def copy_workspace(destination: Path) -> Path:
    """Copy the backend and the reviewed capability manifest into an isolated workspace."""
    backend = destination / "backend"
    ignored = shutil.ignore_patterns(
        ".coverage",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "coverage-02-06.xml",
        "coverage.xml",
        "mutants",
    )
    shutil.copytree(BACKEND_ROOT, backend, ignore=ignored)
    coverage_target = (
        destination / ".planning" / "phases" / "02-admin-configuration" / "COVERAGE.md"
    )
    coverage_target.parent.mkdir(parents=True)
    shutil.copy2(COVERAGE_SOURCE, coverage_target)
    return backend


def run_suite(backend: Path) -> subprocess.CompletedProcess[str]:
    """Run the exact Task 2 command selection in one isolated workspace."""
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(backend / "src")
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *TEST_SELECTION, "-x"],
        cwd=backend,
        env=environment,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )


def prove_mutations() -> None:
    """Require a green baseline and one assertion failure per reviewed mutant."""
    with tempfile.TemporaryDirectory(prefix="verboflex-bitbucket-http-mutants-") as temp_dir:
        workspace = Path(temp_dir)
        baseline = run_suite(copy_workspace(workspace / "baseline"))
        if baseline.returncode != 0:
            raise MutationProofError(
                "mutation baseline failed:\n" + baseline.stdout + baseline.stderr
            )
        print("baseline: PASS")

        killed = 0
        for index, mutation in enumerate(MUTATIONS, start=1):
            mutant_backend = copy_workspace(workspace / f"mutant-{index}")
            replace_once(
                mutant_backend / mutation.relative_path,
                mutation.original,
                mutation.replacement,
            )
            result = run_suite(mutant_backend)
            combined_output = result.stdout + result.stderr
            if result.returncode == 0:
                raise MutationProofError(f"surviving mutant: {mutation.label}")
            if "failed" not in combined_output.casefold():
                raise MutationProofError(
                    f"mutant did not reach an assertion failure: {mutation.label}\n"
                    + combined_output
                )
            killed += 1
            print(f"{mutation.label}: KILLED")

        if killed != len(MUTATIONS):
            raise MutationProofError("mutation count mismatch")
        print(f"mutation score: {killed}/{len(MUTATIONS)} killed")


def self_test() -> None:
    """Prove source drift reaches the checker's own failure path."""
    with tempfile.TemporaryDirectory(prefix="verboflex-bitbucket-http-mutant-control-") as temp_dir:
        control = Path(temp_dir) / "control.py"
        control.write_text("approved = True\n")
        try:
            replace_once(control, "approved = False", "approved = True")
        except MutationProofError:
            print("mutation checker negative control: PASS")
            return
    raise MutationProofError("mutation checker negative control unexpectedly passed")


def main() -> None:
    """Run the negative control or the complete targeted mutation proof."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    arguments = parser.parse_args()
    if arguments.self_test:
        self_test()
    else:
        prove_mutations()


if __name__ == "__main__":
    try:
        main()
    except MutationProofError as error:
        print(f"Bitbucket HTTP mutation proof error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
