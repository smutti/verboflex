"""Serialized product-team administration and one-time account provisioning."""

import secrets
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from verboflex.audit.ledger import record_audit
from verboflex.auth.identity import normalize_email
from verboflex.auth.passwords import hash_password, validate_password_for_user
from verboflex.auth.product_access import (
    current_product_role,
    may_manage_member,
    operational_roles,
)
from verboflex.models.product import Product
from verboflex.models.product_member import ProductMember, ProductTeamEvent
from verboflex.models.role import Role
from verboflex.models.user import User
from verboflex.schemas.product_team import (
    AddMemberInput,
    MemberAdded,
    MemberInput,
    ProductAccess,
    TeamMember,
    TeamResponse,
)
from verboflex.services.admin_users import _lock_admin_authority


class TeamError(ValueError):
    def __init__(self, detail: str, status: int = 409) -> None:
        super().__init__(detail)
        self.status = status


def _email(value: str) -> str:
    try:
        return normalize_email(value)
    except ValueError:
        raise TeamError("Invalid email address", 422) from None


def _product(session: Session, product_id: UUID) -> Product:
    product = session.scalar(select(Product).where(Product.id == product_id).with_for_update())
    if product is None or product.deleted_at is not None:
        raise TeamError("Product unavailable", 404)
    return product


def access(session: Session, product_id: UUID, actor_id: UUID) -> ProductAccess:
    product = session.get(Product, product_id)
    role = current_product_role(session, actor_id, product_id)
    if (
        product is None
        or product.deleted_at is not None
        or (not product.is_active and role != "admin")
    ):
        role = None
    return ProductAccess(
        role=role,
        roles=[r.value for r in operational_roles(role)],
        can_manage_team=role in {"admin", "product_owner"},
    )


def _manager(session: Session, product_id: UUID, actor_id: UUID) -> str:
    value = access(session, product_id, actor_id)
    if not value.can_manage_team or value.role is None:
        raise TeamError("Insufficient product permissions", 403)
    return value.role


def _event(
    session: Session,
    actor_id: UUID,
    product_id: UUID,
    subject_id: UUID,
    action: str,
    previous: str | None = None,
    role: str | None = None,
) -> None:
    session.add(
        ProductTeamEvent(
            actor_id=actor_id,
            product_id=product_id,
            subject_id=subject_id,
            action=action,
            previous_role=previous,
            role=role,
        )
    )


def _version(current: UUID | None, expected: UUID | None) -> None:
    if current != expected:
        raise TeamError("Team changed. Refresh before trying again.")


def _assign(
    session: Session, product_id: UUID, user: User, role: str, member: ProductMember | None
) -> ProductMember:
    if member is None:
        member = ProductMember(
            product_id=product_id, user_id=user.id, role=role, active=True, version=uuid4()
        )
        session.add(member)
    else:
        member.role, member.active, member.version = role, True, uuid4()
    return member


def set_member(session: Session, product_id: UUID, actor_id: UUID, data: MemberInput) -> None:
    _lock_admin_authority(session)
    _product(session, product_id)
    actor_role = _manager(session, product_id, actor_id)
    user = session.scalar(select(User).where(User.email == _email(data.email)).with_for_update())
    if user is None or not user.is_active:
        raise TeamError("Active account required. Add a collaborator to create a new account.")
    member = session.get(ProductMember, (product_id, user.id), populate_existing=True)
    previous = member.role if member and member.active else None
    if actor_role != "admin" and any(r.name == "admin" for r in user.roles):
        raise TeamError("Only administrators may change administrator membership", 403)
    if not may_manage_member(actor_role, previous, data.role) or (
        actor_role != "admin" and previous is None
    ):
        raise TeamError("This membership can only be changed by an administrator", 403)
    _version(member.version if member and member.active else None, data.expected_version)
    if previous == data.role:
        return
    _assign(session, product_id, user, data.role, member)
    _event(session, actor_id, product_id, user.id, "member.changed", previous, data.role)


def remove_member(
    session: Session, product_id: UUID, actor_id: UUID, user_id: UUID, version: UUID
) -> None:
    _lock_admin_authority(session)
    _product(session, product_id)
    actor_role = _manager(session, product_id, actor_id)
    member = session.get(ProductMember, (product_id, user_id), populate_existing=True)
    if member is None or not member.active:
        raise TeamError("Membership unavailable", 404)
    if not may_manage_member(actor_role, member.role, None):
        raise TeamError("Only administrators may remove product owners", 403)
    user = session.get_one(User, user_id)
    if actor_role != "admin" and any(r.name == "admin" for r in user.roles):
        raise TeamError("Only administrators may change administrator membership", 403)
    _version(member.version, version)
    previous = member.role
    member.active, member.version = False, uuid4()
    _event(session, actor_id, product_id, user_id, "member.removed", previous)


def _new_account(session: Session, email: str, display_name: str) -> tuple[User, str]:
    name = display_name.strip()
    if not name or "\x00" in name:
        raise TeamError("Display name is required", 422)
    viewer = session.scalar(select(Role).where(Role.name == "viewer"))
    if viewer is None:
        raise TeamError("Account setup unavailable", 503)
    password = secrets.token_urlsafe(24)
    validate_password_for_user(password, normalized_email=email)
    user = User(
        email=email,
        display_name=name,
        hashed_password=hash_password(password),
        is_active=True,
        must_change_password=True,
        token_version=0,
        roles=[viewer],
    )
    session.add(user)
    session.flush()
    return user, password


def add_member(
    session: Session, product_id: UUID, actor_id: UUID, data: AddMemberInput
) -> MemberAdded:
    """Add an active account, provisioning a new identity only when absent."""
    _lock_admin_authority(session)
    product = _product(session, product_id)
    actor_role = _manager(session, product_id, actor_id)
    if not product.is_active:
        raise TeamError("Activate the product before adding collaborators")
    email = _email(data.email)
    user = session.scalar(select(User).where(User.email == email).with_for_update())
    member = session.get(ProductMember, (product_id, user.id)) if user is not None else None
    if user is not None and not user.is_active:
        raise TeamError("Account disabled. Contact an administrator.")
    if user is not None and actor_role != "admin" and any(r.name == "admin" for r in user.roles):
        raise TeamError("Only administrators may change administrator membership", 403)
    if member is not None and member.active:
        raise TeamError("Already a member. Use the team list to change their role.")
    if not may_manage_member(actor_role, None, data.role):
        raise TeamError("Only administrators may appoint product owners", 403)
    password = None
    if user is None:
        user, password = _new_account(session, email, data.display_name)
        record_audit(session, actor_id=actor_id, action="user.created", entity_id=user.id)
    _assign(session, product_id, user, data.role, member)
    _event(session, actor_id, product_id, user.id, "member.added", role=data.role)
    return MemberAdded(
        user_id=user.id,
        email=user.email,
        account_created=password is not None,
        temporary_password=password,
    )


def team(session: Session, product_id: UUID, actor_id: UUID) -> TeamResponse:
    _manager(session, product_id, actor_id)
    members = [
        TeamMember(
            user_id=u.id,
            email=u.email,
            display_name=u.display_name,
            role=m.role,
            version=m.version,
            account_active=u.is_active,
        )
        for m, u in session.execute(
            select(ProductMember, User)
            .join(User, User.id == ProductMember.user_id)
            .where(ProductMember.product_id == product_id, ProductMember.active)
            .order_by(User.email)
        )
    ]
    return TeamResponse(
        access=access(session, product_id, actor_id),
        members=members,
        has_active_owner=any(m.role == "product_owner" and m.account_active for m in members),
    )
