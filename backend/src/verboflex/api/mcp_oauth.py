"""OAuth discovery/token endpoints plus bearer-authenticated browser consent."""

from __future__ import annotations

import base64
from datetime import UTC, datetime
from typing import Annotated
from urllib.parse import unquote, urlsplit
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import ValidationError
from redis import Redis
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from verboflex.auth.principal import CurrentPrincipal
from verboflex.auth.rate_limits import (
    RateLimitUnavailable,
    enforce_auth_action_rate_limit,
    get_redis_client,
    validated_client_ip,
)
from verboflex.core.config import Settings, get_settings
from verboflex.core.text import validate_storable_text
from verboflex.db.session import get_db_session
from verboflex.models.mcp_oauth import McpClient, McpGrant
from verboflex.schemas.mcp_oauth import SCOPES, McpConsentDecision, RegisterMcpClient
from verboflex.services import mcp_oauth as oauth

router = APIRouter(tags=["mcp-oauth"])
browser_router = APIRouter(prefix="/mcp", tags=["mcp-connections"])
Db = Annotated[Session, Depends(get_db_session)]
Config = Annotated[Settings, Depends(get_settings)]
NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache"}


def oauth_response(data: object, status: int = 200) -> JSONResponse:
    return JSONResponse(data, status_code=status, headers=NO_STORE)


def limit(request: Request, redis: Redis, *, action: str, maximum: int) -> None:
    try:
        result = enforce_auth_action_rate_limit(
            redis,
            action=f"mcp-{action}",
            identity="anonymous",
            client_ip=validated_client_ip(request),
            limit=maximum,
        )
    except RateLimitUnavailable:
        raise oauth.OAuthError("temporarily_unavailable", 503) from None
    if not result.allowed:
        raise oauth.OAuthError("slow_down", 429)


async def bounded_body(request: Request, maximum: int = 16384) -> bytes:
    body = bytearray()
    async for part in request.stream():
        body.extend(part)
        if len(body) > maximum:
            raise oauth.OAuthError("invalid_request", 413)
    return bytes(body)


@router.get("/.well-known/oauth-authorization-server", include_in_schema=False)
def authorization_metadata(settings: Config) -> JSONResponse:
    issuer, _ = oauth.public_urls(settings)
    return oauth_response(
        {
            "issuer": issuer,
            "authorization_endpoint": issuer + "/oauth/authorize",
            "token_endpoint": issuer + "/oauth/token",
            "registration_endpoint": issuer + "/oauth/register",
            "revocation_endpoint": issuer + "/oauth/revoke",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"],
            "scopes_supported": SCOPES,
            "token_endpoint_auth_methods_supported": [
                "none",
                "client_secret_post",
                "client_secret_basic",
            ],
            "revocation_endpoint_auth_methods_supported": [
                "none",
                "client_secret_post",
                "client_secret_basic",
            ],
            "client_id_metadata_document_supported": False,
        }
    )


@router.get("/.well-known/oauth-protected-resource", include_in_schema=False)
@router.get("/.well-known/oauth-protected-resource/mcp", include_in_schema=False)
def resource_metadata(settings: Config) -> JSONResponse:
    issuer, resource = oauth.public_urls(settings)
    return oauth_response(
        {
            "resource": resource,
            "authorization_servers": [issuer],
            "scopes_supported": SCOPES,
            "bearer_methods_supported": ["header"],
        }
    )


@router.post("/oauth/register", include_in_schema=False)
async def register(
    request: Request,
    session: Db,
    settings: Config,
    redis: Annotated[Redis, Depends(get_redis_client)],
) -> JSONResponse:
    oauth.public_urls(settings)
    await run_in_threadpool(limit, request, redis, action="register", maximum=10)
    try:
        payload = RegisterMcpClient.model_validate_json(await bounded_body(request))
    except ValidationError:
        raise oauth.OAuthError("invalid_client_metadata") from None
    return oauth_response(await run_in_threadpool(oauth.register_client, session, payload), 201)


@router.get("/oauth/authorize", include_in_schema=False)
def authorize(
    request: Request,
    session: Db,
    settings: Config,
    redis: Annotated[Redis, Depends(get_redis_client)],
) -> RedirectResponse:
    issuer, _ = oauth.public_urls(settings)
    limit(request, redis, action="authorize", maximum=30)
    items = list(request.query_params.multi_items())
    if (
        len(items) > 12
        or len({k for k, _ in items}) != len(items)
        or any(len(v) > 2048 for _, v in items)
    ):
        raise oauth.OAuthError("invalid_request")
    validate_parameters(dict(items))
    request_id = oauth.start_authorization(session, dict(items), settings)
    return RedirectResponse(
        issuer + "/mcp/authorize?request=" + request_id, status_code=302, headers=NO_STORE
    )


async def token_form(request: Request) -> tuple[dict[str, str], str]:
    from urllib.parse import parse_qsl

    if request.headers.get("content-type", "").split(";")[0] != "application/x-www-form-urlencoded":
        raise oauth.OAuthError("invalid_request")
    try:
        items = parse_qsl(
            (await bounded_body(request)).decode(), keep_blank_values=True, max_num_fields=12
        )
    except ValueError, UnicodeError:
        raise oauth.OAuthError("invalid_request") from None
    if len({k for k, _ in items}) != len(items) or any(len(v) > 4096 for _, v in items):
        raise oauth.OAuthError("invalid_request")
    data = dict(items)
    method = "client_secret_post" if "client_secret" in data else "none"
    if header := request.headers.get("Authorization"):
        if method != "none" or "client_id" in data or not header.startswith("Basic "):
            raise oauth.OAuthError("invalid_client", 401)
        try:
            client_id, secret = base64.b64decode(header[6:], validate=True).decode().split(":", 1)
        except ValueError, UnicodeError:
            raise oauth.OAuthError("invalid_client", 401) from None
        data.update(client_id=unquote(client_id), client_secret=unquote(secret))
        method = "client_secret_basic"
    validate_parameters(data)
    return data, method


def validate_parameters(data: dict[str, str]) -> None:
    try:
        for key, value in data.items():
            validate_storable_text(key)
            validate_storable_text(value)
    except ValueError:
        raise oauth.OAuthError("invalid_request") from None


@router.post("/oauth/token", include_in_schema=False)
async def token(
    request: Request,
    session: Db,
    settings: Config,
    redis: Annotated[Redis, Depends(get_redis_client)],
) -> JSONResponse:
    oauth.public_urls(settings)
    await run_in_threadpool(limit, request, redis, action="token", maximum=120)
    data, method = await token_form(request)
    client = await run_in_threadpool(
        oauth.authenticate_client,
        session,
        data.get("client_id", ""),
        data.get("client_secret"),
        method,
    )
    if data.get("grant_type") == "authorization_code":
        payload = await run_in_threadpool(oauth.exchange_code, session, client, data, settings)
    elif data.get("grant_type") == "refresh_token":
        payload = await run_in_threadpool(oauth.rotate_token, session, client, data, settings)
    else:
        raise oauth.OAuthError("unsupported_grant_type")
    return oauth_response(payload)


@router.post("/oauth/revoke", include_in_schema=False)
async def revoke(
    request: Request,
    session: Db,
    settings: Config,
    redis: Annotated[Redis, Depends(get_redis_client)],
) -> JSONResponse:
    oauth.public_urls(settings)
    await run_in_threadpool(limit, request, redis, action="revoke", maximum=30)
    data, method = await token_form(request)
    client = await run_in_threadpool(
        oauth.authenticate_client,
        session,
        data.get("client_id", ""),
        data.get("client_secret"),
        method,
    )
    await run_in_threadpool(oauth.revoke_token, session, client, data.get("token", ""))
    return oauth_response({})


@browser_router.get("/authorization/{request_id}")
def get_consent(request_id: str, principal: CurrentPrincipal, session: Db) -> JSONResponse:
    pending = oauth.consent_request(session, request_id)
    client = session.get_one(McpClient, pending.client_id)
    redirect = urlsplit(pending.redirect_uri)
    return oauth_response(
        {
            "client_name": client.name,
            "redirect_origin": f"{redirect.scheme}://{redirect.netloc}",
            "scopes": pending.scope.split(),
            "expires_at": pending.expires_at.isoformat(),
        }
    )


@browser_router.post("/authorization/{request_id}")
def post_consent(
    request_id: str, decision: McpConsentDecision, principal: CurrentPrincipal, session: Db
) -> JSONResponse:
    # Uses the ordinary SPA bearer token, never a cookie-only decision.
    redirect = oauth.decide(
        session, request_id, principal, allow=decision.allow, allow_write=decision.allow_write
    )
    return oauth_response({"redirect_url": redirect})


@browser_router.get("/connections")
def connections(principal: CurrentPrincipal, session: Db) -> JSONResponse:
    rows = session.execute(
        select(McpGrant, McpClient.name)
        .join(McpClient)
        .where(
            McpGrant.user_id == principal.user_id,
            McpGrant.revoked_at.is_(None),
            McpGrant.expires_at > datetime.now(UTC),
        )
        .order_by(McpGrant.created_at.desc(), McpGrant.id)
        .limit(100)
    ).all()
    return oauth_response(
        {
            "items": [
                {
                    "id": str(grant.id),
                    "client_name": name,
                    "scopes": grant.scope.split(),
                    "created_at": grant.created_at.isoformat(),
                    "expires_at": grant.expires_at.isoformat(),
                }
                for grant, name in rows
            ]
        }
    )


@browser_router.delete("/connections/{grant_id}", status_code=204)
def disconnect(grant_id: UUID, principal: CurrentPrincipal, session: Db) -> None:
    grant = session.scalar(
        select(McpGrant)
        .where(
            McpGrant.id == grant_id,
            McpGrant.user_id == principal.user_id,
        )
        .with_for_update()
    )
    if grant is None:
        raise HTTPException(404, "Connection unavailable")
    grant.revoked_at = datetime.now(UTC)
    session.commit()


async def oauth_error_handler(request: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, oauth.OAuthError)
    response = oauth_response({"error": error.code}, error.status)
    if error.code == "invalid_client" and request.headers.get("Authorization", "").startswith(
        "Basic "
    ):
        response.headers["WWW-Authenticate"] = 'Basic realm="VerboFlex OAuth"'
    return response
