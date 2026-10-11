"""Global reusable, provider-scoped repository identity."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from verboflex.db.base import Base


class Repository(Base):
    """Credential-free provider identity reusable by independent products."""

    __tablename__ = "repositories"
    __table_args__ = (
        CheckConstraint("provider IN ('bitbucket', 'github')", name="provider_value"),
        CheckConstraint(
            "workspace ~ '^[a-z0-9][a-z0-9_-]{0,99}$'",
            name="workspace_normalized",
        ),
        CheckConstraint(
            "repository_slug ~ '^[a-z0-9][a-z0-9_.-]{0,99}$' "
            "AND (provider = 'github' OR repository_slug NOT LIKE '%.%')",
            name="repository_slug_normalized",
        ),
        CheckConstraint(
            "(descriptive_name IS NULL AND descriptive_name_key IS NULL) OR "
            "(char_length(descriptive_name) BETWEEN 1 AND 120 AND "
            "char_length(descriptive_name_key) BETWEEN 1 AND 360)",
            name="descriptive_name_state",
        ),
        UniqueConstraint(
            "provider",
            "workspace",
            "repository_slug",
            name="uq_repositories_provider_identity",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    workspace: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str] = mapped_column(
        String(16), nullable=False, default="bitbucket", server_default="bitbucket"
    )
    repository_slug: Mapped[str] = mapped_column(String(100), nullable=False)
    descriptive_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    descriptive_name_key: Mapped[str | None] = mapped_column(String(360), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
