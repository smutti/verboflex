"""Fail-closed contract for the disposable Phase 2 live provider smoke."""

from __future__ import annotations

import importlib.util
import json
import os
import secrets
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
import yaml
from cryptography.fernet import Fernet

from verboflex.core.config import Settings
from verboflex.services.bitbucket_oauth import BitbucketOAuthService

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
LIVE_SMOKE_HELPER = REPOSITORY_ROOT / "tools" / "phase2_live_provider.py"
BASE_COMPOSE = REPOSITORY_ROOT / "docker-compose.yml"
STAGING_COMPOSE = REPOSITORY_ROOT / "docker-compose.staging.yml"
PRODUCTION_COMPOSE = REPOSITORY_ROOT / "docker-compose.prod.yml"
SMOKE_HARNESS = REPOSITORY_ROOT / "tools" / "phase2_smoke.sh"
GAUNTLET_HARNESS = REPOSITORY_ROOT / "tools" / "phase2_gauntlet.sh"
MOCK_PROVIDER = REPOSITORY_ROOT / "tools" / "phase2_mock_provider.py"
COVERAGE_PATH = REPOSITORY_ROOT / ".planning" / "phases" / "02-admin-configuration" / "COVERAGE.md"
EXACT_PROVIDER_SETTINGS = {
    "VERBOFLEX_BITBUCKET_OAUTH_CLIENT_ID",
    "VERBOFLEX_BITBUCKET_OAUTH_CLIENT_SECRET",
    "VERBOFLEX_BITBUCKET_TOKEN_ENCRYPTION_KEYRING",
}
EXACT_DEPLOYMENT_SETTINGS = {
    "VERBOFLEX_APP_ENV",
    "VERBOFLEX_DATABASE_URL",
    "VERBOFLEX_REDIS_URL",
    "VERBOFLEX_BITBUCKET_OAUTH_CLIENT_ID",
    "VERBOFLEX_BITBUCKET_OAUTH_CLIENT_SECRET",
    "VERBOFLEX_BITBUCKET_TOKEN_ENCRYPTION_KEYRING",
    "VERBOFLEX_PREVIEW_SOFT_TIME_LIMIT_SECONDS",
    "VERBOFLEX_PREVIEW_HARD_TIME_LIMIT_SECONDS",
    "VERBOFLEX_PREVIEW_WATCHDOG_GRACE_SECONDS",
    "VERBOFLEX_PREVIEW_WATCHDOG_INTERVAL_SECONDS",
}
PRE_REWRITE_DECISIONS = {
    "oauth-authorization-code-start": "INTEGRATE",
    "oauth-authorization-code-exchange": "INTEGRATE",
    "oauth-refresh-token-exchange-and-rotation": "INTEGRATE",
    "oauth-effective-scope-inspection": "INTEGRATE",
    "repository-metadata-by-workspace-and-slug": "INTEGRATE",
    "branch-listing-with-provider-pagination": "INTEGRATE",
    "branch-to-commit-resolution": "INTEGRATE",
    "source-tree-directory-pagination": "INTEGRATE",
    "raw-source-file-read-at-commit": "INTEGRATE",
    "provider-next-url-validation": "INTEGRATE",
    "oauth-provider-side-token-revocation": "OPT-OUT",
    "repository-listing-and-search": "OPT-OUT",
    "account-profile-and-email": "OPT-OUT",
    "workspace-membership-and-permissions": "OPT-OUT",
    "project-listing-and-metadata": "OPT-OUT",
    "workspace-and-project-administration": "OPT-OUT",
    "tag-listing-and-other-ref-discovery": "OPT-OUT",
    "commit-history-listing-and-search": "OPT-OUT",
    "commit-diff-diffstat-and-patch-read": "OPT-OUT",
    "commit-status-read-and-write": "OPT-OUT",
    "source-file-create-update-delete": "OPT-OUT",
    "branch-create-update-delete": "OPT-OUT",
    "tag-create-update-delete": "OPT-OUT",
    "commit-create": "OPT-OUT",
    "pull-request-list-and-read": "OPT-OUT",
    "pull-request-create-and-update": "OPT-OUT",
    "pull-request-merge-decline-and-approve": "OPT-OUT",
    "pull-request-comments-tasks-and-activity": "OPT-OUT",
    "pull-request-diff-and-diffstat": "OPT-OUT",
    "repository-webhook-list-and-read": "OPT-OUT",
    "repository-webhook-create-update-delete": "OPT-OUT",
    "repository-settings-and-permissions-admin": "OPT-OUT",
    "branch-restrictions-and-merge-checks-admin": "OPT-OUT",
    "deploy-keys-access-keys-and-ssh-keys-admin": "OPT-OUT",
    "pipelines-list-and-read": "OPT-OUT",
    "pipelines-run-stop-and-manage": "OPT-OUT",
    "deployments-and-environments": "OPT-OUT",
    "issues-list-and-read": "OPT-OUT",
    "issues-create-update-delete-and-comments": "OPT-OUT",
    "downloads-list-and-read": "OPT-OUT",
    "downloads-upload-and-delete": "OPT-OUT",
    "wiki-read-and-write": "OPT-OUT",
    "snippets-read-and-write": "OPT-OUT",
    "code-search": "OPT-OUT",
}
DECLARED_CREDENTIAL_REWRITE = {
    "oauth-authorization-code-start": "oauth-client-credentials-acquisition",
    "oauth-authorization-code-exchange": "oauth-client-credentials-reacquisition",
    "oauth-refresh-token-exchange-and-rotation": (
        "oauth-authorization-code-callback-and-refresh-token-flows"
    ),
}
IDENTITY_REWRITE = {
    key: key for key in PRE_REWRITE_DECISIONS if key not in DECLARED_CREDENTIAL_REWRITE
}


def _load_live_smoke() -> ModuleType:
    assert LIVE_SMOKE_HELPER.is_file(), "live provider helper is not implemented"
    specification = importlib.util.spec_from_file_location(
        "phase2_live_provider",
        LIVE_SMOKE_HELPER,
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def _write_live_env(path: Path, **overrides: str) -> None:
    values = {
        "VERBOFLEX_LIVE_PROVIDER_OPT_IN": "production-api-read-only-confirmed",
        "VERBOFLEX_BASE_URL": "http://localhost:8123",
        "VERBOFLEX_ADMIN_EMAIL": "provider-admin@example.com",
        "VERBOFLEX_ADMIN_PASSWORD": "local-admin-password-one",
        "VERBOFLEX_ADMIN_NEW_PASSWORD": "local-admin-password-two",
        "BITBUCKET_WORKSPACE": "acme",
        "BITBUCKET_REPOSITORY_SLUG": "translations",
        "BITBUCKET_BRANCH": "main",
    }
    values.update(overrides)
    path.write_text("".join(f'{key}="{value}"\n' for key, value in values.items()))
    path.chmod(0o600)


def _coverage_rows() -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for line in COVERAGE_PATH.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) == 3 and cells[1] in {"INTEGRATE", "OPT-OUT"}:
            rows.append((cells[0].strip("`"), cells[1], cells[2]))
    return rows


class _UnusedTokenExchange:
    def exchange_client_credentials(
        self,
        *,
        client_id: str,
        client_secret: str,
    ) -> dict[str, object]:
        raise AssertionError("provider contact is not allowed during readiness validation")


def test_base_compose_inherits_exact_provider_settings_without_secret_output(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Base Compose makes API and worker provider-ready without rendering secrets."""
    sentinels = {
        "VERBOFLEX_BITBUCKET_OAUTH_CLIENT_ID": "seed-client-id-02-35",
        "VERBOFLEX_BITBUCKET_OAUTH_CLIENT_SECRET": "seed-client-secret-02-35",
        "VERBOFLEX_BITBUCKET_TOKEN_ENCRYPTION_KEYRING": Fernet.generate_key().decode(),
    }
    environment_file = tmp_path / "owner-only.env"
    environment_file.write_text(
        "".join(f"{key}={value}\n" for key, value in sentinels.items()),
        encoding="utf-8",
    )
    environment_file.chmod(0o600)
    command = [
        "docker",
        "compose",
        "--env-file",
        os.fspath(environment_file),
        "-f",
        os.fspath(BASE_COMPOSE),
    ]
    rendered = subprocess.run(
        [*command, "config", "--format", "json"],
        check=False,
        capture_output=True,
        text=True,
    )
    quiet = subprocess.run(
        [*command, "config", "--quiet"],
        check=False,
        capture_output=True,
        text=True,
    )

    problems: list[str] = []
    if rendered.returncode != 0:
        problems.append("rendered base Compose was invalid")
        config: dict[str, object] = {}
    else:
        config = json.loads(rendered.stdout)
    if quiet.returncode != 0:
        problems.append("operator-facing quiet validation failed")
    services = config.get("services") if isinstance(config, dict) else None
    for service_name in ("backend", "worker"):
        service = services.get(service_name) if isinstance(services, dict) else None
        service_environment = service.get("environment") if isinstance(service, dict) else None
        if not isinstance(service_environment, dict):
            problems.append(f"{service_name} environment was absent")
            continue
        if not EXACT_PROVIDER_SETTINGS.issubset(service_environment):
            problems.append(f"{service_name} provider settings were absent")
            continue
        if any(service_environment[key] != sentinels[key] for key in EXACT_PROVIDER_SETTINGS):
            problems.append(f"{service_name} provider settings did not match")

    settings = Settings(
        bitbucket_oauth_client_id=sentinels["VERBOFLEX_BITBUCKET_OAUTH_CLIENT_ID"],
        bitbucket_oauth_client_secret=sentinels["VERBOFLEX_BITBUCKET_OAUTH_CLIENT_SECRET"],
        bitbucket_token_encryption_keyring=sentinels[
            "VERBOFLEX_BITBUCKET_TOKEN_ENCRYPTION_KEYRING"
        ],
    )
    BitbucketOAuthService(settings=settings, token_exchange=_UnusedTokenExchange())

    captured = capsys.readouterr()
    diagnostic_surfaces = "\n".join(
        (captured.out, captured.err, rendered.stderr, quiet.stdout, quiet.stderr)
    )
    assert all(value not in diagnostic_surfaces for value in sentinels.values())
    assert not problems, "; ".join(problems)


def test_deployment_overlays_give_scheduler_exact_worker_authority(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Every deployed backend process receives one exact scheduler-safe authority."""
    sentinels = {
        "VERBOFLEX_POSTGRES_PASSWORD": secrets.token_urlsafe(24),
        "VERBOFLEX_JWT_SECRET_KEY": secrets.token_urlsafe(32),
        "VERBOFLEX_BITBUCKET_OAUTH_CLIENT_ID": secrets.token_urlsafe(18),
        "VERBOFLEX_BITBUCKET_OAUTH_CLIENT_SECRET": secrets.token_urlsafe(32),
        "VERBOFLEX_BITBUCKET_TOKEN_ENCRYPTION_KEYRING": Fernet.generate_key().decode(),
        "VERBOFLEX_PREVIEW_SOFT_TIME_LIMIT_SECONDS": "41",
        "VERBOFLEX_PREVIEW_HARD_TIME_LIMIT_SECONDS": "53",
        "VERBOFLEX_PREVIEW_WATCHDOG_GRACE_SECONDS": "7",
        "VERBOFLEX_PREVIEW_WATCHDOG_INTERVAL_SECONDS": "3",
    }
    environment_file = tmp_path / "owner-only-deployment.env"
    environment_file.write_text(
        "".join(f"{key}={value}\n" for key, value in sentinels.items()),
        encoding="utf-8",
    )
    environment_file.chmod(0o600)

    problems: list[str] = []
    diagnostic_surfaces: list[str] = []
    if environment_file.stat().st_mode & 0o777 != 0o600:
        problems.append("deployment env permissions were not owner-only")

    for deployment, overlay, expected_environment, expected_image in (
        ("staging", STAGING_COMPOSE, "staging", "verboflex-backend:staging"),
        (
            "production",
            PRODUCTION_COMPOSE,
            "production",
            "verboflex-backend:production",
        ),
    ):
        command = [
            "docker",
            "compose",
            "--env-file",
            os.fspath(environment_file),
            "-f",
            os.fspath(BASE_COMPOSE),
            "-f",
            os.fspath(overlay),
        ]
        rendered = subprocess.run(
            [*command, "config", "--format", "json"],
            check=False,
            capture_output=True,
            text=True,
        )
        quiet = subprocess.run(
            [*command, "config", "--quiet"],
            check=False,
            capture_output=True,
            text=True,
        )
        diagnostic_surfaces.extend((rendered.stderr, quiet.stdout, quiet.stderr))
        if rendered.returncode != 0:
            problems.append(f"{deployment} rendered config was invalid")
            continue
        if quiet.returncode != 0:
            problems.append(f"{deployment} quiet validation failed")

        config = json.loads(rendered.stdout)
        services = config.get("services")
        if not isinstance(services, dict):
            problems.append(f"{deployment} services were absent")
            continue
        authorities: dict[str, dict[str, object]] = {}
        for service_name in ("backend", "worker", "scheduler"):
            service = services.get(service_name)
            if not isinstance(service, dict):
                problems.append(f"{deployment} {service_name} service was absent")
                continue
            environment = service.get("environment")
            if not isinstance(environment, dict):
                problems.append(f"{deployment} {service_name} environment was absent")
                continue
            missing = EXACT_DEPLOYMENT_SETTINGS.difference(environment)
            for key in sorted(missing):
                problems.append(f"{deployment} {service_name} missing {key}")
            authorities[service_name] = {
                "environment": {
                    key: environment.get(key) for key in EXACT_DEPLOYMENT_SETTINGS
                },
                "image": service.get("image"),
                "restart": service.get("restart"),
            }
            if environment.get("VERBOFLEX_APP_ENV") != expected_environment:
                problems.append(f"{deployment} {service_name} app environment mismatched")
            if service.get("image") != expected_image:
                problems.append(f"{deployment} {service_name} image mismatched")
            if service.get("restart") != "unless-stopped":
                problems.append(f"{deployment} {service_name} restart policy mismatched")

        if len(authorities) == 3 and len(set(map(repr, authorities.values()))) != 1:
            problems.append(f"{deployment} backend process authority mismatched")
        scheduler = services.get("scheduler")
        worker = services.get("worker")
        if isinstance(scheduler, dict) and "beat" not in scheduler.get("command", []):
            problems.append(f"{deployment} scheduler command was not Celery Beat")
        if isinstance(worker, dict) and "beat" in worker.get("command", []):
            problems.append(f"{deployment} worker command included Celery Beat")

    captured = capsys.readouterr()
    diagnostic_surfaces.extend((captured.out, captured.err))
    combined_diagnostics = "\n".join(diagnostic_surfaces)
    for key, value in sentinels.items():
        if value in combined_diagnostics:
            problems.append(f"diagnostics leaked {key}")
    assert not problems, "; ".join(problems)


def test_base_client_credentials_smoke_uses_only_base_compose_and_owner_env() -> None:
    """The provider-readiness smoke has no staging or generated override dependency."""
    source = SMOKE_HARNESS.read_text(encoding="utf-8")

    assert "--base-client-credentials" in source
    assert "run_base_client_credentials" in source
    assert "compose_base()" in source
    assert 'chmod 600 "$SMOKE_ENV_FILE"' in source
    assert '"$REPO_ROOT/docker-compose.yml"' in source
    assert "provider-ready" in source
    base_function = source.split("run_base_client_credentials()", 1)[1].split("\n}", 1)[0]
    assert "docker-compose.staging.yml" not in base_function
    assert "SMOKE_OVERRIDE_FILE" not in base_function


def test_probe_is_an_authenticated_local_api_driver_without_provider_authority() -> None:
    """Only production code may contact the provider token endpoint or hold its bearer."""
    source = LIVE_SMOKE_HELPER.read_text(encoding="utf-8")
    forbidden = (
        "bitbucket.org/site/oauth2/access_token",
        "_exchange_client_credentials",
        "LiveCredentialAuthority",
        "ReadOnlyAuditTransport",
        "BitbucketHttpAdapter",
        "BITBUCKET_CLIENT_ID",
        "BITBUCKET_CLIENT_SECRET",
        "TOKEN_URL",
        "TOKEN_RESPONSE",
    )
    required_api_paths = (
        "/api/v1/auth/token",
        "/api/v1/admin/bitbucket/connect",
        "/api/v1/admin/bitbucket/reconnect",
        "/api/v1/admin/bitbucket/revoke",
        "/api/v1/admin/repositories",
        "/branches",
        "/sources",
    )

    assert all(fragment not in source for fragment in forbidden)
    assert all(path in source for path in required_api_paths)
    assert "Authorization" in source
    assert "Bearer" in source


def test_mock_provider_audit_is_exact_scope_five_gets_and_zero_writes() -> None:
    """The provider spy records only bounded non-secret grant and read metadata."""
    provider_source = MOCK_PROVIDER.read_text(encoding="utf-8")
    smoke_source = SMOKE_HARNESS.read_text(encoding="utf-8")

    assert 'form.get("grant_type") != ["client_credentials"]' in provider_source
    assert '"effective_scope": "repository"' in provider_source
    assert '"grant_type": "client_credentials"' in provider_source
    assert "CALLBACK_URL" not in provider_source
    assert "REFRESH_TOKEN" not in provider_source
    assert "assert len(repository_reads) == 5" in smoke_source
    assert 'assert all(row["method"] == "GET"' in smoke_source
    assert 'assert not [row for row in rows if row["category"] == "forbidden-mutation"]' in (
        smoke_source
    )
    assert 'allowed_keys = {"category", "effective_scope", "grant_type", "method"}' in (
        smoke_source
    )


def test_repeated_probe_uses_serialized_api_lifecycle_and_three_generations() -> None:
    """Connect/reconnect/revoke/reacquire stays behind the production API boundary."""
    probe_source = LIVE_SMOKE_HELPER.read_text(encoding="utf-8")
    smoke_source = SMOKE_HARNESS.read_text(encoding="utf-8")
    run_source = probe_source.split("def run(path: Path) -> None:", 1)[1].split("\ndef main()", 1)[
        0
    ]

    assert run_source.count('"/api/v1/admin/bitbucket/connect"') == 2
    assert run_source.count('"/api/v1/admin/bitbucket/reconnect"') == 1
    assert run_source.count('"/api/v1/admin/bitbucket/revoke"') == 2
    assert run_source.count('"/api/v1/admin/bitbucket"') >= 2
    assert run_source.rstrip().endswith('"Disconnected",\n    )')
    assert "ciphertext" not in run_source.casefold()
    assert "provider_token" not in run_source.casefold()
    assert "assert len(exchanges) == 3" in smoke_source


def test_coverage_rewrites_exactly_three_keys_without_semantic_loss() -> None:
    """The 44-row provider ledger changes only the declared grant-model decisions."""
    rows = _coverage_rows()
    decisions = {key: decision for key, decision, _reason in rows}
    reasons = {key: reason for key, _decision, reason in rows}
    expected = {IDENTITY_REWRITE[key]: PRE_REWRITE_DECISIONS[key] for key in IDENTITY_REWRITE}
    expected.update(
        {
            "oauth-client-credentials-acquisition": "INTEGRATE",
            "oauth-client-credentials-reacquisition": "INTEGRATE",
            "oauth-authorization-code-callback-and-refresh-token-flows": "OPT-OUT",
        }
    )

    assert len(PRE_REWRITE_DECISIONS) == 44
    assert len(IDENTITY_REWRITE) == 41
    assert len(rows) == 44
    assert len(decisions) == 44
    assert decisions == expected
    assert set(DECLARED_CREDENTIAL_REWRITE) == {
        "oauth-authorization-code-start",
        "oauth-authorization-code-exchange",
        "oauth-refresh-token-exchange-and-rotation",
    }
    assert all(old not in decisions for old in DECLARED_CREDENTIAL_REWRITE)
    assert all(new in decisions for new in DECLARED_CREDENTIAL_REWRITE.values())
    assert decisions["oauth-effective-scope-inspection"] == "INTEGRATE"
    assert all(reasons[key] for key, decision in decisions.items() if decision == "OPT-OUT")
    consolidated_reason = reasons[
        "oauth-authorization-code-callback-and-refresh-token-flows"
    ].casefold()
    assert "authorization-code" in consolidated_reason
    assert "callback" in consolidated_reason
    assert "refresh-token" in consolidated_reason


def test_smoke_contract_scans_all_evidence_and_always_tears_down() -> None:
    """Every deterministic secret surface is scanned before disposable cleanup."""
    source = SMOKE_HARNESS.read_text(encoding="utf-8")

    assert "verify_no_secret_surfaces" in source
    assert "provider-audit.jsonl" in source
    assert "compose.log" in source
    assert "stdout.log" in source
    assert "stderr.log" in source
    assert "traceback" in source.casefold()
    assert "compose down --volumes --remove-orphans" in source
    assert 'docker ps -aq --filter "label=com.docker.compose.project=$SMOKE_PROJECT"' in source
    assert (
        'docker volume ls -q --filter "label=com.docker.compose.project=$SMOKE_PROJECT"' in source
    )
    assert (
        'docker network ls -q --filter "label=com.docker.compose.project=$SMOKE_PROJECT"' in source
    )


def test_live_config_requires_secure_exact_authorization_and_repository_identity(
    tmp_path: Path,
) -> None:
    """Only one mode-0600 exact-scope repository target reaches live I/O."""
    live_smoke = _load_live_smoke()
    environment = tmp_path / ".env.phase2-live"
    _write_live_env(environment)

    config = live_smoke.LiveSmokeConfig.from_dotenv(environment)

    assert config.base_url == "http://localhost:8123"
    assert config.workspace == "acme"
    assert config.repository_slug == "translations"
    assert config.branch == "main"

    rejected = (
        {"VERBOFLEX_BASE_URL": "https://api.bitbucket.org"},
        {"BITBUCKET_WORKSPACE": "../acme"},
        {"BITBUCKET_REPOSITORY_SLUG": "translations/other"},
        {"BITBUCKET_BRANCH": "bad\\branch"},
    )
    for index, overrides in enumerate(rejected):
        candidate = tmp_path / f"rejected-{index}.env"
        _write_live_env(candidate, **overrides)
        with pytest.raises(live_smoke.LiveSmokeRejected):
            live_smoke.LiveSmokeConfig.from_dotenv(candidate)

    skipped = tmp_path / "skipped.env"
    _write_live_env(skipped, VERBOFLEX_LIVE_PROVIDER_OPT_IN="")
    with pytest.raises(live_smoke.LiveSmokeSkipped):
        live_smoke.LiveSmokeConfig.from_dotenv(skipped)

    environment.chmod(0o640)
    with pytest.raises(live_smoke.LiveSmokeRejected):
        live_smoke.LiveSmokeConfig.from_dotenv(environment)


def test_local_api_client_rejects_non_application_paths() -> None:
    """The probe client cannot be redirected into a provider or arbitrary URL."""
    live_smoke = _load_live_smoke()
    api = live_smoke.LocalApi("http://localhost:8123")

    with pytest.raises(live_smoke.LiveSmokeRejected):
        api.request("GET", "https://api.bitbucket.org/2.0/repositories/acme/translations")
    with pytest.raises(live_smoke.LiveSmokeRejected):
        api.request("GET", "/health")


def test_mock_provider_smoke_retries_only_the_bounded_port_binding_race() -> None:
    """A transient host-port race gets a bounded fresh isolated smoke attempt."""
    source = (REPOSITORY_ROOT / "tools" / "phase2_smoke.sh").read_text()

    assert "run_mock_provider_with_port_retry()" in source
    assert "for attempt in 1 2 3" in source
    assert 'if [ "$rc" -ne 75 ]' in source
    assert 'grep -Fq "address already in use"' in source
    assert "return 75" in source


def test_compose_runs_preview_scheduler_as_a_separate_shared_service() -> None:
    """Beat is isolated from worker loss while sharing its durable dependencies."""
    compose = yaml.safe_load(BASE_COMPOSE.read_text(encoding="utf-8"))
    services = compose["services"]
    backend = services["backend"]
    worker = services["worker"]
    scheduler = services["scheduler"]

    assert scheduler["environment"] == worker["environment"] == backend["environment"]
    assert scheduler["depends_on"] == worker["depends_on"]
    assert scheduler["build"] == worker["build"]
    assert scheduler["command"] == [
        "celery",
        "-A",
        "verboflex.worker.celery_app",
        "beat",
        "--loglevel=INFO",
        "--schedule=/tmp/celerybeat-schedule",
    ]
    assert "beat" not in worker["command"]


def test_worker_loss_smoke_proves_bounded_terminalization_and_retry() -> None:
    """The smoke kills only after durable running and retains the old terminal row."""
    source = SMOKE_HARNESS.read_text(encoding="utf-8")

    assert "--worker-loss" in source
    assert "run_worker_loss()" in source
    worker_loss = source.split("run_worker_loss()", 1)[1].split(
        "\nrun_mock_provider_with_port_retry()", 1
    )[0]
    required = (
        "wait_for_preview_state",
        '"running"',
        "docker kill --signal=KILL",
        "preview_max_terminalization_seconds",
        '"timed_out"',
        '"time_limit_exceeded"',
        "compose_active up -d worker",
        "retry_preview_job",
        '"succeeded"',
        "assert_original_preview_unchanged",
    )

    assert all(fragment in worker_loss for fragment in required)
    assert "deadline=" in worker_loss
    assert "sleep 10" not in worker_loss


def test_worker_loss_smoke_exercises_staging_and_production_overlays() -> None:
    """The authoritative process-loss gate runs each shipped deployment in isolation."""
    source = SMOKE_HARNESS.read_text(encoding="utf-8")
    gauntlet = GAUNTLET_HARNESS.read_text(encoding="utf-8")

    assert 'SMOKE_DEPLOYMENT_OVERLAY=""' in source
    assert "compose_deployment_overlay()" in source
    assert "run_worker_loss_for_overlay_with_port_retry()" in source
    assert "run_worker_loss_dual_overlay()" in source

    compose_mock = source.split("compose_mock()", 1)[1].split("\n}", 1)[0]
    assert 'if [ -n "$SMOKE_DEPLOYMENT_OVERLAY" ]' in compose_mock
    base_position = compose_mock.index('"$REPO_ROOT/docker-compose.yml"')
    deployment_position = compose_mock.index('"$deployment_overlay"')
    mock_position = compose_mock.index('"$SMOKE_OVERRIDE_FILE"')
    assert base_position < deployment_position < mock_position

    worker_loss = source.split("run_worker_loss()", 1)[1].split(
        "\nrun_worker_loss_for_overlay_with_port_retry()", 1
    )[0]
    assert 'SMOKE_DEPLOYMENT_OVERLAY=$1' in worker_loss
    assert "prepare_base_stack" in worker_loss
    assert "wait_for_scheduler" in source.split("prepare_base_stack()", 1)[1].split(
        "\n}", 1
    )[0]
    assert "compose_base" not in worker_loss

    retry = source.split("run_worker_loss_for_overlay_with_port_retry()", 1)[1].split(
        "\n}", 1
    )[0]
    assert "for attempt in 1 2 3" in retry
    assert 'if [ "$rc" -ne 75 ]' in retry
    assert '"$SCRIPT_DIR/phase2_smoke.sh" --worker-loss-once "$deployment_overlay"' in (
        retry
    )

    dual_overlay = source.split("run_worker_loss_dual_overlay()", 1)[1].split(
        "\n}", 1
    )[0]
    assert dual_overlay.count("run_worker_loss_for_overlay_with_port_retry staging") == 1
    assert dual_overlay.count("run_worker_loss_for_overlay_with_port_retry production") == 1
    assert "compose_base" not in dual_overlay

    assert gauntlet.count("run_layer worker-loss-smoke") == 1
    assert (
        'run_layer worker-loss-smoke "$GAUNTLET_DIR/phase2_smoke.sh" '
        "--mock-provider --worker-loss"
    ) in gauntlet
