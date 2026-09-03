"""Fail-closed contract for the supplemental Phase 3 live-read smoke mode."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SMOKE_HARNESS = REPOSITORY_ROOT / "tools" / "phase3_smoke.sh"
LIVE_VARIABLES = (
    "VERBOFLEX_BITBUCKET_OAUTH_CLIENT_ID",
    "VERBOFLEX_BITBUCKET_OAUTH_CLIENT_SECRET",
    "VERBOFLEX_BITBUCKET_LIVE_WORKSPACE",
    "VERBOFLEX_BITBUCKET_LIVE_REPOSITORY",
)


def _without_live_configuration() -> dict[str, str]:
    return {key: value for key, value in os.environ.items() if key not in LIVE_VARIABLES}


def test_live_mode_self_test_is_secret_free_and_passes() -> None:
    sentinel = "phase3-self-test-secret-must-never-appear"
    environment = _without_live_configuration()
    environment["VERBOFLEX_BITBUCKET_OAUTH_CLIENT_SECRET"] = sentinel

    result = subprocess.run(
        [os.fspath(SMOKE_HARNESS), "--self-test-live-mode"],
        cwd=REPOSITORY_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    diagnostics = result.stdout + result.stderr
    assert result.returncode == 0, diagnostics
    assert result.stdout == "phase3 live provider self-test: PASS\n"
    assert sentinel not in diagnostics


def test_unconfigured_live_mode_is_an_explicit_successful_supplemental_skip() -> None:
    result = subprocess.run(
        [
            os.fspath(SMOKE_HARNESS),
            "--live-provider-read-only",
            "--skip-if-unconfigured",
        ],
        cwd=REPOSITORY_ROOT,
        env=_without_live_configuration(),
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == (
        "phase3 live provider: SKIP "
        "(supplemental variables are not configured)\n"
    )
    assert result.stderr == ""


def test_live_mode_contract_is_bounded_get_only_and_trap_cleaned() -> None:
    source = SMOKE_HARNESS.read_text(encoding="utf-8")

    required_fragments = (
        "run_live_provider_read_only()",
        "self_test_live_mode()",
        "verify_live_provider_audit()",
        'trap cleanup EXIT INT TERM',
        'chmod 600 "$SMOKE_ENV_FILE"',
        'resource_mutations=0',
        'all(row["method"] == "GET" for row in resources)',
        'hashlib.sha256',
        'final_local_revoke=PASS',
    )
    assert all(fragment in source for fragment in required_fragments)

    live_section = source.split("run_live_provider_read_only()", 1)[1].split(
        "\nself_test_live_mode()",
        1,
    )[0]
    assert "docker compose" not in live_section
    assert "curl" not in live_section
    assert "api.bitbucket.org" not in live_section
    assert "bitbucket.org/site/oauth2/access_token" not in live_section
    assert "VERBOFLEX_BITBUCKET_OAUTH_CLIENT_SECRET" not in live_section
    assert "set -x" not in source
    assert "eval " not in source
