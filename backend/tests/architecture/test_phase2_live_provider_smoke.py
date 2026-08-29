"""Fail-closed contract for the disposable Phase 2 live provider smoke."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import httpx
import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
LIVE_SMOKE_HELPER = REPOSITORY_ROOT / "tools" / "phase2_live_provider.py"
EXPECTED_CALLBACK = "http://localhost:8000/api/v1/admin/bitbucket/oauth/callback"


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
