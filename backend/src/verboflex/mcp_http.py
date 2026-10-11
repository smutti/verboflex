"""Authenticated Streamable HTTP MCP, with request-local internal API dispatch."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from urllib.parse import quote, urlsplit

import httpx
from fastapi import FastAPI
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import AnyHttpUrl
from starlette.applications import Starlette
from starlette.types import Receive, Scope, Send
from verboflex_mcp.api import MAX_RESPONSE_BYTES
from verboflex_mcp.server import create_server
from verboflex_mcp.session import ConnectorError

from verboflex.auth.principal import Principal
from verboflex.core.config import Settings
from verboflex.db.session import SessionFactory
from verboflex.schemas.mcp_oauth import READ_SCOPE, WRITE_SCOPE
from verboflex.services.mcp_oauth import OAuthError, load_authority, public_urls


def build_mcp_http(application: FastAPI, settings: Settings) -> Starlette:
    issuer, resource = public_urls(settings)

    class Verifier:
        async def verify_token(self, token: str) -> AccessToken | None:
            def verify() -> AccessToken | None:
                with SessionFactory() as session:
                    try:
                        authority = load_authority(session, token, settings)
                    except OAuthError:
                        return None
                    return AccessToken(
                        token=token,
                        client_id=authority.grant.client_id,
                        scopes=authority.grant.scope.split(),
                        resource=resource,
                        subject=str(authority.principal.user_id),
                        expires_at=int(authority.expires_at.timestamp()),
                    )

            return await asyncio.to_thread(verify)

    def can_write() -> bool:
        token = get_access_token()
        return token is not None and WRITE_SCOPE in token.scopes

    async def call_api(operation: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
        token = get_access_token()
        if token is None:
            raise ConnectorError("MCP authentication required")

        def principal_from_token() -> Principal:
            with SessionFactory() as session:
                return load_authority(session, token.token, settings).principal

        try:
            principal = await asyncio.to_thread(principal_from_token)
        except OAuthError:
            raise ConnectorError("MCP authorization expired or revoked") from None

        async def internal_app(scope: Scope, receive: Receive, send: Send) -> None:
            # This key is created in-process only. No HTTP header can supply it.
            scope["verboflex.mcp_principal"] = principal
            await application(scope, receive, send)

        path = operation["path"]
        query: list[tuple[str, str]] = []
        for key, location in operation["bindings"].items():
            value = arguments.get(key)
            if value is None:
                continue
            if location == "path":
                path = path.replace("{" + key + "}", quote(str(value), safe=""))
            else:
                query.extend(
                    (key, str(item).lower() if isinstance(item, bool) else str(item))
                    for item in (value if isinstance(value, list) else [value])
                )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=internal_app, raise_app_exceptions=False),
            base_url="http://internal",
            follow_redirects=False,
        ) as client:
            response = await client.request(
                operation["method"],
                settings.api_v1_prefix + path,
                params=httpx.QueryParams(tuple(query)),
                json=arguments.get("payload"),
            )
        if len(response.content) > MAX_RESPONSE_BYTES:
            raise ConnectorError(
                "Response too large. Narrow filters; inspect write state before retrying."
            )
        if response.status_code == 204:
            data = None
        elif response.status_code >= 500 or 300 <= response.status_code < 400:
            data = {"detail": "VerboFlex unavailable. Check status before retrying writes."}
        else:
            try:
                data = response.json()
            except json.JSONDecodeError:
                raise ConnectorError("Invalid API response") from None
        return {"status_code": response.status_code, "data": data}

    server = create_server(async_api=call_api, can_write=can_write)
    return server.streamable_http_app(
        streamable_http_path="/",
        json_response=True,
        stateless_http=True,
        max_request_body_size=2 * 1024 * 1024,
        auth=AuthSettings(
            issuer_url=AnyHttpUrl(issuer),
            resource_server_url=AnyHttpUrl(resource),
            required_scopes=[READ_SCOPE],
            validate_token_resource=True,
        ),
        token_verifier=Verifier(),
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=[urlsplit(resource).netloc],
            allowed_origins=[issuer],
        ),
    )


class McpEndpoint:
    """Dispatch the canonical resource path without a redirect or a shared scope."""

    def __init__(self, app: Starlette) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        inner = dict(scope)
        inner["path"], inner["raw_path"] = "/", b"/"
        await self.app(inner, receive, send)
