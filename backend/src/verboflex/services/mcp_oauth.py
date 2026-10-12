"""Bounded OAuth code/PKCE and rotating-token transactions for the MCP resource."""

from __future__ import annotations

import base64
import hashlib
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from verboflex.auth.principal import Principal
from verboflex.auth.product_access import operational_roles
from verboflex.core.config import Settings
from verboflex.models.mcp_oauth import McpAuthorizationRequest, McpClient, McpGrant, McpToken
from verboflex.models.product_member import ProductMember
from verboflex.models.user import User
from verboflex.schemas.mcp_oauth import READ_SCOPE, SCOPES, RegisterMcpClient
from verboflex.schemas.users import RoleName


class OAuthError(Exception):
    def __init__(self, code: str, status: int = 400) -> None:
        self.code, self.status = code, status
        super().__init__(code)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def scope_string(value: str | None) -> str:
    scopes = set((value or READ_SCOPE).split())
    if not scopes <= set(SCOPES) or READ_SCOPE not in scopes:
        raise OAuthError("invalid_scope")
    return " ".join(sorted(scopes))


def public_urls(settings: Settings) -> tuple[str, str]:
    if settings.mcp_public_url is None:
        raise OAuthError("MCP is not configured", 404)
    resource = settings.mcp_public_url.rstrip("/")
    return resource.removesuffix("/mcp"), resource


def register_client(session: Session, payload: RegisterMcpClient) -> dict[str, Any]:
    scope_string(payload.scope)
    session.execute(text("SELECT pg_advisory_xact_lock(77146201)"))
    if session.execute(select(func.count()).select_from(McpClient)).scalar_one() >= 5000:
        raise OAuthError("temporarily_unavailable", 503)
    secret = secrets.token_urlsafe(32) if payload.token_endpoint_auth_method != "none" else None
    client = McpClient(
        id="vfmcp_" + secrets.token_urlsafe(24),
        name=payload.client_name,
        redirect_uris=payload.redirect_uris,
        auth_method=payload.token_endpoint_auth_method,
        secret_hash=digest(secret) if secret else None,
    )
    session.add(client)
    session.commit()
    result = payload.model_dump(exclude_none=True)
    result.update(client_id=client.id, client_id_issued_at=int(datetime.now(UTC).timestamp()))
    if secret:
        result.update(client_secret=secret, client_secret_expires_at=0)
    return result


def authenticate_client(
    session: Session, client_id: str, secret: str | None, method: str
) -> McpClient:
    client = session.get(McpClient, client_id)
    if client is None or client.auth_method != method:
        raise OAuthError("invalid_client", 401)
    if method != "none" and (
        secret is None or not secrets.compare_digest(client.secret_hash or "", digest(secret))
    ):
        raise OAuthError("invalid_client", 401)
    return client


def start_authorization(session: Session, parameters: dict[str, str], settings: Settings) -> str:
    _, resource = public_urls(settings)
    client = session.get(McpClient, parameters.get("client_id", ""))
    redirect = parameters.get("redirect_uri", "")
    if client is None or redirect not in client.redirect_uris:
        # Never redirect errors to an unvalidated callback.
        raise OAuthError("invalid_request")
    if parameters.get("response_type") != "code":
        raise OAuthError("unsupported_response_type")
    challenge = parameters.get("code_challenge", "")
    if parameters.get("code_challenge_method") != "S256" or not re.fullmatch(
        r"[A-Za-z0-9_-]{43}", challenge
    ):
        raise OAuthError("invalid_request")
    if parameters.get("resource") != resource:
        raise OAuthError("invalid_target")
    now = datetime.now(UTC)
    if (
        session.execute(
            select(func.count())
            .select_from(McpAuthorizationRequest)
            .where(
                McpAuthorizationRequest.client_id == client.id,
                McpAuthorizationRequest.expires_at > now,
            )
        ).scalar_one()
        >= 20
    ):
        raise OAuthError("temporarily_unavailable", 429)
    request_id = secrets.token_urlsafe(32)
    session.add(
        McpAuthorizationRequest(
            id=digest(request_id),
            client_id=client.id,
            redirect_uri=redirect,
            scope=scope_string(parameters.get("scope")),
            resource=resource,
            state=parameters.get("state"),
            code_challenge=challenge,
            expires_at=now + timedelta(minutes=10),
        )
    )
    session.commit()
    return request_id


def consent_request(
    session: Session, request_id: str, *, lock: bool = False
) -> McpAuthorizationRequest:
    query = select(McpAuthorizationRequest).where(McpAuthorizationRequest.id == digest(request_id))
    if lock:
        query = query.with_for_update()
    pending = session.scalar(query)
    if pending is None or pending.status != "pending" or pending.expires_at <= datetime.now(UTC):
        raise OAuthError("Authorization request expired", 404)
    return pending


def decide(
    session: Session, request_id: str, principal: Principal, *, allow: bool, allow_write: bool
) -> str:
    pending = consent_request(session, request_id, lock=True)
    query = list(parse_qsl(urlsplit(pending.redirect_uri).query, keep_blank_values=True))
    if pending.state is not None:
        query.append(("state", pending.state))
    if allow:
        code = secrets.token_urlsafe(32)
        pending.code_hash = digest(code)
        pending.status = "approved"
        pending.user_id = principal.user_id
        user = session.get_one(User, principal.user_id)
        pending.token_version = user.token_version
        pending.scope = pending.scope if allow_write else READ_SCOPE
        pending.expires_at = datetime.now(UTC) + timedelta(minutes=2)
        query.append(("code", code))
    else:
        pending.status = "denied"
        query.append(("error", "access_denied"))
    session.commit()
    url = urlsplit(pending.redirect_uri)
    return urlunsplit((url.scheme, url.netloc, url.path, urlencode(query), ""))


def _principal(session: Session, grant: McpGrant) -> Principal:
    user = session.get(User, grant.user_id)
    if (
        grant.revoked_at is not None
        or grant.expires_at <= datetime.now(UTC)
        or user is None
        or not user.is_active
        or user.must_change_password
        or user.token_version != grant.token_version
    ):
        raise OAuthError("invalid_grant")
    return Principal(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        roles=tuple(
            sorted(
                {RoleName(role.name) for role in user.roles}
                | {
                    r
                    for role in session.scalars(
                        select(ProductMember.role).where(
                            ProductMember.user_id == user.id, ProductMember.active
                        )
                    )
                    for r in operational_roles(role)
                }
            )
        ),
        must_change_password=False,
    )


def _issue(session: Session, grant: McpGrant, settings: Settings) -> dict[str, Any]:
    now = datetime.now(UTC)
    seconds = min(
        settings.access_token_expire_minutes * 60, int((grant.expires_at - now).total_seconds())
    )
    if seconds <= 0:
        raise OAuthError("invalid_grant")
    access, refresh = (
        "vfmcp_at_" + secrets.token_urlsafe(32),
        "vfmcp_rt_" + secrets.token_urlsafe(32),
    )
    session.add_all(
        [
            McpToken(
                token_hash=digest(access),
                grant_id=grant.id,
                kind="access",
                expires_at=now + timedelta(seconds=seconds),
            ),
            McpToken(
                token_hash=digest(refresh),
                grant_id=grant.id,
                kind="refresh",
                expires_at=grant.expires_at,
            ),
        ]
    )
    session.commit()
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "Bearer",
        "expires_in": seconds,
        "scope": grant.scope,
    }


def exchange_code(
    session: Session, client: McpClient, data: dict[str, str], settings: Settings
) -> dict[str, Any]:
    _, resource = public_urls(settings)
    pending = session.scalar(
        select(McpAuthorizationRequest)
        .where(
            McpAuthorizationRequest.code_hash == digest(data.get("code", "")),
        )
        .with_for_update()
    )
    verifier = data.get("code_verifier", "")
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    )
    if (
        pending is None
        or pending.client_id != client.id
        or pending.expires_at <= datetime.now(UTC)
        or pending.redirect_uri != data.get("redirect_uri")
        or pending.resource != resource
        or data.get("resource") != resource
        or not re.fullmatch(r"[A-Za-z0-9._~-]{43,128}", verifier)
        or not secrets.compare_digest(pending.code_challenge, challenge)
    ):
        raise OAuthError("invalid_grant")
    if pending.status != "approved":
        if pending.grant_id:
            grant = session.get(McpGrant, pending.grant_id, with_for_update=True)
            if grant:
                grant.revoked_at = datetime.now(UTC)
                session.commit()
        raise OAuthError("invalid_grant")
    grant = McpGrant(
        client_id=client.id,
        user_id=pending.user_id,
        token_version=pending.token_version,
        scope=pending.scope,
        resource=resource,
        expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days),
    )
    _principal(session, grant)
    session.add(grant)
    session.flush()
    pending.status, pending.grant_id = "exchanged", grant.id
    return _issue(session, grant, settings)


def rotate_token(
    session: Session, client: McpClient, data: dict[str, str], settings: Settings
) -> dict[str, Any]:
    _, resource = public_urls(settings)
    token = session.get(McpToken, digest(data.get("refresh_token", "")))
    if token is None or token.kind != "refresh":
        raise OAuthError("invalid_grant")
    grant = session.get_one(McpGrant, token.grant_id, with_for_update=True)
    session.refresh(token)
    if (
        grant.client_id != client.id
        or grant.resource != resource
        or data.get("resource", resource) != resource
    ):
        raise OAuthError("invalid_grant")
    _principal(session, grant)
    if token.used_at is not None:
        grant.revoked_at = datetime.now(UTC)
        session.commit()
        raise OAuthError("invalid_grant")
    if "scope" in data and scope_string(data["scope"]) != grant.scope:
        raise OAuthError("invalid_scope")
    token.used_at = datetime.now(UTC)
    return _issue(session, grant, settings)


@dataclass(frozen=True)
class McpAuthority:
    principal: Principal
    grant: McpGrant
    expires_at: datetime


def load_authority(session: Session, raw_token: str, settings: Settings) -> McpAuthority:
    _, resource = public_urls(settings)
    if not raw_token.startswith("vfmcp_at_") or len(raw_token) > 128:
        raise OAuthError("invalid_token", 401)
    token = session.get(McpToken, digest(raw_token))
    if token is None or token.kind != "access" or token.expires_at <= datetime.now(UTC):
        raise OAuthError("invalid_token", 401)
    grant = session.get_one(McpGrant, token.grant_id)
    if grant.resource != resource:
        raise OAuthError("invalid_token", 401)
    return McpAuthority(_principal(session, grant), grant, token.expires_at)


def revoke_token(session: Session, client: McpClient, raw_token: str) -> None:
    token = session.get(McpToken, digest(raw_token))
    if token:
        grant = session.get_one(McpGrant, token.grant_id, with_for_update=True)
        if grant.client_id == client.id:
            grant.revoked_at = datetime.now(UTC)
            session.commit()


def cleanup_oauth(session: Session, now: datetime) -> int:
    """Bounded hourly deletion; consumed refresh tokens survive until grant expiry."""
    total = 0
    for model, primary, condition in (
        (
            McpAuthorizationRequest,
            McpAuthorizationRequest.id,
            McpAuthorizationRequest.expires_at <= now,
        ),
        (McpToken, McpToken.token_hash, (McpToken.kind == "access") & (McpToken.expires_at <= now)),
        (McpGrant, McpGrant.id, McpGrant.expires_at <= now),
        (
            McpClient,
            McpClient.id,
            (McpClient.created_at < now - timedelta(days=90))
            & ~select(McpGrant.id).where(McpGrant.client_id == McpClient.id).exists()
            & ~select(McpAuthorizationRequest.id)
            .where(McpAuthorizationRequest.client_id == McpClient.id)
            .exists(),
        ),
    ):
        ids = select(primary).where(condition).order_by(primary).limit(1000)
        rows = session.scalars(delete(model).where(primary.in_(ids)).returning(primary))
        total += len(rows.all())
    session.commit()
    return total
