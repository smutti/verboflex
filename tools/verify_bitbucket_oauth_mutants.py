#!/usr/bin/env python3
"""Fail-closed targeted mutation proof for Bitbucket OAuth secret authority."""

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
TEST_SELECTION = (
    "tests/integration/test_bitbucket_oauth.py",
    "tests/api/test_admin_bitbucket.py",
    "tests/api/test_openapi_contract.py::test_openapi_surface_is_exact_and_security_is_not_accidental",
    "tests/api/test_openapi_contract.py::test_admin_bitbucket_openapi_is_closed_bounded_and_secret_free",
)


class MutationProofError(RuntimeError):
    """The checker could not establish an exact killed mutant."""


@dataclass(frozen=True, slots=True)
class Mutation:
    """One reviewed source transformation representing a plausible defect."""

    label: str
    relative_path: str
    original: str
    replacement: str


MUTATIONS = (
    Mutation(
        "partial-client-credentials-settings-accepted",
        "src/verboflex/services/bitbucket_oauth.py",
        "if client_id is None or client_secret is None:",
        "if client_id is None and client_secret is None:",
    ),
    Mutation(
        "generation-comparison-inverted",
        "src/verboflex/services/bitbucket_oauth.py",
        "if connection.generation != lease.generation:",
        "if connection.generation == lease.generation:",
    ),
    Mutation(
        "repository-scope-comparison-inverted",
        "src/verboflex/services/bitbucket_oauth.py",
        "or scope != REPOSITORY_SCOPE",
        "or scope == REPOSITORY_SCOPE",
    ),
    Mutation(
        "access-token-persisted-in-plaintext",
        "src/verboflex/services/bitbucket_oauth.py",
        "connection.access_token_ciphertext = self._secret_box.encrypt(access_token)",
        "connection.access_token_ciphertext = access_token",
    ),
    Mutation(
        "token-renewal-boundary-inverted",
        "src/verboflex/services/bitbucket_oauth.py",
        "if connection.provider_expires_at > renewed_at + timedelta(",
        "if connection.provider_expires_at < renewed_at + timedelta(",
    ),
    Mutation(
        "admin-guard-to-viewer",
        "src/verboflex/api/v1/routes/admin_bitbucket.py",
        "AdminPrincipal = Annotated[Principal, Depends(require_roles(RoleName.ADMIN))]",
        "AdminPrincipal = Annotated[Principal, Depends(require_roles(RoleName.VIEWER))]",
    ),
    Mutation(
        "configured-service-guard-inverted",
        "src/verboflex/api/v1/routes/admin_bitbucket.py",
        "def _configured(service: BitbucketOAuthService | None) -> BitbucketOAuthService:\n"
        "    if service is None:\n"
        "        raise _unavailable()",
        "def _configured(service: BitbucketOAuthService | None) -> BitbucketOAuthService:\n"
        "    if service is not None:\n"
        "        raise _unavailable()",
    ),
    Mutation(
        "client-credentials-grant-changed",
        "src/verboflex/services/bitbucket_oauth.py",
        'data=urlencode({"grant_type": "client_credentials"}).encode("ascii"),',
        'data=urlencode({"grant_type": "password"}).encode("ascii"),',
    ),
    Mutation(
        "connection-status-becomes-cacheable",
        "src/verboflex/api/v1/routes/admin_bitbucket.py",
        'NO_STORE_HEADERS = {"Cache-Control": "no-store"}',
        'NO_STORE_HEADERS = {"Cache-Control": "public"}',
    ),
    Mutation(
        "local-revoke-skipped",
        "src/verboflex/api/v1/routes/admin_bitbucket.py",
        "configured.revoke_current(session, actor_id=principal.user_id)",
        "configured.public_status(session)",
    ),
    Mutation(
        "status-response-allows-extra-fields",
        "src/verboflex/schemas/admin_bitbucket.py",
        "class AdminBitbucketStatusResponse(BaseModel):\n"
        '    """Bounded connection state safe for browser projection."""\n\n'
        '    model_config = ConfigDict(extra="forbid")',
        "class AdminBitbucketStatusResponse(BaseModel):\n"
        '    """Bounded connection state safe for browser projection."""\n\n'
        '    model_config = ConfigDict(extra="ignore")',
    ),
)


def replace_once(path: Path, original: str, replacement: str) -> None:
    """Apply exactly one reviewed transformation or fail before testing."""
    source = path.read_text()
    occurrence_count = source.count(original)
    if occurrence_count != 1:
        raise MutationProofError(
            f"mutation subject drifted for {path}: expected 1 occurrence, found {occurrence_count}"
        )
    if original == replacement:
        raise MutationProofError("mutation replacement must change the subject")
    path.write_text(source.replace(original, replacement, 1))


def copy_backend(destination: Path) -> Path:
    """Copy the backend without virtualenvs, caches, or stale reports."""
    target = destination / "backend"
    ignored = shutil.ignore_patterns(
        ".coverage",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "coverage.xml",
        "coverage-02-05.xml",
        "mutants",
    )
    shutil.copytree(BACKEND_ROOT, target, ignore=ignored)
    frontend_target = destination / "frontend"
    frontend_target.mkdir()
    shutil.copy2(REPOSITORY_ROOT / "frontend/openapi.json", frontend_target)
    return target


def run_suite(backend: Path) -> subprocess.CompletedProcess[str]:
    """Run the exact OAuth integration contract against one isolated copy."""
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(backend / "src")
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *TEST_SELECTION, "-x"],
        cwd=backend,
        env=environment,
        text=True,
        capture_output=True,
        timeout=90,
        check=False,
    )


def prove_mutations() -> None:
    """Require a green baseline and one assertion failure per mutation."""
    with tempfile.TemporaryDirectory(prefix="verboflex-oauth-mutants-") as temp_dir:
        workspace = Path(temp_dir)
        baseline = run_suite(copy_backend(workspace / "baseline"))
        if baseline.returncode != 0:
            raise MutationProofError(
                "mutation baseline failed:\n" + baseline.stdout + baseline.stderr
            )
        print("baseline: PASS")

        killed = 0
        for index, mutation in enumerate(MUTATIONS, start=1):
            mutant_backend = copy_backend(workspace / f"mutant-{index}")
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
    """Prove source drift reaches the checker's failure path."""
    with tempfile.TemporaryDirectory(prefix="verboflex-oauth-mutant-control-") as temp_dir:
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
        print(f"OAuth mutation proof error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
