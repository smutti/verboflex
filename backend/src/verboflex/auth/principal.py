"""Database-backed authenticated-principal seams."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy.orm import Session

from verboflex.api.v1.routes.auth import OptionalBearerToken
from verboflex.core.config import Settings, get_settings
from verboflex.db.session import get_db_session
from verboflex.schemas.users import RoleName


@dataclass(frozen=True, slots=True)
class Principal:
    """Safe provider-independent authority loaded from durable state."""

    user_id: UUID
    email: str
    display_name: str
    roles: tuple[RoleName, ...]
    must_change_password: bool


def load_principal(
    session: Session,
    access_token: str | None,
    *,
    settings: Settings,
) -> Principal:
    """Resolve verified bearer authority against current PostgreSQL state."""
    raise NotImplementedError


def get_current_principal(
    access_token: OptionalBearerToken,
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Principal:
    """FastAPI dependency for ordinary authenticated resources."""
    raise NotImplementedError


CurrentPrincipal = Annotated[Principal, Depends(get_current_principal)]


def require_roles(*allowed: RoleName) -> Callable[[Principal], Principal]:
    """Build a reusable dependency accepting any database-loaded allowed role."""
    raise NotImplementedError
