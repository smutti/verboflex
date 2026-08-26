"""Credentialed browser-origin policy at the ASGI boundary."""

import asyncio

import httpx
import pytest
from fastapi import FastAPI
from pydantic import AnyHttpUrl

import verboflex.main as main_module
from verboflex.core.config import Settings

ALLOWED_ORIGIN = "https://frontend.verboflex.example"
DISALLOWED_ORIGIN = "https://attacker.example"


def build_app(monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    """Create an app with one exact browser origin."""
    settings = Settings(cors_origins=(AnyHttpUrl(ALLOWED_ORIGIN),))
    monkeypatch.setattr(main_module, "get_settings", lambda: settings)
    return main_module.create_app()


async def request(
    app: FastAPI,
    method: str,
    path: str,
    *,
    headers: dict[str, str],
) -> httpx.Response:
    """Issue an HTTP request directly through the configured ASGI app."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="https://api.verboflex.example",
    ) as client:
        return await client.request(method, path, headers=headers)


def test_exact_configured_origin_receives_credentialed_cors_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Echo only the configured origin and permit the refresh cookie."""
    app = build_app(monkeypatch)
    preflight = asyncio.run(
        request(
            app,
            "OPTIONS",
            "/api/v1/auth/token",
            headers={
                "Origin": ALLOWED_ORIGIN,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )
    )
    actual = asyncio.run(
        request(
            app,
            "GET",
            "/api/v1/health",
            headers={"Origin": ALLOWED_ORIGIN},
        )
    )

    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
    assert preflight.headers["access-control-allow-credentials"] == "true"
    assert preflight.headers["access-control-allow-origin"] != "*"
    assert actual.status_code == 200
    assert actual.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
    assert actual.headers["access-control-allow-credentials"] == "true"


def test_disallowed_origin_is_not_authorized_or_leaked_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reject hostile preflight without exposing the allowlist or internals."""
    app = build_app(monkeypatch)
    preflight = asyncio.run(
        request(
            app,
            "OPTIONS",
            "/api/v1/auth/token",
            headers={
                "Origin": DISALLOWED_ORIGIN,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
    )
    actual = asyncio.run(
        request(
            app,
            "GET",
            "/api/v1/health",
            headers={"Origin": DISALLOWED_ORIGIN},
        )
    )

    assert preflight.status_code == 400
    assert "access-control-allow-origin" not in preflight.headers
    assert "access-control-allow-origin" not in actual.headers
    diagnostic = preflight.text.casefold()
    assert ALLOWED_ORIGIN.casefold() not in diagnostic
    assert "cors_origins" not in diagnostic
    assert "traceback" not in diagnostic
