"""Fail-closed contract for the disposable Phase 2 live provider smoke."""

from __future__ import annotations

import asyncio
import json
import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import httpx
import pytest
from cryptography.fernet import Fernet

from verboflex.core.config import Settings
from verboflex.services.bitbucket_oauth import BitbucketOAuthService

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
LIVE_SMOKE_HELPER = REPOSITORY_ROOT / "tools" / "phase2_live_provider.py"
EXPECTED_CALLBACK = "http://localhost:8000/api/v1/admin/bitbucket/oauth/callback"
BASE_COMPOSE = REPOSITORY_ROOT / "docker-compose.yml"
SMOKE_HARNESS = REPOSITORY_ROOT / "tools" / "phase2_smoke.sh"
MOCK_PROVIDER = REPOSITORY_ROOT / "tools" / "phase2_mock_provider.py"
EXACT_PROVIDER_SETTINGS = {
    "VERBOFLEX_BITBUCKET_OAUTH_CLIENT_ID",
    "VERBOFLEX_BITBUCKET_OAUTH_CLIENT_SECRET",
    "VERBOFLEX_BITBUCKET_TOKEN_ENCRYPTION_KEYRING",
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
        "VERBOFLEX_CONSUMER_VERIFIED": "consumer verified",
        "BITBUCKET_CLIENT_ID": "client-id",
        "BITBUCKET_CLIENT_SECRET": "client-secret",
        "BITBUCKET_CALLBACK_URL": EXPECTED_CALLBACK,
        "BITBUCKET_WORKSPACE": "acme",
        "BITBUCKET_REPOSITORY_SLUG": "translations",
        "BITBUCKET_BRANCH": "main",
    }
    values.update(overrides)
    path.write_text("".join(f'{key}="{value}"\n' for key, value in values.items()))
    path.chmod(0o600)


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
        bitbucket_oauth_client_secret=sentinels[
            "VERBOFLEX_BITBUCKET_OAUTH_CLIENT_SECRET"
        ],
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
    assert 'assert len(repository_reads) == 5' in smoke_source
    assert 'assert all(row["method"] == "GET"' in smoke_source
    assert 'assert not [row for row in rows if row["category"] == "forbidden-mutation"]' in (
        smoke_source
    )
    assert 'allowed_keys = {"category", "effective_scope", "grant_type", "method"}' in (
        smoke_source
    )


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
    assert 'docker volume ls -q --filter "label=com.docker.compose.project=$SMOKE_PROJECT"' in source
    assert 'docker network ls -q --filter "label=com.docker.compose.project=$SMOKE_PROJECT"' in source


def test_live_config_requires_secure_exact_authorization_and_repository_identity(
    tmp_path: Path,
) -> None:
    """Only one mode-0600 exact-scope repository target reaches live I/O."""
    live_smoke = _load_live_smoke()
    environment = tmp_path / ".env.phase2-live"
    _write_live_env(environment)

    config = live_smoke.LiveSmokeConfig.from_dotenv(environment)

    assert config.callback_url == EXPECTED_CALLBACK
    assert config.workspace == "acme"
    assert config.repository_slug == "translations"
    assert config.branch == "main"

    rejected = (
        {"VERBOFLEX_CONSUMER_VERIFIED": "yes"},
        {"BITBUCKET_CALLBACK_URL": "http://localhost:8000/callback"},
        {"BITBUCKET_WORKSPACE": "../acme"},
        {"BITBUCKET_REPOSITORY_SLUG": "translations/other"},
        {"BITBUCKET_BRANCH": "bad\\branch"},
    )
    for index, overrides in enumerate(rejected):
        candidate = tmp_path / f"rejected-{index}.env"
        _write_live_env(candidate, **overrides)
        with pytest.raises(live_smoke.LiveSmokeRejected):
            live_smoke.LiveSmokeConfig.from_dotenv(candidate)

    environment.chmod(0o640)
    with pytest.raises(live_smoke.LiveSmokeRejected):
        live_smoke.LiveSmokeConfig.from_dotenv(environment)


def test_provider_transport_allows_get_only_and_audits_mutation_attempts() -> None:
    """The live provider transport cannot emit a mutating REST request."""
    live_smoke = _load_live_smoke()
    delegated: list[httpx.Request] = []

    async def exercise() -> None:
        inner = httpx.MockTransport(
            lambda request: (
                delegated.append(request)
                or httpx.Response(
                    200,
                    json={"uuid": "{repository-uuid}"},
                    headers={"x-oauth-scopes": "repository"},
                    request=request,
                )
            )
        )
        audit = live_smoke.ProviderReadAudit()
        transport = live_smoke.ReadOnlyAuditTransport(inner=inner, audit=audit)
        get_request = httpx.Request(
            "GET",
            "https://api.bitbucket.org/2.0/repositories/acme/translations",
        )
        response = await transport.handle_async_request(get_request)
        assert response.status_code == 200

        for method in ("POST", "PUT", "PATCH", "DELETE"):
            request = httpx.Request(
                method,
                "https://api.bitbucket.org/2.0/repositories/acme/translations",
            )
            with pytest.raises(live_smoke.LiveSmokeRejected):
                await transport.handle_async_request(request)

        assert [request.method for request in delegated] == ["GET"]
        assert audit.get_requests == 1
        assert audit.mutation_attempts == 4
        await transport.aclose()

    asyncio.run(exercise())


def test_local_generation_revoke_erases_token_and_rejects_existing_lease() -> None:
    """The disposable token becomes unusable after the smoke's local revoke."""
    live_smoke = _load_live_smoke()
    authority = live_smoke.LiveCredentialAuthority(access_token="opaque")
    lease = authority.acquire_repository_read_lease(object())

    authority.revoke_local()

    assert authority.is_revoked is True
    with pytest.raises(live_smoke.OAuthGenerationRejected):
        authority.require_current_repository_read_lease(object(), lease)
    with pytest.raises(live_smoke.OAuthConnectionUnavailable):
        authority.acquire_repository_read_lease(object())


def test_mock_provider_smoke_retries_only_the_bounded_port_binding_race() -> None:
    """A transient host-port race gets a bounded fresh isolated smoke attempt."""
    source = (REPOSITORY_ROOT / "tools" / "phase2_smoke.sh").read_text()

    assert "run_mock_provider_with_port_retry()" in source
    assert "for attempt in 1 2 3" in source
    assert 'if [ "$rc" -ne 75 ]' in source
    assert 'grep -Fq "address already in use"' in source
    assert "return 75" in source
