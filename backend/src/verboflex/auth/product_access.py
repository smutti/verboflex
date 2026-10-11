"""Current product authority; global operational roles never grant product access."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from verboflex.models.product_member import PRODUCT_ROLES, ProductMember
from verboflex.models.user import User
from verboflex.schemas.users import RoleName

OPERATIONAL_ROLES = frozenset(PRODUCT_ROLES) - {"product_owner"}


def may_manage_member(actor: str, current: str | None, requested: str | None) -> bool:
    valid = {*PRODUCT_ROLES, None}
    if current not in valid or requested not in valid:
        return False
    return actor == "admin" or (
        actor == "product_owner" and current != "product_owner" and requested != "product_owner"
    )


def current_product_role(session: Session, user_id: UUID, product_id: UUID) -> str | None:
    user = session.scalar(
        select(User)
        .where(User.id == user_id)
        .execution_options(populate_existing=True)
        .with_for_update(read=True)
    )
    if (
        user is None
        or not user.is_active
        or user.must_change_password
        or not user.roles
        or not {r.name for r in user.roles} <= set(RoleName)
    ):
        return None
    if any(role.name == "admin" for role in user.roles):
        return "admin"
    member = session.scalar(
        select(ProductMember)
        .where(
            ProductMember.user_id == user_id,
            ProductMember.product_id == product_id,
        )
        .execution_options(populate_existing=True)
        .with_for_update(read=True)
    )
    return member.role if member is not None and member.active else None


def operational_roles(role: str | None) -> tuple[RoleName, ...]:
    if role == "admin":
        return (RoleName.ADMIN,)
    if role in {"product_owner", "product_manager_reviewer"}:
        return (RoleName.PRODUCT_MANAGER_REVIEWER, RoleName.TRANSLATOR, RoleName.VIEWER)
    if role == "translator":
        return (RoleName.TRANSLATOR, RoleName.VIEWER)
    return (RoleName.VIEWER,) if role == "viewer" else ()


def product_roles(session: Session, user_id: UUID, product_id: UUID) -> tuple[RoleName, ...]:
    return operational_roles(current_product_role(session, user_id, product_id))


def visible_product_sql(product: str = "product.id", actor: str = ":principal_id") -> str:
    """Only internal SQL identifiers are accepted by callers; values remain bound."""
    return f"""EXISTS (
        SELECT 1 FROM users access_user WHERE access_user.id=CAST({actor} AS uuid)
        AND access_user.is_active AND NOT access_user.must_change_password AND (
          EXISTS (SELECT 1 FROM user_roles ur JOIN roles r ON r.id=ur.role_id
                  WHERE ur.user_id=access_user.id AND r.name='admin')
          OR EXISTS (SELECT 1 FROM product_members pm WHERE pm.user_id=access_user.id
                     AND pm.product_id={product} AND pm.active)))"""


def membership_stamp(session: Session, user_id: UUID, product_id: UUID) -> str:
    role = current_product_role(session, user_id, product_id)
    if role == "admin":
        user = session.get_one(User, user_id)
        return f"admin:{user.token_version}"
    member = session.get(ProductMember, (product_id, user_id))
    return (
        f"{member.version}:{session.get_one(User, user_id).token_version}"
        if role and member
        else "unavailable"
    )
