"""OAuth authority for MCP; raw codes, client secrets and tokens are never persisted."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from verboflex.db.base import Base


class McpClient(Base):
    __tablename__ = "mcp_oauth_clients"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    redirect_uris: Mapped[list[str]] = mapped_column(JSONB)
    auth_method: Mapped[str] = mapped_column(String(32))
    secret_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class McpGrant(Base):
    __tablename__ = "mcp_oauth_grants"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    client_id: Mapped[str] = mapped_column(
        ForeignKey("mcp_oauth_clients.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_version: Mapped[int] = mapped_column(Integer)
    scope: Mapped[str] = mapped_column(String(64))
    resource: Mapped[str] = mapped_column(String(2048))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class McpAuthorizationRequest(Base):
    __tablename__ = "mcp_oauth_requests"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[str] = mapped_column(
        ForeignKey("mcp_oauth_clients.id", ondelete="CASCADE"), index=True
    )
    redirect_uri: Mapped[str] = mapped_column(String(2048))
    scope: Mapped[str] = mapped_column(String(64))
    resource: Mapped[str] = mapped_column(String(2048))
    state: Mapped[str | None] = mapped_column(String(2048))
    code_challenge: Mapped[str] = mapped_column(String(43))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_version: Mapped[int | None] = mapped_column(Integer)
    code_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    grant_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("mcp_oauth_grants.id", ondelete="SET NULL")
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class McpToken(Base):
    __tablename__ = "mcp_oauth_tokens"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    grant_id: Mapped[UUID] = mapped_column(
        ForeignKey("mcp_oauth_grants.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(8))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
