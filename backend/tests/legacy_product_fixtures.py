"""Explicit memberships for pre-membership shared-product test factories.

Opt-in only: legacy fixtures model staff sharing every product. When those fixtures
insert users/products, seed the equivalent memberships. Never change memberships
on updates or overwrite a revoked membership. New isolation/invitation tests do
not opt in and must construct every grant explicitly.
"""

from sqlalchemy import event, text
from sqlalchemy.orm import Session, sessionmaker

from verboflex.models.product import Product
from verboflex.models.user import User


def shared_product_fixture(factory: sessionmaker[Session]) -> None:
    def remember(session: Session, _context: object, _instances: object) -> None:
        session.info["seed_shared_memberships"] = any(
            isinstance(row, (User, Product)) for row in session.new
        )

    def seed(session: Session, _context: object) -> None:
        if not session.info.pop("seed_shared_memberships", False):
            return
        if session.scalar(text("SELECT to_regclass('public.product_members')")) is None:
            return  # Historical migration fixtures intentionally use earlier schemas.
        session.execute(
            text("""
            INSERT INTO product_members(product_id,user_id,role,active,version)
            SELECT p.id,u.id, CASE
              WHEN EXISTS(SELECT 1 FROM user_roles ur JOIN roles r ON r.id=ur.role_id
                  WHERE ur.user_id=u.id AND r.name IN ('admin','product_manager_reviewer'))
                THEN 'product_manager_reviewer'
              WHEN EXISTS(SELECT 1 FROM user_roles ur JOIN roles r ON r.id=ur.role_id
                  WHERE ur.user_id=u.id AND r.name='translator') THEN 'translator'
              ELSE 'viewer' END, true, gen_random_uuid()
            FROM users u CROSS JOIN products p WHERE p.deleted_at IS NULL
            ON CONFLICT (product_id,user_id) DO NOTHING
        """)
        )

    event.listen(factory, "before_flush", remember)
    event.listen(factory, "after_flush_postexec", seed)


def shared_reader(factory: sessionmaker[Session], identity=None):
    """Persist the synthetic reader previously represented only by a cursor UUID."""
    from uuid import uuid4

    from sqlalchemy import select

    from verboflex.models.product_member import ProductMember
    from verboflex.models.role import Role

    identity = identity or uuid4()
    with factory.begin() as session:
        if session.get(User, identity) is None:
            session.add(
                User(
                    id=identity,
                    email=f"reader-{identity}@example.com",
                    display_name="Synthetic reader",
                    hashed_password="synthetic-unused-hash",
                    is_active=True,
                    must_change_password=False,
                    roles=list(session.scalars(select(Role).where(Role.name == "viewer"))),
                )
            )
            session.flush()
        for product_id in session.scalars(select(Product.id)):
            if session.get(ProductMember, (product_id, identity)) is None:
                session.add(ProductMember(product_id=product_id, user_id=identity, role="viewer"))
    return identity


def mirror_fixture_role(session: Session, user_id):
    """Role-changing legacy scenarios now explicitly change product authority too."""
    from uuid import uuid4

    from sqlalchemy import select

    from verboflex.models.product_member import ProductMember

    user = session.get_one(User, user_id)
    roles = {r.name for r in user.roles}
    role = next(
        (r for r in ("product_manager_reviewer", "translator", "viewer") if r in roles), "viewer"
    )
    for product_id in session.scalars(select(Product.id)):
        member = session.get(ProductMember, (product_id, user_id))
        if member is None:
            member = ProductMember(product_id=product_id, user_id=user_id)
            session.add(member)
        member.role, member.active, member.version = role, bool(roles), uuid4()
