"""Preserve existing access once; refuse destructive rollback after team decisions."""

from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import select, text

from alembic import command
from tests.integration.test_translation_workspace_performance import ROOT, owned_database
from verboflex.models.product import Product
from verboflex.models.product_member import ProductMember, ProductTeamEvent
from verboflex.models.role import Role
from verboflex.models.user import User


def test_membership_upgrade_backfills_only_existing_products_and_safe_downgrade(monkeypatch):
    monkeypatch.delenv("VERBOFLEX_DATABASE_URL", raising=False)
    with owned_database() as factory:
        config = Config(ROOT / "backend/alembic.ini")
        config.set_main_option("sqlalchemy.url", str(factory.kw["bind"].url))
        command.downgrade(config, "0043_product_workspace_coverage")
        product_id = uuid4()
        identities = {}
        with factory.begin() as session:
            session.add(Product(id=product_id, display_name="Existing", name_key="existing"))
            for name in ("admin", "product_manager_reviewer", "translator", "viewer"):
                identity = uuid4()
                identities[identity] = "product_manager_reviewer" if name == "admin" else name
                session.add(
                    User(
                        id=identity,
                        email=f"{name}@example.com",
                        display_name=name,
                        hashed_password="synthetic-unused",
                        is_active=True,
                        must_change_password=False,
                        roles=[session.scalar(select(Role).where(Role.name == name))],
                    )
                )
        command.upgrade(config, "head")
        with factory.begin() as session:
            for identity, role in identities.items():
                member = session.get_one(ProductMember, (product_id, identity))
                assert member.active and member.role == role
            assert not session.scalar(
                select(ProductMember).where(ProductMember.role == "product_owner")
            )
            fresh_id = uuid4()
            session.add(Product(id=fresh_id, display_name="New", name_key="new"))
            session.flush()
            assert not session.scalar(
                select(ProductMember).where(ProductMember.product_id == fresh_id)
            )
        command.downgrade(config, "0043_product_workspace_coverage")
        command.upgrade(config, "head")
        with factory.begin() as session:
            session.add(
                ProductTeamEvent(
                    actor_id=next(iter(identities)),
                    product_id=product_id,
                    subject_id=next(iter(identities)),
                    action="member.changed",
                )
            )
        with pytest.raises(ValueError, match="product membership has activity"):
            command.downgrade(config, "0043_product_workspace_coverage")
        with factory() as session:
            assert (
                session.scalar(text("SELECT version_num FROM alembic_version"))
                == "0044_product_membership"
            )
            assert session.scalar(select(ProductTeamEvent.id)) is not None
