"""Single transactional authority for administrator-managed internal users."""

from __future__ import annotations

import base64
import binascii
import json
import secrets
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import and_, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from verboflex.auth.identity import ASCII_WHITESPACE, normalize_email
from verboflex.auth.passwords import hash_password, validate_password_for_user
from verboflex.models.role import Role
from verboflex.models.user import User
from verboflex.schemas.users import RoleName

ADMIN_AUTHORITY_LOCK_KEY = 0x564552424F464C58
DEFAULT_ADMIN_USER_PAGE_SIZE = 50
MAX_ADMIN_USER_PAGE_SIZE = 100
_CURSOR_VERSION = 1
_FIXED_ROLE_ORDER = tuple(RoleName)


class AdminUserAuthorityError(PermissionError):
    """Raised when the actor no longer has current durable admin authority."""


class AdminUserConflict(ValueError):
    """Raised through the non-enumerating duplicate-identity boundary."""


class AdminUserInputError(ValueError):
    """Raised when normalized input cannot form a valid user."""


class InvalidAdminUserCursor(ValueError):
    """Raised when a list cursor is not one emitted by this service."""


@dataclass(frozen=True, slots=True)
class AdminUserRecord:
    """Safe service projection shared by list and lifecycle results."""

    id: UUID
    email: str
    display_name: str
    roles: tuple[RoleName, ...]
    is_active: bool
    must_change_password: bool


@dataclass(frozen=True, slots=True)
class CreatedAdminUser:
    """Successful creation result whose plaintext is never durable or printable."""

    user: AdminUserRecord
    temporary_password: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class AdminUserPage:
    """One stable keyset page."""

    items: tuple[AdminUserRecord, ...]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class _CursorPosition:
    email: str
    user_id: UUID


def _ordered_roles(roles: list[Role]) -> tuple[RoleName, ...]:
    selected = {RoleName(role.name) for role in roles}
    return tuple(role for role in _FIXED_ROLE_ORDER if role in selected)


def _to_record(user: User) -> AdminUserRecord:
    return AdminUserRecord(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        roles=_ordered_roles(user.roles),
        is_active=user.is_active,
        must_change_password=user.must_change_password,
    )


def _load_current_admin(session: Session, actor_id: UUID, *, lock: bool) -> User:
    statement = select(User).where(User.id == actor_id).options(selectinload(User.roles))
    if lock:
        statement = statement.with_for_update()
    actor = session.execute(statement).scalar_one_or_none()
    if actor is None or not actor.is_active:
        raise AdminUserAuthorityError("administrator authority unavailable")
    if RoleName.ADMIN not in _ordered_roles(actor.roles):
        raise AdminUserAuthorityError("administrator authority unavailable")
    return actor


def _normalize_display_name(display_name: str) -> str:
    normalized = display_name.strip(ASCII_WHITESPACE)
    if not normalized:
        raise AdminUserInputError("display name is required")
    return normalized


def _load_requested_roles(session: Session, roles: frozenset[RoleName]) -> list[Role]:
    if not roles:
        raise AdminUserInputError("at least one role is required")
    durable_roles = list(
        session.execute(select(Role).where(Role.name.in_(role.value for role in roles))).scalars()
    )
    by_name = {RoleName(role.name): role for role in durable_roles}
    if set(by_name) != set(roles):
        raise AdminUserInputError("role authority is unavailable")
    return [by_name[role] for role in _FIXED_ROLE_ORDER if role in by_name]


def create_admin_user(
    session: Session,
    *,
    actor_id: UUID,
    email: str,
    display_name: str,
    roles: frozenset[RoleName],
) -> CreatedAdminUser:
    """Create one user under current database admin authority and return plaintext once."""
    normalized_email = normalize_email(email)
    normalized_display_name = _normalize_display_name(display_name)
    try:
        with session.begin():
            session.execute(
                text("SELECT pg_advisory_xact_lock(:lock_key)"),
                {"lock_key": ADMIN_AUTHORITY_LOCK_KEY},
            )
            _load_current_admin(session, actor_id, lock=True)
            if session.scalar(select(User.id).where(User.email == normalized_email)) is not None:
                raise AdminUserConflict("user could not be created")
            durable_roles = _load_requested_roles(session, roles)

            temporary_password = secrets.token_urlsafe(24)
            validate_password_for_user(
                temporary_password,
                normalized_email=normalized_email,
            )
            password_hash = hash_password(temporary_password)
            user = User(
                email=normalized_email,
                display_name=normalized_display_name,
                hashed_password=password_hash,
                is_active=True,
                must_change_password=True,
                token_version=0,
                roles=durable_roles,
            )
            session.add(user)
            session.flush()
            result = CreatedAdminUser(
                user=_to_record(user),
                temporary_password=temporary_password,
            )
    except IntegrityError as error:
        raise AdminUserConflict("user could not be created") from error
    return result


def _encode_cursor(record: AdminUserRecord) -> str:
    payload = json.dumps(
        {"email": record.email, "id": str(record.id), "version": _CURSOR_VERSION},
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")


def _decode_cursor(cursor: str) -> _CursorPosition:
    if not cursor or len(cursor) > 1024:
        raise InvalidAdminUserCursor("invalid cursor")
    try:
        padding = "=" * (-len(cursor) % 4)
        raw = base64.b64decode(cursor + padding, altchars=b"-_", validate=True)
        payload = json.loads(raw)
        if not isinstance(payload, dict) or set(payload) != {"email", "id", "version"}:
            raise ValueError
        if payload["version"] != _CURSOR_VERSION or not isinstance(payload["email"], str):
            raise ValueError
        position = _CursorPosition(
            email=payload["email"],
            user_id=UUID(payload["id"]),
        )
    except (
        binascii.Error,
        json.JSONDecodeError,
        UnicodeDecodeError,
        ValueError,
        TypeError,
    ) as error:
        raise InvalidAdminUserCursor("invalid cursor") from error
    canonical = _encode_cursor(
        AdminUserRecord(
            id=position.user_id,
            email=position.email,
            display_name="",
            roles=(),
            is_active=False,
            must_change_password=False,
        )
    )
    if canonical != cursor:
        raise InvalidAdminUserCursor("invalid cursor")
    return position


def list_admin_users(
    session: Session,
    *,
    actor_id: UUID,
    limit: int = DEFAULT_ADMIN_USER_PAGE_SIZE,
    cursor: str | None = None,
) -> AdminUserPage:
    """Return one deterministic user page only to current durable administrators."""
    if not 1 <= limit <= MAX_ADMIN_USER_PAGE_SIZE:
        raise AdminUserInputError("invalid page size")
    position = _decode_cursor(cursor) if cursor is not None else None
    with session.begin():
        _load_current_admin(session, actor_id, lock=False)
        statement = select(User).options(selectinload(User.roles))
        if position is not None:
            statement = statement.where(
                or_(
                    User.email > position.email,
                    and_(User.email == position.email, User.id > position.user_id),
                )
            )
        users = list(
            session.execute(statement.order_by(User.email, User.id).limit(limit + 1)).scalars()
        )
        records = tuple(_to_record(user) for user in users[:limit])
        next_cursor = _encode_cursor(records[-1]) if len(users) > limit else None
    return AdminUserPage(items=records, next_cursor=next_cursor)
