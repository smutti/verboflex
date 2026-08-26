"""Administrator-only HTTP contracts for internal user creation and listing."""

from __future__ import annotations

import asyncio
import json
import os
import secrets
from collections.abc import Generator, Iterator, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from alembic.config import Config
from psycopg import connect, sql
from pydantic import SecretStr
from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from verboflex.auth.access_tokens import issue_access_token
from verboflex.auth.passwords import hash_password, verify_password
from verboflex.core.config import Settings, get_settings
from verboflex.db.session import get_db_session
from verboflex.main import app
from verboflex.models.auth_session import AuthSession
from verboflex.models.role import Role
from verboflex.models.user import User

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ADMIN_DATABASE_URL = os.environ.get(
    "VERBOFLEX_TEST_POSTGRES_ADMIN_URL",
    "postgresql://postgres@127.0.0.1:55432/postgres",
)
SIGNING_SECRET = "0123456789abcdef" * 2
ADMIN_USERS_PATH = "/api/v1/admin/users"
FIXED_ROLE_ORDER = (
    "admin",
    "product_manager_reviewer",
    "translator",
    "viewer",
)


@pytest.fixture(scope="module")
def admin_session_factory() -> Iterator[sessionmaker[Session]]:
    """Migrate one isolated PostgreSQL database for the focused API contract."""
    database_name = f"verboflex_admin_users_{uuid4().hex}"
    with connect(ADMIN_DATABASE_URL, autocommit=True) as admin_connection:
        admin_connection.execute(
            sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name))
        )
    database_url = ADMIN_DATABASE_URL.rsplit("/", 1)[0] + f"/{database_name}"
    sqlalchemy_url = database_url.replace("postgresql://", "postgresql+psycopg://")
    config = Config(BACKEND_ROOT / "alembic.ini")
    config.set_main_option("sqlalchemy.url", sqlalchemy_url)
    engine = create_engine(sqlalchemy_url)
    command.upgrade(config, "head")
    factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)

    try:
        yield factory
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
        with connect(ADMIN_DATABASE_URL, autocommit=True) as admin_connection:
            admin_connection.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database_name))
            )


@pytest.fixture(autouse=True)
def clean_admin_users_database(
    admin_session_factory: sessionmaker[Session],
) -> Iterator[None]:
    """Keep every test independent while retaining the fixed seeded roles."""
    app.dependency_overrides.clear()
    with admin_session_factory.begin() as session:
        session.execute(delete(AuthSession))
        session.execute(delete(User))
    yield
    app.dependency_overrides.clear()
    with admin_session_factory.begin() as session:
        session.execute(delete(AuthSession))
        session.execute(delete(User))


def admin_settings() -> Settings:
    """Return explicit signing settings independent from ambient secrets."""
    return Settings(jwt_secret_key=SecretStr(SIGNING_SECRET))


def configure_admin_dependencies(factory: sessionmaker[Session]) -> None:
    """Wire principal and route sessions to the isolated database."""

    def override_session() -> Generator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_settings] = admin_settings


def create_authority(
    factory: sessionmaker[Session],
    *,
    email: str,
    roles: Sequence[str],
    is_active: bool = True,
    revoked: bool = False,
    expired: bool = False,
) -> tuple[UUID, str]:
    """Persist one principal and return an ordinary access token for its session."""
    user_id = uuid4()
    auth_session_id = uuid4()
    now = datetime.now(UTC)
    with factory.begin() as session:
        durable_roles = list(session.execute(select(Role).where(Role.name.in_(roles))).scalars())
        user = User(
            id=user_id,
            email=email,
            display_name=email.split("@", 1)[0].replace(".", " ").title(),
            hashed_password=hash_password("principal password phrase!"),
            is_active=is_active,
            must_change_password=False,
            roles=durable_roles,
        )
        session.add(user)
        session.add(
            AuthSession(
                id=auth_session_id,
                user_id=user_id,
                family_id=uuid4(),
                token_hash=uuid4().hex + uuid4().hex,
                revoked_at=now if revoked else None,
                expires_at=now - timedelta(seconds=1) if expired else now + timedelta(days=7),
            )
        )
    return user_id, issue_access_token(
        user_id=user_id,
        session_id=auth_session_id,
        token_version=0,
        purpose="access",
        settings=admin_settings(),
        now=now,
    )


async def admin_request(
    method: str,
    *,
    access_token: str | None,
    path: str = ADMIN_USERS_PATH,
    json_body: dict[str, object] | None = None,
) -> httpx.Response:
    """Call an admin-user route through the registered ASGI boundary."""
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    headers = {"Authorization": f"Bearer {access_token}"} if access_token else None
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, headers=headers, json=json_body)


def create_payload(
    email: str = "person@example.com",
    *,
    roles: Sequence[str] = FIXED_ROLE_ORDER,
) -> dict[str, object]:
    """Return one valid create request using an arbitrary non-empty role set."""
    return {
        "email": email,
        "display_name": "Person Example",
        "roles": list(roles),
    }


def test_active_admin_creates_user_and_receives_one_non_persistent_temporary_password(
    admin_session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Create a UUID identity while exposing plaintext only in the successful response."""
    _admin_id, admin_token = create_authority(
        admin_session_factory,
        email="admin@example.com",
        roles=("admin",),
    )
    generated_password = "A1-safe-temporary-password-value"
    token_urlsafe_calls: list[int] = []

    def fixed_token_urlsafe(byte_count: int) -> str:
        token_urlsafe_calls.append(byte_count)
        return generated_password

    monkeypatch.setattr(secrets, "token_urlsafe", fixed_token_urlsafe)
    configure_admin_dependencies(admin_session_factory)

    response = asyncio.run(
        admin_request(
            "POST",
            access_token=admin_token,
            json_body=create_payload(email=" PERSON@EXAMPLE.COM "),
        )
    )

    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    assert token_urlsafe_calls == [24]
    assert response.json() == {
        "id": response.json()["id"],
        "email": "person@example.com",
        "display_name": "Person Example",
        "roles": list(FIXED_ROLE_ORDER),
        "is_active": True,
        "must_change_password": True,
        "temporary_password": generated_password,
    }
    created_id = UUID(response.json()["id"])
    with admin_session_factory() as session:
        created = session.get_one(User, created_id)
        assert created.email == "person@example.com"
        assert created.hashed_password != generated_password
        assert verify_password(generated_password, created.hashed_password) is True
        assert created.must_change_password is True
        assert created.is_active is True
        assert created.token_version == 0
        assert [role.name for role in created.roles] == list(FIXED_ROLE_ORDER)
        durable_snapshot = {
            "id": str(created.id),
            "email": created.email,
            "display_name": created.display_name,
            "hashed_password": created.hashed_password,
        }
        assert generated_password not in json.dumps(durable_snapshot)

    listed = asyncio.run(admin_request("GET", access_token=admin_token))
    assert listed.status_code == 200
    serialized_list = listed.text
    assert generated_password not in serialized_list
    assert "hashed_password" not in serialized_list
    assert listed.json()["items"][1] == {
        "id": str(created_id),
        "email": "person@example.com",
        "display_name": "Person Example",
        "roles": list(FIXED_ROLE_ORDER),
        "is_active": True,
        "must_change_password": True,
    }
    assert generated_password not in caplog.text

    schemas = app.openapi()["components"]["schemas"]
    assert "hashed_password" not in json.dumps(schemas)
    assert "temporary_password" not in schemas["AdminUserResponse"]["properties"]
    assert "temporary_password" not in schemas["AdminUserListResponse"]["properties"]
    credential_schema = schemas["AdminUserCredentialResponse"]
    assert "temporary_password" in credential_schema["properties"]
    assert "example" not in credential_schema["properties"]["temporary_password"]
    assert "default" not in credential_schema["properties"]["temporary_password"]


def test_every_non_admin_or_non_current_principal_is_denied_without_mutation(
    admin_session_factory: sessionmaker[Session],
) -> None:
    """Reject missing, invalid, non-admin, inactive, expired, and revoked authority."""
    principals = {
        "non-admin": create_authority(
            admin_session_factory,
            email="viewer@example.com",
            roles=("viewer",),
        )[1],
        "inactive": create_authority(
            admin_session_factory,
            email="inactive@example.com",
            roles=("admin",),
            is_active=False,
        )[1],
        "expired": create_authority(
            admin_session_factory,
            email="expired@example.com",
            roles=("admin",),
            expired=True,
        )[1],
        "revoked": create_authority(
            admin_session_factory,
            email="revoked@example.com",
            roles=("admin",),
            revoked=True,
        )[1],
        "invalid": "not-a-signed-token",
        "missing": None,
    }
    with admin_session_factory() as session:
        users_before = session.scalar(select(func.count()).select_from(User))
    configure_admin_dependencies(admin_session_factory)

    responses = {
        name: asyncio.run(
            admin_request(
                "POST",
                access_token=token,
                json_body=create_payload(email=f"created-by-{name}@example.com"),
            )
        )
        for name, token in principals.items()
    }

    assert responses["non-admin"].status_code == 403
    assert responses["non-admin"].json() == {"detail": "Insufficient permissions"}
    for name in ("inactive", "expired", "revoked", "invalid", "missing"):
        assert responses[name].status_code == 401
        assert responses[name].json() == {"detail": "Invalid access token"}
        assert responses[name].headers["www-authenticate"] == "Bearer"
    with admin_session_factory() as session:
        assert session.scalar(select(func.count()).select_from(User)) == users_before


def test_duplicate_normalized_email_conflicts_without_enumeration_or_secret(
    admin_session_factory: sessionmaker[Session],
) -> None:
    """Map one duplicate identity to a bounded conflict and preserve durable state."""
    _admin_id, admin_token = create_authority(
        admin_session_factory,
        email="admin@example.com",
        roles=("admin",),
    )
    configure_admin_dependencies(admin_session_factory)
    first = asyncio.run(
        admin_request(
            "POST",
            access_token=admin_token,
            json_body=create_payload(email="person@example.com", roles=("viewer",)),
        )
    )
    assert first.status_code == 201

    duplicate = asyncio.run(
        admin_request(
            "POST",
            access_token=admin_token,
            json_body=create_payload(email=" PERSON@EXAMPLE.COM ", roles=("admin",)),
        )
    )

    assert duplicate.status_code == 409
    assert duplicate.json() == {"detail": "User could not be created"}
    assert "temporary_password" not in duplicate.text
    assert "person@example.com" not in duplicate.text
    with admin_session_factory() as session:
        assert session.scalar(select(func.count()).select_from(User)) == 2


@pytest.mark.parametrize(
    "roles",
    [[], ["owner"], ["admin", "owner"]],
)
def test_role_input_must_be_a_non_empty_subset_of_the_fixed_vocabulary(
    admin_session_factory: sessionmaker[Session],
    roles: list[str],
) -> None:
    """Reject empty or unsupported authority sets before persistence."""
    _admin_id, admin_token = create_authority(
        admin_session_factory,
        email="admin@example.com",
        roles=("admin",),
    )
    configure_admin_dependencies(admin_session_factory)

    response = asyncio.run(
        admin_request(
            "POST",
            access_token=admin_token,
            json_body=create_payload(roles=roles),
        )
    )

    assert response.status_code == 422
    assert "temporary_password" not in response.text
    with admin_session_factory() as session:
        assert session.scalar(select(func.count()).select_from(User)) == 1


def test_user_list_has_stable_opaque_default_and_maximum_pagination(
    admin_session_factory: sessionmaker[Session],
) -> None:
    """Page deterministic email/UUID order with default 50 and maximum 100."""
    _admin_id, admin_token = create_authority(
        admin_session_factory,
        email="admin@example.com",
        roles=("admin",),
    )
    shared_hash = hash_password("seeded pagination password!")
    with admin_session_factory.begin() as session:
        viewer = session.execute(select(Role).where(Role.name == "viewer")).scalar_one()
        session.add_all(
            User(
                email=f"person-{index:03d}@example.com",
                display_name=f"Person {index:03d}",
                hashed_password=shared_hash,
                must_change_password=True,
                roles=[viewer],
            )
            for index in range(105)
        )
    configure_admin_dependencies(admin_session_factory)

    first = asyncio.run(admin_request("GET", access_token=admin_token))
    assert first.status_code == 200
    assert len(first.json()["items"]) == 50
    cursor = first.json()["next_cursor"]
    assert isinstance(cursor, str) and cursor
    assert "@" not in cursor

    second = asyncio.run(
        admin_request(
            "GET",
            access_token=admin_token,
            path=f"{ADMIN_USERS_PATH}?cursor={cursor}",
        )
    )
    third_cursor = second.json()["next_cursor"]
    third = asyncio.run(
        admin_request(
            "GET",
            access_token=admin_token,
            path=f"{ADMIN_USERS_PATH}?cursor={third_cursor}",
        )
    )
    all_items = first.json()["items"] + second.json()["items"] + third.json()["items"]
    identities = [(item["email"], item["id"]) for item in all_items]
    assert len(first.json()["items"]) == 50
    assert len(second.json()["items"]) == 50
    assert len(third.json()["items"]) == 6
    assert third.json()["next_cursor"] is None
    assert identities == sorted(identities)
    assert len(set(identities)) == 106

    maximum = asyncio.run(
        admin_request(
            "GET",
            access_token=admin_token,
            path=f"{ADMIN_USERS_PATH}?limit=100",
        )
    )
    assert maximum.status_code == 200
    assert len(maximum.json()["items"]) == 100
    assert maximum.json()["next_cursor"]

    over_limit = asyncio.run(
        admin_request(
            "GET",
            access_token=admin_token,
            path=f"{ADMIN_USERS_PATH}?limit=101",
        )
    )
    invalid_cursor = asyncio.run(
        admin_request(
            "GET",
            access_token=admin_token,
            path=f"{ADMIN_USERS_PATH}?cursor=not-a-valid-cursor",
        )
    )
    assert over_limit.status_code == 422
    assert invalid_cursor.status_code == 422
    assert invalid_cursor.json() == {"detail": "Invalid cursor"}


def _authority_snapshot(factory: sessionmaker[Session]) -> list[tuple[object, ...]]:
    """Capture every mutable user authority field for rejection assertions."""
    with factory() as session:
        users = list(session.execute(select(User).order_by(User.email)).scalars())
        return [
            (
                user.id,
                user.email,
                user.display_name,
                tuple(role.name for role in user.roles),
                user.is_active,
                user.must_change_password,
                user.token_version,
                user.hashed_password,
            )
            for user in users
        ]


def test_every_admin_user_endpoint_uses_the_same_bearer_and_admin_guard_without_mutation(
    admin_session_factory: sessionmaker[Session],
) -> None:
    """List, create, update, reset, deactivate, and reactivate all fail closed."""
    _admin_id, _admin_token = create_authority(
        admin_session_factory,
        email="admin@example.com",
        roles=("admin",),
    )
    _viewer_id, viewer_token = create_authority(
        admin_session_factory,
        email="viewer@example.com",
        roles=("viewer",),
    )
    target_id, _target_token = create_authority(
        admin_session_factory,
        email="target@example.com",
        roles=("translator",),
    )
    configure_admin_dependencies(admin_session_factory)
    before = _authority_snapshot(admin_session_factory)
    operations = (
        ("GET", ADMIN_USERS_PATH, None),
        ("POST", ADMIN_USERS_PATH, create_payload(email="new@example.com")),
        (
            "PATCH",
            f"{ADMIN_USERS_PATH}/{target_id}",
            {"display_name": "Changed", "roles": ["viewer"]},
        ),
        ("POST", f"{ADMIN_USERS_PATH}/{target_id}/reset-password", None),
        ("POST", f"{ADMIN_USERS_PATH}/{target_id}/deactivate", None),
        ("POST", f"{ADMIN_USERS_PATH}/{target_id}/reactivate", None),
    )

    for method, path, body in operations:
        for token, expected_status in ((None, 401), ("invalid-token", 401), (viewer_token, 403)):
            response = asyncio.run(
                admin_request(
                    method,
                    access_token=token,
                    path=path,
                    json_body=body,
                )
            )
            assert response.status_code == expected_status
            assert "temporary_password" not in response.text

    assert _authority_snapshot(admin_session_factory) == before


def test_admin_updates_roles_then_resets_deactivates_and_reactivates_one_identity(
    admin_session_factory: sessionmaker[Session],
) -> None:
    """The complete lifecycle preserves UUID and reveals secrets only on reset/reactivate."""
    _admin_id, admin_token = create_authority(
        admin_session_factory,
        email="admin@example.com",
        roles=("admin",),
    )
    target_id, _target_token = create_authority(
        admin_session_factory,
        email="target@example.com",
        roles=("viewer",),
    )
    configure_admin_dependencies(admin_session_factory)

    updated = asyncio.run(
        admin_request(
            "PATCH",
            access_token=admin_token,
            path=f"{ADMIN_USERS_PATH}/{target_id}",
            json_body={
                "display_name": "  Target Person  ",
                "roles": ["viewer", "translator", "viewer"],
            },
        )
    )
    assert updated.status_code == 200
    assert updated.json() == {
        "id": str(target_id),
        "email": "target@example.com",
        "display_name": "Target Person",
        "roles": ["translator", "viewer"],
        "is_active": True,
        "must_change_password": False,
    }
    assert "temporary_password" not in updated.text

    reset = asyncio.run(
        admin_request(
            "POST",
            access_token=admin_token,
            path=f"{ADMIN_USERS_PATH}/{target_id}/reset-password",
        )
    )
    assert reset.status_code == 200
    assert reset.headers["cache-control"] == "no-store"
    reset_secret = reset.json()["temporary_password"]

    deactivated = asyncio.run(
        admin_request(
            "POST",
            access_token=admin_token,
            path=f"{ADMIN_USERS_PATH}/{target_id}/deactivate",
        )
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["id"] == str(target_id)
    assert deactivated.json()["is_active"] is False
    assert "temporary_password" not in deactivated.text

    reactivated = asyncio.run(
        admin_request(
            "POST",
            access_token=admin_token,
            path=f"{ADMIN_USERS_PATH}/{target_id}/reactivate",
        )
    )
    assert reactivated.status_code == 200
    assert reactivated.headers["cache-control"] == "no-store"
    reactivation_secret = reactivated.json()["temporary_password"]
    assert reactivation_secret != reset_secret
    assert reactivated.json()["id"] == str(target_id)
    assert reactivated.json()["is_active"] is True
    assert reactivated.json()["must_change_password"] is True

    listed = asyncio.run(admin_request("GET", access_token=admin_token))
    serialized = listed.text
    assert reset_secret not in serialized
    assert reactivation_secret not in serialized
    with admin_session_factory() as session:
        target = session.get_one(User, target_id)
        assert target.id == target_id
        assert target.email == "target@example.com"
        assert target.token_version == 4
        assert verify_password(reactivation_secret, target.hashed_password) is True
        assert verify_password(reset_secret, target.hashed_password) is False
        assert all(
            item.revoked_at is not None
            for item in session.execute(
                select(AuthSession).where(AuthSession.user_id == target_id)
            ).scalars()
        )


def test_user_update_rejects_email_changes_empty_roles_and_self_admin_removal(
    admin_session_factory: sessionmaker[Session],
) -> None:
    """The PATCH surface exposes only mutable fields and preserves admin invariants."""
    admin_id, admin_token = create_authority(
        admin_session_factory,
        email="admin@example.com",
        roles=("admin", "viewer"),
    )
    configure_admin_dependencies(admin_session_factory)
    before = _authority_snapshot(admin_session_factory)

    email_change = asyncio.run(
        admin_request(
            "PATCH",
            access_token=admin_token,
            path=f"{ADMIN_USERS_PATH}/{admin_id}",
            json_body={
                "email": "changed@example.com",
                "display_name": "Admin",
                "roles": ["admin"],
            },
        )
    )
    empty_roles = asyncio.run(
        admin_request(
            "PATCH",
            access_token=admin_token,
            path=f"{ADMIN_USERS_PATH}/{admin_id}",
            json_body={"display_name": "Admin", "roles": []},
        )
    )
    self_removal = asyncio.run(
        admin_request(
            "PATCH",
            access_token=admin_token,
            path=f"{ADMIN_USERS_PATH}/{admin_id}",
            json_body={"display_name": "Admin", "roles": ["viewer"]},
        )
    )
    self_deactivation = asyncio.run(
        admin_request(
            "POST",
            access_token=admin_token,
            path=f"{ADMIN_USERS_PATH}/{admin_id}/deactivate",
        )
    )

    assert email_change.status_code == 422
    assert empty_roles.status_code == 422
    assert self_removal.status_code == 409
    assert self_deactivation.status_code == 409
    for response in (email_change, empty_roles, self_removal, self_deactivation):
        assert "temporary_password" not in response.text
    assert _authority_snapshot(admin_session_factory) == before


def test_invalid_lifecycle_transitions_and_unknown_users_are_bounded_and_non_mutating(
    admin_session_factory: sessionmaker[Session],
) -> None:
    """Active reactivate, repeated deactivate, and unknown UUIDs return bounded conflicts."""
    _admin_id, admin_token = create_authority(
        admin_session_factory,
        email="admin@example.com",
        roles=("admin",),
    )
    target_id, _target_token = create_authority(
        admin_session_factory,
        email="target@example.com",
        roles=("viewer",),
    )
    configure_admin_dependencies(admin_session_factory)

    active_reactivation = asyncio.run(
        admin_request(
            "POST",
            access_token=admin_token,
            path=f"{ADMIN_USERS_PATH}/{target_id}/reactivate",
        )
    )
    assert active_reactivation.status_code == 409
    assert "temporary_password" not in active_reactivation.text

    first_deactivation = asyncio.run(
        admin_request(
            "POST",
            access_token=admin_token,
            path=f"{ADMIN_USERS_PATH}/{target_id}/deactivate",
        )
    )
    assert first_deactivation.status_code == 200
    after_first = _authority_snapshot(admin_session_factory)
    repeated_deactivation = asyncio.run(
        admin_request(
            "POST",
            access_token=admin_token,
            path=f"{ADMIN_USERS_PATH}/{target_id}/deactivate",
        )
    )
    unknown = asyncio.run(
        admin_request(
            "POST",
            access_token=admin_token,
            path=f"{ADMIN_USERS_PATH}/{uuid4()}/reset-password",
        )
    )
    assert repeated_deactivation.status_code == 409
    assert unknown.status_code == 404
    assert "temporary_password" not in repeated_deactivation.text
    assert "temporary_password" not in unknown.text
    assert _authority_snapshot(admin_session_factory) == after_first
