"""HTTP contracts for the authenticated current-identity projection."""

import asyncio
import os
from collections.abc import Generator, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import jwt
import pytest
from alembic.config import Config
from psycopg import connect, sql
from pydantic import SecretStr
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from verboflex.auth import principal as principal_service
from verboflex.auth.access_tokens import issue_access_token
from verboflex.auth.passwords import hash_password
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
USER_ID = UUID("00000000-0000-4000-8000-000000000101")
SESSION_ID = UUID("00000000-0000-4000-8000-000000000201")


@pytest.fixture
def principal_session_factory() -> Iterator[sessionmaker[Session]]:
    """Migrate one isolated PostgreSQL database for principal resolution."""
    database_name = f"verboflex_principal_{uuid4().hex}"
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


def principal_settings() -> Settings:
    """Return explicit signing settings independent from ambient env."""
    return Settings(
        jwt_secret_key=SecretStr(SIGNING_SECRET),
        refresh_cookie_secure=False,
    )


def configure_principal_dependencies(factory: sessionmaker[Session]) -> None:
    """Wire the protected route to its isolated PostgreSQL database."""

    def override_session() -> Generator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_settings] = principal_settings


def create_principal_authority(factory: sessionmaker[Session]) -> str:
    """Persist current authority and return its signed ordinary bearer token."""
    with factory.begin() as session:
        roles = session.execute(
            select(Role).where(Role.name.in_(("translator", "admin")))
        ).scalars()
        user = User(
            id=USER_ID,
            email="person@example.com",
            display_name="Person Example",
            hashed_password=hash_password("principal password phrase!"),
            must_change_password=False,
            roles=list(roles),
        )
        session.add(user)
        session.add(
            AuthSession(
                id=SESSION_ID,
                user_id=USER_ID,
                family_id=uuid4(),
                token_hash="f" * 64,
                expires_at=datetime.now(UTC) + timedelta(days=7),
            )
        )
    return issue_access_token(
        user_id=USER_ID,
        session_id=SESSION_ID,
        token_version=0,
        purpose="access",
        settings=principal_settings(),
    )


async def get_me(access_token: str | None) -> httpx.Response:
    """Call the registered protected route through the ASGI boundary."""
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {access_token}"} if access_token is not None else None
        return await client.get(
            "/api/v1/users/me",
            headers=headers,
        )


def test_current_identity_returns_only_the_safe_provider_independent_projection(
    principal_session_factory: sessionmaker[Session],
) -> None:
    """Return exact own identity and sorted stable roles without persistence fields."""
    access_token = create_principal_authority(principal_session_factory)
    configure_principal_dependencies(principal_session_factory)

    response = asyncio.run(get_me(access_token))

    assert response.status_code == 200
    assert response.json() == {
        "id": "00000000-0000-4000-8000-000000000101",
        "email": "person@example.com",
        "display_name": "Person Example",
        "roles": ["admin", "translator"],
        "must_change_password": False,
    }


@pytest.mark.parametrize("access_token", [None, "not-a-signed-jwt"])
def test_missing_or_invalid_bearer_authority_returns_exact_401(
    principal_session_factory: sessionmaker[Session],
    access_token: str | None,
) -> None:
    """Reject absent and malformed authority through one non-sensitive surface."""
    configure_principal_dependencies(principal_session_factory)

    response = asyncio.run(get_me(access_token))

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid access token"}
    assert response.headers["www-authenticate"] == "Bearer"


def test_principal_service_denials_preserve_exact_internal_semantics(
    principal_session_factory: sessionmaker[Session],
) -> None:
    """Keep absent bearer, invalid signature, user, and session failures exact."""
    with pytest.raises(principal_service.InvalidPrincipal) as user_error:
        principal_service._require_current_user(None, token_version=0)
    assert user_error.value.args == (principal_service.INVALID_PRINCIPAL_MESSAGE,)

    now = datetime.now(UTC)
    with pytest.raises(principal_service.InvalidPrincipal) as missing_session_error:
        principal_service._require_current_session(None, user_id=USER_ID, now=now)
    assert missing_session_error.value.args == (principal_service.INVALID_PRINCIPAL_MESSAGE,)

    mismatched_session = AuthSession(
        id=SESSION_ID,
        user_id=uuid4(),
        family_id=uuid4(),
        token_hash="m" * 64,
        expires_at=now + timedelta(minutes=15),
    )
    with pytest.raises(principal_service.InvalidPrincipal) as mismatched_session_error:
        principal_service._require_current_session(
            mismatched_session,
            user_id=USER_ID,
            now=now,
        )
    assert mismatched_session_error.value.args == (
        principal_service.INVALID_PRINCIPAL_MESSAGE,
    )

    dead_session = AuthSession(
        id=SESSION_ID,
        user_id=USER_ID,
        family_id=uuid4(),
        token_hash="d" * 64,
        expires_at=now,
    )
    with pytest.raises(principal_service.InvalidPrincipal) as dead_session_error:
        principal_service._require_current_session(dead_session, user_id=USER_ID, now=now)
    assert dead_session_error.value.args == (principal_service.INVALID_PRINCIPAL_MESSAGE,)

    with principal_session_factory() as session:
        with pytest.raises(principal_service.InvalidPrincipal) as missing_bearer_error:
            principal_service.load_principal(session, None, settings=principal_settings())
        with pytest.raises(principal_service.InvalidPrincipal) as invalid_bearer_error:
            principal_service.load_principal(
                session,
                "not-a-signed-token",
                settings=principal_settings(),
            )
    assert missing_bearer_error.value.args == (principal_service.MISSING_ACCESS_TOKEN_MESSAGE,)
    assert invalid_bearer_error.value.args == (principal_service.INVALID_PRINCIPAL_MESSAGE,)


def test_principal_password_flag_denial_preserves_exact_internal_semantics(
    principal_session_factory: sessionmaker[Session],
) -> None:
    """Keep durable password policy on its dedicated typed denial."""
    access_token = create_principal_authority(principal_session_factory)
    with principal_session_factory.begin() as session:
        session.get_one(User, USER_ID).must_change_password = True
    with (
        principal_session_factory() as session,
        pytest.raises(principal_service.PasswordChangeRequired) as error,
    ):
        principal_service.load_principal(
            session,
            access_token,
            settings=principal_settings(),
        )

    assert error.value.args == (principal_service.PASSWORD_CHANGE_REQUIRED_MESSAGE,)


def test_principal_unknown_role_denial_preserves_exact_internal_semantics(
    principal_session_factory: sessionmaker[Session],
) -> None:
    """Keep corrupt durable roles distinct internally while HTTP remains opaque."""
    access_token = create_principal_authority(principal_session_factory)
    with principal_session_factory.begin() as session:
        session.execute(select(Role).where(Role.name == "translator")).scalar_one().name = "owner"
    with (
        principal_session_factory() as session,
        pytest.raises(principal_service.InvalidPrincipal) as error,
    ):
        principal_service.load_principal(
            session,
            access_token,
            settings=principal_settings(),
        )

    assert error.value.args == (principal_service.INVALID_ROLE_STATE_MESSAGE,)


@pytest.mark.parametrize(
    "durable_state",
    ["stale-version", "inactive", "revoked-session", "missing-session", "expired-session"],
)
def test_stale_inactive_or_revoked_authority_returns_exact_401(
    principal_session_factory: sessionmaker[Session],
    durable_state: str,
) -> None:
    """Durable user and session state overrides otherwise valid signed claims."""
    access_token = create_principal_authority(principal_session_factory)
    with principal_session_factory.begin() as session:
        user = session.get_one(User, USER_ID)
        auth_session = session.get_one(AuthSession, SESSION_ID)
        if durable_state == "stale-version":
            user.token_version += 1
        elif durable_state == "inactive":
            user.is_active = False
        elif durable_state == "revoked-session":
            auth_session.revoked_at = datetime.now(UTC)
        elif durable_state == "missing-session":
            session.delete(auth_session)
        else:
            auth_session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    configure_principal_dependencies(principal_session_factory)

    response = asyncio.run(get_me(access_token))

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid access token"}
    assert response.headers["www-authenticate"] == "Bearer"


def test_session_is_invalid_at_its_exact_expiry_boundary(
    principal_session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reject a session at, not only after, its durable expiry timestamp."""
    access_token = create_principal_authority(principal_session_factory)
    exact_expiry = datetime.now(UTC).replace(microsecond=0)
    with principal_session_factory.begin() as session:
        session.get_one(AuthSession, SESSION_ID).expires_at = exact_expiry

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, timezone: object = None) -> FrozenDateTime:
            return cls.fromtimestamp(exact_expiry.timestamp(), UTC)

    monkeypatch.setattr("verboflex.auth.principal.datetime", FrozenDateTime)
    configure_principal_dependencies(principal_session_factory)

    response = asyncio.run(get_me(access_token))

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid access token"}


def test_password_change_authority_returns_exact_403_without_identity_body(
    principal_session_factory: sessionmaker[Session],
) -> None:
    """Restricted credentials cannot disclose the ordinary identity projection."""
    with principal_session_factory.begin() as session:
        session.add(
            User(
                id=USER_ID,
                email="person@example.com",
                display_name="Person Example",
                hashed_password=hash_password("principal password phrase!"),
                must_change_password=True,
            )
        )
    restricted = issue_access_token(
        user_id=USER_ID,
        token_version=0,
        purpose="password_change",
        settings=principal_settings(),
    )
    configure_principal_dependencies(principal_session_factory)

    response = asyncio.run(get_me(restricted))

    assert response.status_code == 403
    assert response.json() == {"detail": "Password change required"}


def test_durable_password_change_flag_restricts_an_existing_session(
    principal_session_factory: sessionmaker[Session],
) -> None:
    """Current database policy overrides an otherwise ordinary signed session."""
    access_token = create_principal_authority(principal_session_factory)
    with principal_session_factory.begin() as session:
        session.get_one(User, USER_ID).must_change_password = True
    configure_principal_dependencies(principal_session_factory)

    response = asyncio.run(get_me(access_token))

    assert response.status_code == 403
    assert response.json() == {"detail": "Password change required"}


def test_unknown_durable_role_fails_closed(
    principal_session_factory: sessionmaker[Session],
) -> None:
    """Never project an authority role outside the stable public role vocabulary."""
    access_token = create_principal_authority(principal_session_factory)
    with principal_session_factory.begin() as session:
        session.execute(select(Role).where(Role.name == "translator")).scalar_one().name = "owner"
    configure_principal_dependencies(principal_session_factory)

    response = asyncio.run(get_me(access_token))

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid access token"}
    assert response.headers["www-authenticate"] == "Bearer"


def test_forged_role_claim_never_overrides_database_roles(
    principal_session_factory: sessionmaker[Session],
) -> None:
    """Ignore caller-signed role fields and return only current PostgreSQL roles."""
    with principal_session_factory.begin() as session:
        viewer = session.execute(select(Role).where(Role.name == "viewer")).scalar_one()
        session.add(
            User(
                id=USER_ID,
                email="person@example.com",
                display_name="Person Example",
                hashed_password=hash_password("principal password phrase!"),
                must_change_password=False,
                roles=[viewer],
            )
        )
        session.add(
            AuthSession(
                id=SESSION_ID,
                user_id=USER_ID,
                family_id=uuid4(),
                token_hash="e" * 64,
                expires_at=datetime.now(UTC) + timedelta(days=7),
            )
        )
    now = datetime.now(UTC).replace(microsecond=0)
    forged = jwt.encode(
        {
            "sub": str(USER_ID),
            "sid": str(SESSION_ID),
            "iat": int(now.timestamp()),
            "exp": int(now.timestamp()) + 900,
            "purpose": "access",
            "token_version": 0,
            "roles": ["admin"],
        },
        SIGNING_SECRET,
        algorithm="HS256",
    )
    configure_principal_dependencies(principal_session_factory)

    response = asyncio.run(get_me(forged))

    assert response.status_code == 200
    assert response.json()["roles"] == ["viewer"]
