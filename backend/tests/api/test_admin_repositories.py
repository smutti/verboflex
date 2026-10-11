"""Administrator-only global repository registry HTTP contracts."""

from __future__ import annotations

import asyncio
import base64
import inspect
import json
import os
import unicodedata
from collections.abc import Generator, Iterator, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from alembic.config import Config
from psycopg import connect, sql
from pydantic import SecretStr
from sqlalchemy import create_engine, delete, func, select, text
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from verboflex.auth.access_tokens import issue_access_token
from verboflex.auth.passwords import hash_password
from verboflex.core.config import Settings, get_settings
from verboflex.db.session import get_db_session
from verboflex.main import app
from verboflex.models.auth_session import AuthSession
from verboflex.models.repository import Repository
from verboflex.models.role import Role
from verboflex.models.user import User
from verboflex.services.repositories import list_repositories, normalize_repository_identity

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ADMIN_DATABASE_URL = os.environ.get(
    "VERBOFLEX_TEST_POSTGRES_ADMIN_URL",
    "postgresql://postgres@127.0.0.1:55432/postgres",
)
SIGNING_SECRET = "0123456789abcdef" * 2
ADMIN_REPOSITORIES_PATH = "/api/v1/admin/repositories"


@pytest.fixture(scope="module")
def repository_api_session_factory() -> Iterator[sessionmaker[Session]]:
    """Migrate one isolated PostgreSQL database for the focused repository API."""
    database_name = f"verboflex_admin_repositories_{uuid4().hex}"
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
def clean_repository_api_database(
    repository_api_session_factory: sessionmaker[Session],
) -> Iterator[None]:
    """Keep repository and bearer-principal state independent across examples."""
    app.dependency_overrides.clear()
    with repository_api_session_factory.begin() as session:
        session.execute(text("TRUNCATE repositories CASCADE"))
        session.execute(delete(AuthSession))
        session.execute(delete(User))
    yield
    app.dependency_overrides.clear()


def admin_settings() -> Settings:
    """Return deterministic signing settings independent from ambient secrets."""
    return Settings(jwt_secret_key=SecretStr(SIGNING_SECRET))


def configure_dependencies(factory: sessionmaker[Session]) -> None:
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
) -> str:
    """Persist one current principal and return its ordinary bearer token."""
    user_id = uuid4()
    auth_session_id = uuid4()
    now = datetime.now(UTC)
    with factory.begin() as session:
        durable_roles = list(session.execute(select(Role).where(Role.name.in_(roles))).scalars())
        session.add(
            User(
                id=user_id,
                email=email,
                display_name=email.split("@", 1)[0].title(),
                hashed_password=hash_password("principal password phrase!"),
                is_active=True,
                must_change_password=False,
                roles=durable_roles,
            )
        )
        session.add(
            AuthSession(
                id=auth_session_id,
                user_id=user_id,
                family_id=uuid4(),
                token_hash=uuid4().hex + uuid4().hex,
                expires_at=now + timedelta(days=7),
            )
        )
    return issue_access_token(
        user_id=user_id,
        session_id=auth_session_id,
        token_version=0,
        purpose="access",
        settings=admin_settings(),
        now=now,
    )


async def repository_request(
    method: str,
    *,
    access_token: str | None,
    path: str = ADMIN_REPOSITORIES_PATH,
    json_body: dict[str, object] | None = None,
) -> httpx.Response:
    """Call the registered ASGI surface without bypassing dependencies."""
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    headers = {"Authorization": f"Bearer {access_token}"} if access_token is not None else None
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, headers=headers, json=json_body)


def repository_payload(
    *,
    workspace: str = "Mobile-Team",
    repository_slug: str = "Translations-App",
    descriptive_name: str | None = "Mobile translations",
) -> dict[str, object]:
    return {
        "workspace": workspace,
        "repository_slug": repository_slug,
        "descriptive_name": descriptive_name,
    }


def _repository_count(factory: sessionmaker[Session]) -> int:
    with factory() as session:
        return session.scalar(select(func.count()).select_from(Repository)) or 0


def _descriptive_key(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split()).casefold()


def _cursor_from_json(payload: object, *, compact: bool) -> str:
    separators = (",", ":") if compact else None
    encoded = json.dumps(payload, separators=separators).encode()
    return base64.urlsafe_b64encode(encoded).rstrip(b"=").decode("ascii")


def test_repository_registration_conflict_and_uuid_selection_are_separate_operations(
    repository_api_session_factory: sessionmaker[Session],
) -> None:
    """Registration has one 201 while get-by-UUID is the explicit reuse path."""
    admin_token = create_authority(
        repository_api_session_factory,
        email="admin@example.com",
        roles=("admin",),
    )
    configure_dependencies(repository_api_session_factory)

    created = asyncio.run(
        repository_request(
            "POST",
            access_token=admin_token,
            json_body=repository_payload(),
        )
    )
    assert created.status_code == 201
    body = created.json()
    assert body == {
        "id": body["id"],
        "provider": "bitbucket",
        "workspace": "mobile-team",
        "repository_slug": "translations-app",
        "descriptive_name": "Mobile translations",
    }
    repository_id = UUID(body["id"])

    duplicate = asyncio.run(
        repository_request(
            "POST",
            access_token=admin_token,
            json_body=repository_payload(
                workspace=" mobile-team ",
                repository_slug=" TRANSLATIONS-APP ",
                descriptive_name="Duplicate attempt",
            ),
        )
    )
    assert duplicate.status_code == 409
    assert duplicate.json() == {"detail": "Repository unavailable"}

    selected = asyncio.run(
        repository_request(
            "GET",
            access_token=admin_token,
            path=f"{ADMIN_REPOSITORIES_PATH}/{repository_id}",
        )
    )
    assert selected.status_code == 200
    assert selected.json() == body
    assert _repository_count(repository_api_session_factory) == 1

    missing = asyncio.run(
        repository_request(
            "GET",
            access_token=admin_token,
            path=f"{ADMIN_REPOSITORIES_PATH}/{uuid4()}",
        )
    )
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Repository unavailable"}


def test_every_repository_route_reuses_admin_authority_and_denials_do_not_mutate(
    repository_api_session_factory: sessionmaker[Session],
) -> None:
    """Unauthenticated and non-admin requests fail before registry access."""
    admin_token = create_authority(
        repository_api_session_factory,
        email="admin@example.com",
        roles=("admin",),
    )
    viewer_token = create_authority(
        repository_api_session_factory,
        email="viewer@example.com",
        roles=("viewer",),
    )
    configure_dependencies(repository_api_session_factory)
    created = asyncio.run(
        repository_request(
            "POST",
            access_token=admin_token,
            json_body=repository_payload(),
        )
    )
    repository_id = created.json()["id"]
    before = _repository_count(repository_api_session_factory)
    calls: tuple[tuple[str, str, dict[str, object] | None], ...] = (
        ("GET", ADMIN_REPOSITORIES_PATH, None),
        (
            "POST",
            ADMIN_REPOSITORIES_PATH,
            repository_payload(workspace="forbidden", repository_slug="forbidden"),
        ),
        ("GET", f"{ADMIN_REPOSITORIES_PATH}/{repository_id}", None),
    )

    for token, expected_status in ((None, 401), (viewer_token, 403)):
        for method, path, payload in calls:
            response = asyncio.run(
                repository_request(
                    method,
                    access_token=token,
                    path=path,
                    json_body=payload,
                )
            )
            assert response.status_code == expected_status
            assert _repository_count(repository_api_session_factory) == before


def _seed_repositories(factory: sessionmaker[Session], count: int) -> None:
    """Seed reversed deterministic identities so the API owns exact ordering."""
    repositories = []
    for index in reversed(range(count)):
        workspace = f"workspace-{index % 7:02d}"
        repository_slug = f"repository-{index:03d}"
        descriptive_name = f" Shared Name {index % 5:02d} " if index % 3 else None
        descriptive_name_key = (
            _descriptive_key(descriptive_name) if descriptive_name is not None else None
        )
        repositories.append(
            Repository(
                id=UUID(int=index + 1),
                workspace=workspace,
                repository_slug=repository_slug,
                descriptive_name=(
                    " ".join(unicodedata.normalize("NFKC", descriptive_name).split())
                    if descriptive_name is not None
                    else None
                ),
                descriptive_name_key=descriptive_name_key,
            )
        )
    with factory.begin() as session:
        session.add_all(repositories)


def test_repository_collection_is_empty_bounded_opaque_and_exactly_server_ordered(
    repository_api_session_factory: sessionmaker[Session],
) -> None:
    """Prove empty/default/max pages, canonical cursors, and fallback ordering."""
    admin_token = create_authority(
        repository_api_session_factory,
        email="admin@example.com",
        roles=("admin",),
    )
    configure_dependencies(repository_api_session_factory)

    empty = asyncio.run(repository_request("GET", access_token=admin_token))
    assert empty.status_code == 200
    assert empty.json() == {"items": [], "next_cursor": None}

    _seed_repositories(repository_api_session_factory, 105)
    first = asyncio.run(repository_request("GET", access_token=admin_token))
    assert first.status_code == 200
    assert len(first.json()["items"]) == 50
    first_cursor = first.json()["next_cursor"]
    assert isinstance(first_cursor, str) and first_cursor
    assert "workspace" not in first_cursor
    assert "repository" not in first_cursor

    second = asyncio.run(
        repository_request(
            "GET",
            access_token=admin_token,
            path=f"{ADMIN_REPOSITORIES_PATH}?cursor={first_cursor}",
        )
    )
    second_cursor = second.json()["next_cursor"]
    third = asyncio.run(
        repository_request(
            "GET",
            access_token=admin_token,
            path=f"{ADMIN_REPOSITORIES_PATH}?cursor={second_cursor}",
        )
    )
    all_items = first.json()["items"] + second.json()["items"] + third.json()["items"]
    observed_order = [
        (
            _descriptive_key(item["descriptive_name"])
            if item["descriptive_name"] is not None
            else f"{item['workspace']}/{item['repository_slug']}",
            item["workspace"],
            item["repository_slug"],
            UUID(item["id"]),
        )
        for item in all_items
    ]
    assert [len(page.json()["items"]) for page in (first, second, third)] == [50, 50, 5]
    assert third.json()["next_cursor"] is None
    assert observed_order == sorted(observed_order)
    assert len(set(observed_order)) == 105

    maximum = asyncio.run(
        repository_request(
            "GET",
            access_token=admin_token,
            path=f"{ADMIN_REPOSITORIES_PATH}?limit=100",
        )
    )
    assert maximum.status_code == 200
    assert len(maximum.json()["items"]) == 100
    assert maximum.json()["next_cursor"]

    over_limit = asyncio.run(
        repository_request(
            "GET",
            access_token=admin_token,
            path=f"{ADMIN_REPOSITORIES_PATH}?limit=101",
        )
    )
    invalid = asyncio.run(
        repository_request(
            "GET",
            access_token=admin_token,
            path=f"{ADMIN_REPOSITORIES_PATH}?cursor=not-a-valid-cursor",
        )
    )
    oversized = asyncio.run(
        repository_request(
            "GET",
            access_token=admin_token,
            path=f"{ADMIN_REPOSITORIES_PATH}?cursor={'x' * 1025}",
        )
    )
    first_padding = "=" * (-len(first_cursor) % 4)
    first_payload = json.loads(base64.urlsafe_b64decode(first_cursor + first_padding))
    noncanonical_cursor = _cursor_from_json(first_payload, compact=False)
    wrong_shape_cursor = _cursor_from_json({}, compact=True)
    noncanonical = asyncio.run(
        repository_request(
            "GET",
            access_token=admin_token,
            path=f"{ADMIN_REPOSITORIES_PATH}?cursor={noncanonical_cursor}",
        )
    )
    wrong_shape = asyncio.run(
        repository_request(
            "GET",
            access_token=admin_token,
            path=f"{ADMIN_REPOSITORIES_PATH}?cursor={wrong_shape_cursor}",
        )
    )
    assert over_limit.status_code == 422
    assert invalid.status_code == oversized.status_code == noncanonical.status_code == 422
    assert wrong_shape.status_code == 422
    assert (
        invalid.json()
        == oversized.json()
        == noncanonical.json()
        == wrong_shape.json()
        == {"detail": "Invalid cursor"}
    )


def test_repository_api_is_closed_credential_free_and_provider_read_free(
    repository_api_session_factory: sessionmaker[Session],
) -> None:
    """Transport accepts only registry fields and owns no provider/token capability."""
    admin_token = create_authority(
        repository_api_session_factory,
        email="admin@example.com",
        roles=("admin",),
    )
    configure_dependencies(repository_api_session_factory)

    extra = asyncio.run(
        repository_request(
            "POST",
            access_token=admin_token,
            json_body={**repository_payload(), "access_token": "must-not-be-accepted"},
        )
    )
    assert extra.status_code == 422
    assert _repository_count(repository_api_session_factory) == 0

    invalid_identity = asyncio.run(
        repository_request(
            "POST",
            access_token=admin_token,
            json_body=repository_payload(workspace="../team"),
        )
    )
    assert invalid_identity.status_code == 422
    assert invalid_identity.json() == {"detail": "Invalid repository input"}

    repository_paths = {
        path for path in app.openapi()["paths"] if path.startswith(ADMIN_REPOSITORIES_PATH)
    }
    exact_branch_path = f"{ADMIN_REPOSITORIES_PATH}/{{repository_id}}/branch"
    assert repository_paths == {
        ADMIN_REPOSITORIES_PATH,
        f"{ADMIN_REPOSITORIES_PATH}/{{repository_id}}",
        exact_branch_path,
        f"{ADMIN_REPOSITORIES_PATH}/{{repository_id}}/branches",
        f"{ADMIN_REPOSITORIES_PATH}/{{repository_id}}/sources",
    }
    exact_branch_methods = app.openapi()["paths"][exact_branch_path]
    assert set(exact_branch_methods) == {"get"}
    exact_branch_operation = exact_branch_methods["get"]
    branch_name_parameter = next(
        parameter
        for parameter in exact_branch_operation["parameters"]
        if parameter["name"] == "branch_name"
    )
    assert branch_name_parameter["in"] == "query"
    assert branch_name_parameter["required"] is True
    assert branch_name_parameter["schema"]["minLength"] == 1
    assert branch_name_parameter["schema"]["maxLength"] == 255
    request_schema = app.openapi()["components"]["schemas"]["AdminRepositoryCreateRequest"]
    response_schema = app.openapi()["components"]["schemas"]["AdminRepositoryResponse"]
    assert request_schema["additionalProperties"] is False
    assert response_schema["additionalProperties"] is False
    assert set(request_schema["properties"]) == {
        "workspace",
        "repository_slug",
        "descriptive_name",
    }
    assert set(response_schema["properties"]) == {
        "id",
        "provider",
        "workspace",
        "repository_slug",
        "descriptive_name",
    }

    from verboflex.api.v1.routes import admin_repositories
    from verboflex.services import repositories

    production_source = "\n".join(
        (inspect.getsource(admin_repositories), inspect.getsource(repositories))
    ).casefold()
    assert "httpx" not in production_source
    assert "integrations.bitbucket" not in production_source
    assert "bitbuckethttpadapter" not in production_source
    assert "githubhttpadapter" not in production_source
    assert "access_token" not in production_source
    assert "refresh_token" not in production_source
    assert {"credential", "token"}.isdisjoint(Repository.__table__.columns.keys())


def test_repository_service_and_cursor_rejection_branches_fail_closed(
    repository_api_session_factory: sessionmaker[Session],
) -> None:
    """Direct callers and structurally plausible cursors cannot bypass validation."""
    with pytest.raises(ValueError, match="invalid repository identity"):
        normalize_repository_identity(42, "repository")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="invalid page size"):
        list_repositories(repository_api_session_factory(), limit=0)
    with pytest.raises(ValueError, match="invalid page size"):
        list_repositories(repository_api_session_factory(), limit=101)

    admin_token = create_authority(
        repository_api_session_factory,
        email="admin@example.com",
        roles=("admin",),
    )
    configure_dependencies(repository_api_session_factory)
    no_description = asyncio.run(
        repository_request(
            "POST",
            access_token=admin_token,
            json_body=repository_payload(descriptive_name=None),
        )
    )
    assert no_description.status_code == 201

    for descriptive_name in (42, " ", "x" * 121, "contains\x00nul", "contains\x07bell"):
        with repository_api_session_factory() as session:
            from verboflex.services.repositories import register_repository

            with pytest.raises(ValueError, match="invalid repository description"):
                register_repository(
                    session,
                    workspace="validation-team",
                    repository_slug="validation-repository",
                    descriptive_name=descriptive_name,  # type: ignore[arg-type]
                    actor_id=None,
                )

    valid_cursor_response = asyncio.run(
        repository_request(
            "GET",
            access_token=admin_token,
            path=f"{ADMIN_REPOSITORIES_PATH}?limit=1",
        )
    )
    assert valid_cursor_response.status_code == 200

    cursor_payloads = (
        {
            "id": str(UUID(int=1)),
            "repository_slug": "repository",
            "sort_key": "repository",
            "version": 2,
            "workspace": "workspace",
        },
        {
            "id": str(UUID(int=1)),
            "repository_slug": "repository",
            "sort_key": 7,
            "version": 1,
            "workspace": "workspace",
        },
        {
            "id": str(UUID(int=1)),
            "repository_slug": "repository",
            "sort_key": "repository",
            "version": 1,
            "workspace": 7,
        },
        {
            "id": str(UUID(int=1)),
            "repository_slug": 7,
            "sort_key": "repository",
            "version": 1,
            "workspace": "workspace",
        },
        {
            "id": "not-a-uuid",
            "repository_slug": "repository",
            "sort_key": "repository",
            "version": 1,
            "workspace": "workspace",
        },
    )
    invalid_cursors = (
        "",
        *(_cursor_from_json(payload, compact=True) for payload in cursor_payloads),
    )
    for invalid_cursor in invalid_cursors:
        response = asyncio.run(
            repository_request(
                "GET",
                access_token=admin_token,
                path=f"{ADMIN_REPOSITORIES_PATH}?cursor={invalid_cursor}",
            )
        )
        assert response.status_code == 422
        assert response.json() == {"detail": "Invalid cursor"}
