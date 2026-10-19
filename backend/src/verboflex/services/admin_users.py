"""Single transactional authority for administrator-managed internal users."""

from __future__ import annotations

import base64
import binascii
import json
import secrets
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, func, or_, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from verboflex.audit.ledger import record_audit
from verboflex.auth.identity import ASCII_WHITESPACE, normalize_email
from verboflex.auth.passwords import (
    PasswordPolicyError,
    hash_password,
    validate_password_for_user,
)
from verboflex.models.auth_session import AuthSession
from verboflex.models.product import Product
from verboflex.models.product_member import ProductMember, ProductTeamEvent
from verboflex.models.role import Role
from verboflex.models.user import User
from verboflex.schemas.admin_users import (
    AdminUserProductAccess,
    AdminUserProductAssignment,
    AdminUserProductChange,
    AdminUserProductsResponse,
)
from verboflex.schemas.product_team import MemberInput
from verboflex.schemas.users import RoleName
from verboflex.services.products import _CursorPosition as ProductCursorPosition
from verboflex.services.products import _decode_cursor as decode_product_cursor
from verboflex.services.products import _encode_cursor as encode_product_cursor

ADMIN_AUTHORITY_LOCK_KEY = 0x564552424F464C58
DEFAULT_ADMIN_USER_PAGE_SIZE = 50
MAX_ADMIN_USER_PAGE_SIZE = 100
_CURSOR_VERSION = 1
_FIXED_ROLE_ORDER = tuple(RoleName)
_MAX_TEMPORARY_CREDENTIAL_ATTEMPTS = 8


class AdminUserAuthorityError(PermissionError):
    """Raised when the actor no longer has current durable admin authority."""


class AdminUserConflict(ValueError):
    """Raised through the non-enumerating duplicate-identity boundary."""


class AdminUserInputError(ValueError):
    """Raised when normalized input cannot form a valid user."""


class AdminUserProductUnavailable(AdminUserInputError):
    """Raised when an initial product assignment can no longer be granted."""


class AdminUserProductConflict(AdminUserConflict):
    """An explicit membership edit no longer matches current team authority."""


class AdminUserNotFound(LookupError):
    """Raised when an administrator-selected UUID has no durable user."""


class ResetPasswordError(RuntimeError):
    """Raised when the privileged CLI reset cannot identify its account."""


class DeactivateUserError(RuntimeError):
    """Raised when the privileged CLI cannot deactivate its selected account."""


class _AdminUserAlreadyInactive(ValueError):
    """Internal distinction mapped by each lifecycle adapter."""


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
    statement = (
        select(User)
        .where(User.id == actor_id)
        .options(selectinload(User.roles))
        .execution_options(populate_existing=True)
    )
    if lock:
        statement = statement.with_for_update()
    actor = session.execute(statement).scalar_one_or_none()
    if actor is None or not actor.is_active or actor.must_change_password:
        raise AdminUserAuthorityError("administrator authority unavailable")
    try:
        roles = _ordered_roles(actor.roles)
    except ValueError as error:
        raise AdminUserAuthorityError("administrator authority unavailable") from error
    if RoleName.ADMIN not in roles:
        raise AdminUserAuthorityError("administrator authority unavailable")
    return actor


def _load_target_user(session: Session, target_id: UUID) -> User:
    target = session.execute(
        select(User).where(User.id == target_id).options(selectinload(User.roles)).with_for_update()
    ).scalar_one_or_none()
    if target is None:
        raise AdminUserNotFound("user unavailable")
    return target


def _load_target_user_by_email(session: Session, normalized_email: str) -> User:
    target = session.execute(
        select(User)
        .where(User.email == normalized_email)
        .options(selectinload(User.roles))
        .with_for_update()
    ).scalar_one_or_none()
    if target is None:
        raise AdminUserNotFound("user unavailable")
    return target


def _normalize_display_name(display_name: str) -> str:
    normalized = display_name.strip(ASCII_WHITESPACE)
    if not normalized:
        raise AdminUserInputError("display name is required")
    return normalized


def _normalize_admin_email(email: str) -> str:
    try:
        return normalize_email(email)
    except ValueError as error:
        raise AdminUserInputError("invalid email address") from error


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


def _lock_admin_authority(session: Session) -> None:
    session.execute(
        text("SELECT pg_advisory_xact_lock(:lock_key)"),
        {"lock_key": ADMIN_AUTHORITY_LOCK_KEY},
    )


def _active_admin_count(session: Session) -> int:
    count = session.scalar(
        select(func.count(func.distinct(User.id)))
        .select_from(User)
        .join(User.roles)
        .where(User.is_active.is_(True), Role.name == RoleName.ADMIN.value)
    )
    return int(count or 0)


def _require_admin_survivor(
    session: Session,
    target: User,
    *,
    prospective_roles: frozenset[RoleName],
    prospective_active: bool,
) -> None:
    current_roles = frozenset(_ordered_roles(target.roles))
    removes_active_admin = (
        target.is_active
        and RoleName.ADMIN in current_roles
        and (not prospective_active or RoleName.ADMIN not in prospective_roles)
    )
    if removes_active_admin and _active_admin_count(session) <= 1:
        raise AdminUserConflict("user lifecycle conflict")


def _revoke_live_sessions(
    session: Session,
    user_id: UUID,
    *,
    revoked_at: datetime,
) -> None:
    session.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=revoked_at)
    )


def _replace_password_authority(
    session: Session,
    user: User,
    *,
    password: str,
    revoked_at: datetime,
) -> None:
    validate_password_for_user(
        password,
        normalized_email=user.email,
        current_password_hash=user.hashed_password,
    )
    user.hashed_password = hash_password(password)
    user.must_change_password = True
    user.token_version += 1
    _revoke_live_sessions(session, user.id, revoked_at=revoked_at)


def _generate_temporary_credential(session: Session, user: User) -> CreatedAdminUser:
    for _attempt in range(_MAX_TEMPORARY_CREDENTIAL_ATTEMPTS):
        temporary_password = secrets.token_urlsafe(24)
        try:
            _replace_password_authority(
                session,
                user,
                password=temporary_password,
                revoked_at=datetime.now(UTC),
            )
        except PasswordPolicyError:
            continue
        session.flush()
        return CreatedAdminUser(user=_to_record(user), temporary_password=temporary_password)
    raise RuntimeError("temporary credential generation unavailable")


def create_admin_user(
    session: Session,
    *,
    actor_id: UUID,
    email: str,
    display_name: str,
    roles: frozenset[RoleName],
    product_assignments: Sequence[AdminUserProductAssignment] = (),
) -> CreatedAdminUser:
    """Create one user under current database admin authority and return plaintext once."""
    normalized_email = _normalize_admin_email(email)
    normalized_display_name = _normalize_display_name(display_name)
    try:
        with session.begin():
            _lock_admin_authority(session)
            _load_current_admin(session, actor_id, lock=True)
            if session.scalar(select(User.id).where(User.email == normalized_email)) is not None:
                raise AdminUserConflict("user could not be created")
            durable_roles = _load_requested_roles(session, roles)
            product_ids = {assignment.product_id for assignment in product_assignments}
            if len(product_ids) != len(product_assignments) or len(product_ids) > 100:
                raise AdminUserInputError("invalid product assignments")
            if product_ids:
                # Lock in stable order so deactivation/deletion cannot race provisioning.
                products = list(
                    session.scalars(
                        select(Product)
                        .where(Product.id.in_(product_ids))
                        .order_by(Product.id)
                        .with_for_update()
                    )
                )
                if len(products) != len(product_ids) or any(
                    not product.is_active or product.deleted_at is not None for product in products
                ):
                    raise AdminUserProductUnavailable("selected products unavailable")

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
            record_audit(session, actor_id=actor_id, action="user.created", entity_id=user.id)
            for assignment in product_assignments:
                session.add(
                    ProductMember(
                        product_id=assignment.product_id,
                        user_id=user.id,
                        role=assignment.role,
                        active=True,
                    )
                )
                session.add(
                    ProductTeamEvent(
                        actor_id=actor_id,
                        product_id=assignment.product_id,
                        subject_id=user.id,
                        action="member.added",
                        role=assignment.role,
                    )
                )
            result = CreatedAdminUser(
                user=_to_record(user),
                temporary_password=temporary_password,
            )
    except IntegrityError as error:
        raise AdminUserConflict("user could not be created") from error
    return result


def list_admin_user_products(
    session: Session,
    *,
    actor_id: UUID,
    target_id: UUID,
    limit: int = 50,
    cursor: str | None = None,
) -> AdminUserProductsResponse:
    """Page all non-deleted products with current membership versions for one account."""
    if not 1 <= limit <= 100:
        raise AdminUserInputError("invalid page size")
    with session.begin():
        _load_current_admin(session, actor_id, lock=False)
        if session.get(User, target_id) is None:
            raise AdminUserNotFound("user unavailable")
        position = (
            decode_product_cursor(cursor, status=None, name_filter=None)
            if cursor is not None
            else None
        )
        statement = (
            select(Product, ProductMember)
            .outerjoin(
                ProductMember,
                and_(
                    ProductMember.product_id == Product.id,
                    ProductMember.user_id == target_id,
                    ProductMember.active.is_(True),
                ),
            )
            .where(Product.deleted_at.is_(None))
        )
        if position is not None:
            statement = statement.where(
                or_(
                    Product.name_key > position.name_key,
                    and_(Product.name_key == position.name_key, Product.id > position.product_id),
                )
            )
        rows = list(
            session.execute(statement.order_by(Product.name_key, Product.id).limit(limit + 1))
        )
        page = rows[:limit]
        return AdminUserProductsResponse(
            items=[
                AdminUserProductAccess(
                    product_id=product.id,
                    name=product.display_name,
                    is_active=product.is_active,
                    role=member.role if member else None,
                    version=member.version if member else None,
                )
                for product, member in page
            ],
            next_cursor=(
                encode_product_cursor(
                    ProductCursorPosition(page[-1][0].name_key, page[-1][0].id, None, None)
                )
                if len(rows) > limit
                else None
            ),
        )


def _update_product_assignments(
    session: Session,
    *,
    actor_id: UUID,
    target: User,
    changes: Sequence[AdminUserProductChange],
) -> None:
    # Team operations share this service's authority lock; import after initialization.
    from verboflex.services.product_team import TeamError, remove_member, set_member

    if len(changes) > 100 or len({change.product_id for change in changes}) != len(changes):
        raise AdminUserInputError("invalid product assignments")
    try:
        for change in sorted(changes, key=lambda item: item.product_id):
            if change.role is None:
                if change.expected_version is None:
                    raise AdminUserInputError("membership version required")
                remove_member(
                    session, change.product_id, actor_id, target.id, change.expected_version
                )
            else:
                set_member(
                    session,
                    change.product_id,
                    actor_id,
                    MemberInput(
                        email=target.email,
                        role=change.role,
                        expected_version=change.expected_version,
                    ),
                )
    except TeamError as error:
        raise AdminUserProductConflict("product access changed or unavailable") from error


def update_admin_user(
    session: Session,
    *,
    actor_id: UUID,
    target_id: UUID,
    display_name: str,
    roles: frozenset[RoleName],
    product_assignments: Sequence[AdminUserProductChange] = (),
) -> AdminUserRecord:
    """Update the approved mutable fields while preserving global authority invariants."""
    normalized_display_name = _normalize_display_name(display_name)
    with session.begin():
        _lock_admin_authority(session)
        actor = _load_current_admin(session, actor_id, lock=True)
        target = _load_target_user(session, target_id)
        durable_roles = _load_requested_roles(session, roles)
        current_roles = frozenset(_ordered_roles(target.roles))
        if (
            actor.id == target.id
            and RoleName.ADMIN in current_roles
            and RoleName.ADMIN not in roles
        ):
            raise AdminUserConflict("user lifecycle conflict")
        _require_admin_survivor(
            session,
            target,
            prospective_roles=roles,
            prospective_active=target.is_active,
        )
        _update_product_assignments(
            session, actor_id=actor_id, target=target, changes=product_assignments
        )

        roles_changed = current_roles != roles
        display_changed = target.display_name != normalized_display_name
        if roles_changed:
            target.roles = durable_roles
            target.token_version += 1
            _revoke_live_sessions(session, target.id, revoked_at=datetime.now(UTC))
        if display_changed:
            target.display_name = normalized_display_name
        if roles_changed or display_changed:
            record_audit(session, actor_id=actor_id, action="user.updated", entity_id=target.id)
            session.flush()
        result = _to_record(target)
    return result


def reset_admin_user_password(
    session: Session,
    *,
    actor_id: UUID,
    target_id: UUID,
) -> CreatedAdminUser:
    """Replace one active user's password authority and reveal the new secret once."""
    with session.begin():
        _lock_admin_authority(session)
        _load_current_admin(session, actor_id, lock=True)
        target = _load_target_user(session, target_id)
        if not target.is_active:
            raise AdminUserConflict("user lifecycle conflict")
        record_audit(session, actor_id=actor_id, action="user.password_reset", entity_id=target.id)
        result = _generate_temporary_credential(session, target)
    return result


def deactivate_admin_user(
    session: Session,
    *,
    actor_id: UUID,
    target_id: UUID,
    now: datetime | None = None,
) -> AdminUserRecord:
    """Deactivate one user and revoke its durable authority exactly once."""
    deactivated_at = now or datetime.now(UTC)
    try:
        with session.begin():
            result = _deactivate_user_under_admin_authority_lock(
                session,
                actor_id=actor_id,
                target_id=target_id,
                deactivated_at=deactivated_at,
            )
    except _AdminUserAlreadyInactive as error:
        raise AdminUserConflict("user lifecycle conflict") from error
    return result


def _deactivate_user_under_admin_authority_lock(
    session: Session,
    *,
    deactivated_at: datetime,
    actor_id: UUID | None = None,
    target_id: UUID | None = None,
    normalized_email: str | None = None,
) -> AdminUserRecord:
    """Serialize every deactivation before locking and changing its target."""
    if (target_id is None) == (normalized_email is None):
        raise ValueError("exactly one target identity is required")

    _lock_admin_authority(session)
    if actor_id is not None:
        _load_current_admin(session, actor_id, lock=True)
    target = (
        _load_target_user(session, target_id)
        if target_id is not None
        else _load_target_user_by_email(session, normalized_email or "")
    )
    if not target.is_active:
        raise _AdminUserAlreadyInactive
    current_roles = frozenset(_ordered_roles(target.roles))
    _require_admin_survivor(
        session,
        target,
        prospective_roles=current_roles,
        prospective_active=False,
    )
    record_audit(session, actor_id=actor_id, action="user.deactivated", entity_id=target.id)
    target.is_active = False
    target.token_version += 1
    _revoke_live_sessions(session, target.id, revoked_at=deactivated_at)
    session.flush()
    return _to_record(target)


def reactivate_admin_user(
    session: Session,
    *,
    actor_id: UUID,
    target_id: UUID,
) -> CreatedAdminUser:
    """Reactivate one user with newly generated password authority."""
    with session.begin():
        _lock_admin_authority(session)
        _load_current_admin(session, actor_id, lock=True)
        target = _load_target_user(session, target_id)
        if target.is_active:
            raise AdminUserConflict("user lifecycle conflict")
        target.is_active = True
        record_audit(session, actor_id=actor_id, action="user.reactivated", entity_id=target.id)
        result = _generate_temporary_credential(session, target)
    return result


def replace_user_password(
    session: Session,
    *,
    email: str,
    password: str,
) -> None:
    """Retain the privileged Phase 1 CLI reset through the shared password authority."""
    normalized_email = normalize_email(email)
    with session.begin():
        user = session.execute(
            select(User).where(User.email == normalized_email).with_for_update()
        ).scalar_one_or_none()
        if user is None:
            raise ResetPasswordError("reset refused: account unavailable")
        _replace_password_authority(
            session,
            user,
            password=password,
            revoked_at=datetime.now(UTC),
        )
        record_audit(session, actor_id=None, action="user.password_reset", entity_id=user.id)
        session.flush()


def deactivate_user_by_email(
    session: Session,
    *,
    email: str,
    now: datetime | None = None,
) -> None:
    """Retain the privileged Phase 1 CLI deactivation through shared revocation mechanics."""
    normalized_email = normalize_email(email)
    deactivated_at = now or datetime.now(UTC)
    try:
        with session.begin():
            _deactivate_user_under_admin_authority_lock(
                session,
                normalized_email=normalized_email,
                deactivated_at=deactivated_at,
            )
    except (AdminUserNotFound, _AdminUserAlreadyInactive) as error:
        raise DeactivateUserError("deactivation refused: account unavailable") from error


def _encode_cursor_position(email: str, user_id: UUID) -> str:
    payload = json.dumps(
        {"email": email, "id": str(user_id), "version": _CURSOR_VERSION},
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
    canonical = _encode_cursor_position(position.email, position.user_id)
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
        next_cursor = (
            _encode_cursor_position(records[-1].email, records[-1].id)
            if len(users) > limit
            else None
        )
    return AdminUserPage(items=records, next_cursor=next_cursor)
