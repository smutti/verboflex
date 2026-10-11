"""Durable metadata must be attributable, atomic and independent of sensitive bodies."""

from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import event, select

from tests.api.test_admin_products import (
    configure_dependencies,
    create_authority,
)
from tests.api.test_admin_products import (
    product_session_factory as _product_session_factory,
)
from verboflex.main import app
from verboflex.models.product import Product


@pytest.fixture(scope="module")
def product_session_factory():
    yield from _product_session_factory.__wrapped__()


def test_product_http_mutations_are_attributed_and_noops_are_not_events(product_session_factory):
    asyncio.run(_product_mutations(product_session_factory))


async def _product_mutations(product_session_factory):
    from verboflex.models.audit import AuditEntry

    factory = product_session_factory
    configure_dependencies(factory)
    actor, token = create_authority(factory, email=f"audit-{uuid4()}@example.com", roles=["admin"])
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        headers = {"Authorization": f"Bearer {token}"}
        payload = {"name": f"Audit {uuid4()}", "description": "sensitive description"}
        created = await client.post("/api/v1/admin/products", json=payload, headers=headers)
        assert created.status_code == 201
        product = created.json()
        patch = {**payload, "expected_candidate_version": product["candidate_revision"]["version"]}
        assert (
            await client.patch(
                f"/api/v1/admin/products/{product['id']}", json=patch, headers=headers
            )
        ).status_code == 200
        patch["description"] = "changed sensitive description"
        assert (
            await client.patch(
                f"/api/v1/admin/products/{product['id']}", json=patch, headers=headers
            )
        ).status_code == 200
    with factory() as session:
        events = list(
            session.scalars(
                select(AuditEntry)
                .where(AuditEntry.entity_id == UUID(product["id"]))
                .order_by(AuditEntry.occurred_at)
            )
        )
        assert [row.action for row in events] == ["product.created", "product.updated"]
        assert all(
            row.actor_id == actor and row.actor_kind == "user" and row.occurred_at.tzinfo
            for row in events
        )
        assert set(AuditEntry.__table__.columns.keys()) == {
            "id",
            "actor_id",
            "actor_kind",
            "action",
            "entity_id",
            "occurred_at",
        }


def test_audit_insert_failure_rolls_back_product_and_ledger(product_session_factory):
    from verboflex.models.audit import AuditEntry
    from verboflex.services.products import create_product

    factory = product_session_factory
    name = f"Rollback {uuid4()}"

    def reject_insert(*_args):
        raise RuntimeError("test audit unavailable")

    event.listen(AuditEntry, "before_insert", reject_insert)
    try:
        with factory() as session, pytest.raises(RuntimeError, match="test audit unavailable"):
            create_product(session, name=name, description=None, actor_id=uuid4())
    finally:
        event.remove(AuditEntry, "before_insert", reject_insert)
    with factory() as session:
        assert session.scalar(select(Product.id).where(Product.display_name == name)) is None


def test_audit_rejects_unbounded_action_and_requires_an_existing_transaction(
    product_session_factory,
):
    from verboflex.audit.ledger import record_audit

    with product_session_factory() as session:
        with pytest.raises(ValueError):
            record_audit(session, actor_id=uuid4(), action="product.created", entity_id=uuid4())
        with session.begin(), pytest.raises(ValueError):
            record_audit(
                session, actor_id=uuid4(), action="secret bearer content", entity_id=uuid4()
            )


def test_preview_audit_failure_prevents_dispatch_and_reuse_does_not_duplicate_event(
    product_session_factory,
):
    from tests.integration.test_preview_jobs import COMMIT_HASH, _seed_preview_graph
    from verboflex.models.audit import AuditEntry
    from verboflex.models.preview_job import PreviewJob
    from verboflex.services.preview_jobs import create_or_reuse_preview_job

    factory = product_session_factory
    product_id, _, _, mapping_id = _seed_preview_graph(factory)
    actor_id = uuid4()
    dispatched = []
    kwargs = dict(
        actor_id=actor_id,
        product_id=product_id,
        mapping_id=mapping_id,
        expected_candidate_version=4,
        commits={"direct": COMMIT_HASH},
        enqueuer=dispatched.append,
    )

    def reject_insert(*_args):
        raise RuntimeError("test audit unavailable")

    event.listen(AuditEntry, "before_insert", reject_insert)
    try:
        with factory() as session, pytest.raises(RuntimeError, match="test audit unavailable"):
            create_or_reuse_preview_job(session, **kwargs)
    finally:
        event.remove(AuditEntry, "before_insert", reject_insert)
    assert dispatched == []
    with factory() as session:
        assert (
            session.scalar(select(PreviewJob.id).where(PreviewJob.mapping_id == mapping_id)) is None
        )
    with factory() as session:
        job = create_or_reuse_preview_job(session, **kwargs)
    with factory() as session:
        assert create_or_reuse_preview_job(session, **kwargs).id == job.id
    assert dispatched == [job.id]
    with factory() as session:
        rows = list(session.scalars(select(AuditEntry).where(AuditEntry.entity_id == job.id)))
        assert len(rows) == 1
        assert rows[0].actor_id == actor_id and rows[0].action == "preview.requested"


def test_user_lifecycle_is_atomic_attributable_and_secret_free(product_session_factory):
    from verboflex.models.audit import AuditEntry
    from verboflex.schemas.users import RoleName
    from verboflex.services.admin_users import (
        create_admin_user,
        deactivate_admin_user,
        reactivate_admin_user,
        reset_admin_user_password,
        update_admin_user,
    )

    factory = product_session_factory
    actor, _token = create_authority(factory, email=f"owner-{uuid4()}@example.com", roles=["admin"])
    email = f"member-{uuid4()}@example.com"
    with factory() as session:
        created = create_admin_user(
            session,
            actor_id=actor,
            email=email,
            display_name="Member",
            roles=frozenset({RoleName.VIEWER}),
        )
    user_id = created.user.id
    with factory() as session:
        update_admin_user(
            session,
            actor_id=actor,
            target_id=user_id,
            display_name="Member",
            roles=frozenset({RoleName.VIEWER}),
        )
    with factory() as session:
        update_admin_user(
            session,
            actor_id=actor,
            target_id=user_id,
            display_name="Translator",
            roles=frozenset({RoleName.TRANSLATOR}),
        )
    with factory() as session:
        reset_admin_user_password(session, actor_id=actor, target_id=user_id)
    with factory() as session:
        deactivate_admin_user(session, actor_id=actor, target_id=user_id)
    with factory() as session:
        reactivate_admin_user(session, actor_id=actor, target_id=user_id)
    with factory() as session:
        rows = list(
            session.scalars(
                select(AuditEntry)
                .where(AuditEntry.entity_id == user_id)
                .order_by(AuditEntry.occurred_at)
            )
        )
        assert [row.action for row in rows] == [
            "user.created",
            "user.updated",
            "user.password_reset",
            "user.deactivated",
            "user.reactivated",
        ]
        assert all(row.actor_id == actor for row in rows)
        assert all(
            created.temporary_password not in str(row.__dict__) and email not in str(row.__dict__)
            for row in rows
        )


@pytest.mark.parametrize("restriction", ["inactive", "password_change_required"])
def test_admin_mutation_rechecks_current_authority_after_session_cached_user(
    product_session_factory, restriction
):
    from verboflex.models.user import User
    from verboflex.schemas.users import RoleName
    from verboflex.services.admin_users import AdminUserAuthorityError, create_admin_user

    factory = product_session_factory
    actor, _ = create_authority(factory, email=f"stale-{uuid4()}@example.com", roles=["admin"])
    email = f"denied-{uuid4()}@example.com"
    with factory() as stale_session:
        cached_actor = stale_session.get_one(User, actor)
        stale_session.commit()
        with factory.begin() as other_session:
            current = other_session.get_one(User, actor)
            current.is_active = restriction != "inactive"
            current.must_change_password = restriction == "password_change_required"
        assert cached_actor.is_active and not cached_actor.must_change_password
        with pytest.raises(AdminUserAuthorityError):
            create_admin_user(
                stale_session,
                actor_id=actor,
                email=email,
                display_name="Denied",
                roles=frozenset({RoleName.VIEWER}),
            )
    with factory() as session:
        assert session.scalar(select(User.id).where(User.email == email)) is None


def test_constraint_delete_leaves_only_bounded_metadata(product_session_factory):
    from tests.integration.test_translation_constraints import _seed_constraint_dataset
    from verboflex.models.audit import AuditEntry
    from verboflex.models.translation_constraint import TranslationConstraint
    from verboflex.services.translation_constraints import (
        delete_translation_constraint,
        put_translation_constraint,
    )

    factory = product_session_factory
    ids = _seed_constraint_dataset(factory)
    common = {
        "translation_group_id": ids["target_value"],
        "language": "it",
        "actor_id": ids["actor"],
    }
    with factory.begin() as session:
        created = put_translation_constraint(session, **common, max_chars=3, expected_version=0)
        rule_id = session.scalar(
            select(TranslationConstraint.id).where(
                TranslationConstraint.translation_key_id == ids["target_key"]
            )
        )
    with factory.begin() as session:
        put_translation_constraint(session, **common, max_chars=3, expected_version=created.version)
    with factory.begin() as session:
        delete_translation_constraint(session, **common, expected_version=created.version)
    with factory() as session:
        assert session.get(TranslationConstraint, rule_id) is None
        rows = list(
            session.scalars(
                select(AuditEntry)
                .where(AuditEntry.entity_id == rule_id)
                .order_by(AuditEntry.occurred_at)
            )
        )
        assert [row.action for row in rows] == ["constraint.updated", "constraint.deleted"]
        assert all(row.actor_id == ids["actor"] for row in rows)


def test_migration_roundtrip_keeps_exact_maintenance_catalog(product_session_factory):
    from alembic.config import Config
    from sqlalchemy import inspect, text

    from alembic import command
    from tests.api.test_admin_products import BACKEND_ROOT

    engine = product_session_factory.kw["bind"]
    config = Config(BACKEND_ROOT / "alembic.ini")
    config.set_main_option("sqlalchemy.url", str(engine.url))
    with engine.connect() as conn:
        before = conn.scalar(
            text("SELECT installed_definition FROM maintenance_schema WHERE name='foreign_keys'")
        )
    command.downgrade(config, "0037_mcp_maintenance_catalog")
    assert "audit_entries" not in inspect(engine).get_table_names()
    command.upgrade(config, "head")
    assert inspect(engine).get_foreign_keys("audit_entries") == []
    with engine.connect() as conn:
        assert (
            conn.scalar(
                text(
                    "SELECT installed_definition FROM maintenance_schema WHERE name='foreign_keys'"
                )
            )
            == before
        )
