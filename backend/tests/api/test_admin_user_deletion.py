"""Inactive-account deletion preserves contributions and closes every authority path."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import func, select, text

from tests.api.test_admin_users import (  # noqa: F401
    ADMIN_USERS_PATH,
    admin_request,
    admin_session_factory,
    configure_admin_dependencies,
    create_authority,
    create_payload,
)
from verboflex.auth.passwords import verify_password
from verboflex.auth.rate_limits import get_redis_client
from verboflex.main import app
from verboflex.models.audit import AuditEntry
from verboflex.models.auth_session import AuthSession
from verboflex.models.glossary import GlossaryEntry
from verboflex.models.mcp_oauth import McpAuthorizationRequest, McpClient, McpGrant
from verboflex.models.product import Product
from verboflex.models.product_member import ProductMember
from verboflex.models.user import User
from verboflex.services import admin_users


class AllowedRedis:
    def eval(self, *args):
        return [1, 60]


@pytest.fixture(autouse=True)
def setup(admin_session_factory):  # noqa: F811
    app.dependency_overrides.clear()
    with admin_session_factory.begin() as session:
        session.execute(text("TRUNCATE products, users, mcp_oauth_clients, audit_entries CASCADE"))
    configure_admin_dependencies(admin_session_factory)
    app.dependency_overrides[get_redis_client] = AllowedRedis
    yield
    app.dependency_overrides.clear()
    with admin_session_factory.begin() as session:
        session.execute(text("TRUNCATE products, users, mcp_oauth_clients, audit_entries CASCADE"))


def people(factory, *, active=False):
    actor = create_authority(factory, email="admin@example.test", roles=["admin"])
    target = create_authority(
        factory, email="removed@example.com", roles=["translator"], is_active=active
    )
    return actor, target


def request_delete(token, target):
    return asyncio.run(
        admin_request("DELETE", access_token=token, path=f"{ADMIN_USERS_PATH}/{target}")
    )


def test_deletion_preserves_authored_content_scrubs_identity_and_allows_fresh_email(
    admin_session_factory,  # noqa: F811
):
    factory = admin_session_factory
    (actor_id, token), (target_id, old_token) = people(factory)
    product_id, entry_id, grant_id = uuid4(), uuid4(), uuid4()
    expiry = datetime.now(UTC) + timedelta(days=1)
    with factory.begin() as session:
        session.add(Product(id=product_id, display_name="Synthetic", name_key="synthetic"))
        session.add(
            McpClient(
                id="synthetic-client",
                name="Synthetic",
                redirect_uris=["https://example.test/callback"],
                auth_method="none",
            )
        )
        session.flush()
        session.add_all(
            [
                ProductMember(product_id=product_id, user_id=target_id, role="translator"),
                GlossaryEntry(
                    id=entry_id,
                    product_id=product_id,
                    identity_digest="a" * 64,
                    source_language="en",
                    target_language="it",
                    source_term="Save",
                    target_term="Salva",
                    created_by=target_id,
                    updated_by=target_id,
                ),
                McpGrant(
                    id=grant_id,
                    client_id="synthetic-client",
                    user_id=target_id,
                    token_version=0,
                    scope="read",
                    resource="https://example.test/mcp",
                    expires_at=expiry,
                ),
            ]
        )
        session.flush()
        session.add(
            McpAuthorizationRequest(
                id="pending-consent",
                client_id="synthetic-client",
                redirect_uri="https://example.test/callback",
                scope="read",
                resource="https://example.test/mcp",
                code_challenge="x" * 43,
                user_id=target_id,
                token_version=0,
                grant_id=grant_id,
                expires_at=expiry,
            )
        )
    response = request_delete(token, target_id)
    assert response.status_code == 204 and response.content == b""
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-ratelimit-remaining"] == "9"
    with factory() as session:
        removed = session.get_one(User, target_id)
        assert removed.deleted_at is not None and not removed.is_active
        assert removed.email == f"deleted:{target_id}" and removed.display_name == "Deleted user"
        assert not removed.roles and not removed.must_change_password
        assert removed.token_version == 1
        assert not verify_password("principal password phrase!", removed.hashed_password)
        assert all(
            row.revoked_at
            for row in session.scalars(select(AuthSession).where(AuthSession.user_id == target_id))
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(ProductMember)
                .where(ProductMember.user_id == target_id)
            )
            == 0
        )
        assert session.get_one(McpGrant, grant_id).revoked_at is not None
        assert session.get(McpAuthorizationRequest, "pending-consent") is None
        entry = session.get_one(GlossaryEntry, entry_id)
        assert (entry.source_term, entry.target_term, entry.created_by, entry.updated_by) == (
            "Save",
            "Salva",
            target_id,
            target_id,
        )
        receipt = session.scalars(
            select(AuditEntry).where(AuditEntry.action == "user.deleted")
        ).one()
        assert receipt.actor_id == actor_id and receipt.entity_id == target_id
    listed = asyncio.run(admin_request("GET", access_token=token)).json()
    assert [item["id"] for item in listed["items"]] == [str(actor_id)]
    assert request_delete(token, target_id).status_code == 404
    assert (
        asyncio.run(
            admin_request("GET", access_token=old_token, path="/api/v1/users/me")
        ).status_code
        == 401
    )
    for method, suffix, body in [
        ("PATCH", "", {"display_name": "Return", "roles": ["viewer"]}),
        ("POST", "/reactivate", None),
        ("POST", "/deactivate", None),
        ("POST", "/reset-password", None),
        ("GET", "/products", None),
    ]:
        assert (
            asyncio.run(
                admin_request(
                    method,
                    access_token=token,
                    path=f"{ADMIN_USERS_PATH}/{target_id}{suffix}",
                    json_body=body,
                )
            ).status_code
            == 404
        )
    fresh = asyncio.run(
        admin_request(
            "POST",
            access_token=token,
            json_body=create_payload("removed@example.com", roles=["viewer"]),
        )
    )
    assert fresh.status_code == 201 and fresh.json()["id"] != str(target_id)
    with factory() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(AuditEntry)
                .where(AuditEntry.action == "user.deleted")
            )
            == 1
        )
        assert session.get_one(User, target_id).token_version == 1


@pytest.mark.parametrize("roles", [["viewer"], ["translator"], ["product_manager_reviewer"]])
def test_non_admin_and_anonymous_delete_are_denied(admin_session_factory, roles):  # noqa: F811
    factory = admin_session_factory
    _, (target_id, _) = people(factory)
    _, token = create_authority(factory, email="caller@example.test", roles=roles)
    assert request_delete(token, target_id).status_code == 403
    assert request_delete(None, target_id).status_code == 401
    with factory() as session:
        assert session.get_one(User, target_id).deleted_at is None


def test_active_self_and_unknown_targets_leave_accounts_unchanged(admin_session_factory):  # noqa: F811
    factory = admin_session_factory
    (actor_id, token), (target_id, _) = people(factory, active=True)
    assert request_delete(token, target_id).status_code == 409
    assert request_delete(token, actor_id).status_code == 409
    assert request_delete(token, uuid4()).status_code == 404
    with factory() as session:
        assert session.get_one(User, actor_id).is_active
        assert session.get_one(User, target_id).deleted_at is None
        assert session.scalar(select(func.count()).select_from(AuditEntry)) == 0


@pytest.mark.parametrize("unavailable", [False, True])
def test_rate_limit_and_redis_failure_are_fail_closed(admin_session_factory, unavailable):  # noqa: F811
    (_, token), (target_id, _) = people(admin_session_factory)

    class LimitedRedis:
        def eval(self, *args):
            if unavailable:
                raise RedisConnectionError("synthetic outage")
            return [11, 39]

    app.dependency_overrides[get_redis_client] = LimitedRedis
    response = request_delete(token, target_id)
    assert response.status_code == (503 if unavailable else 429)
    if not unavailable:
        assert response.headers["retry-after"] == "39"
        assert response.headers["x-ratelimit-remaining"] == "0"
    with admin_session_factory() as session:
        assert session.get_one(User, target_id).deleted_at is None


def test_transaction_failure_rolls_back_identity_and_audit(admin_session_factory, monkeypatch):  # noqa: F811
    (_, token), (target_id, _) = people(admin_session_factory)

    def fail(*args, **kwargs):
        raise RuntimeError("synthetic revocation failure")

    monkeypatch.setattr(admin_users, "_revoke_live_sessions", fail)
    assert request_delete(token, target_id).status_code == 500
    with admin_session_factory() as session:
        user = session.get_one(User, target_id)
        assert user.email == "removed@example.com" and user.deleted_at is None and user.roles
        assert user.token_version == 0
        assert session.scalar(select(func.count()).select_from(AuditEntry)) == 0


def test_delete_and_reactivate_are_serialized(admin_session_factory):  # noqa: F811
    factory = admin_session_factory
    (actor_id, _), (target_id, _) = people(factory)
    barrier = Barrier(2)

    def attempt(action):
        barrier.wait()
        with factory() as session:
            try:
                action(session, actor_id=actor_id, target_id=target_id)
            except admin_users.AdminUserConflict, admin_users.AdminUserNotFound:
                return "refused"
        return action.__name__

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                attempt, [admin_users.delete_admin_user, admin_users.reactivate_admin_user]
            )
        )
    assert results.count("refused") == 1
    with factory() as session:
        user = session.get_one(User, target_id)
        assert user.is_active == (user.deleted_at is None)
        assert user.token_version == 1


def test_deleted_identity_cannot_be_enabled_and_migration_cannot_resurrect_it(
    admin_session_factory,  # noqa: F811
):
    from alembic.config import Config
    from sqlalchemy.exc import IntegrityError

    from alembic import command
    from tests.api.test_admin_users import BACKEND_ROOT

    factory = admin_session_factory
    (_, token), (target_id, _) = people(factory)
    assert request_delete(token, target_id).status_code == 204
    with pytest.raises(IntegrityError), factory.begin() as session:
        session.get_one(User, target_id).is_active = True
    config = Config(BACKEND_ROOT / "alembic.ini")
    config.set_main_option("sqlalchemy.url", str(factory.kw["bind"].url))
    with pytest.raises(RuntimeError, match="cannot be undone"):
        command.downgrade(config, "0050_source_fallback")
    with factory() as session:
        assert (
            session.scalar(text("SELECT version_num FROM alembic_version")) == "0051_user_deletion"
        )
        assert session.get_one(User, target_id).deleted_at is not None


def test_migration_round_trip_preserves_existing_accounts_before_any_deletion(
    admin_session_factory,  # noqa: F811
):
    from alembic.config import Config

    from alembic import command
    from tests.api.test_admin_users import BACKEND_ROOT

    factory = admin_session_factory
    (actor_id, _), (target_id, _) = people(factory)
    config = Config(BACKEND_ROOT / "alembic.ini")
    config.set_main_option("sqlalchemy.url", str(factory.kw["bind"].url))
    try:
        command.downgrade(config, "0050_source_fallback")
    finally:
        command.upgrade(config, "head")
    with factory() as session:
        assert session.get_one(User, actor_id).is_active
        target = session.get_one(User, target_id)
        assert (
            target.email == "removed@example.com"
            and target.deleted_at is None
            and not target.is_active
        )


def test_current_admin_authority_is_rechecked_inside_the_deletion_transaction(
    admin_session_factory,  # noqa: F811
):
    factory = admin_session_factory
    (actor_id, _), (target_id, _) = people(factory)
    with factory() as stale_session:
        stale_actor = stale_session.get_one(User, actor_id)
        stale_session.commit()
        with factory.begin() as session:
            session.get_one(User, actor_id).roles = []
        assert any(role.name == "admin" for role in stale_actor.roles)
        with pytest.raises(admin_users.AdminUserAuthorityError):
            admin_users.delete_admin_user(stale_session, actor_id=actor_id, target_id=target_id)
    with factory() as session:
        assert session.get_one(User, target_id).deleted_at is None
