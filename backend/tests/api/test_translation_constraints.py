"""Closed maximum-length mutation HTTP contracts."""

from __future__ import annotations

import asyncio
import hashlib
import importlib
import importlib.util
import os
from collections.abc import Generator, Iterator, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType
from uuid import UUID, uuid4

import httpx
import pytest
from alembic.config import Config
from psycopg import connect, sql
from pydantic import SecretStr, ValidationError
from sqlalchemy import create_engine, delete, func, select, text
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from verboflex.auth.access_tokens import issue_access_token
from verboflex.auth.passwords import hash_password
from verboflex.core.config import Settings, get_settings
from verboflex.db.session import get_db_session
from verboflex.main import app
from verboflex.models.auth_session import AuthSession
from verboflex.models.import_job import ImportExecution, ImportJob, ImportSourceReference
from verboflex.models.product import Product, ProductRevision
from verboflex.models.product_mapping import (
    ProductMappingAllowedTarget,
    ProductMappingRepositorySide,
    ProductRepositoryMapping,
)
from verboflex.models.repository import Repository
from verboflex.models.role import Role
from verboflex.models.translation import (
    LocalizationScope,
    TranslationKey,
    TranslationValue,
    TranslationValueLocator,
)
from verboflex.models.translation_constraint import TranslationConstraint
from verboflex.models.user import User

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ADMIN_DATABASE_URL = os.environ.get(
    "VERBOFLEX_TEST_POSTGRES_ADMIN_URL",
    "postgresql://postgres@127.0.0.1:55432/postgres",
)
SIGNING_SECRET = "0123456789abcdef" * 2
TRANSLATIONS_PATH = "/api/v1/translations"
ROLE_NAMES = ("admin", "product_manager_reviewer", "translator", "viewer")


def _constraint_schemas() -> ModuleType:
    module_name = "verboflex.schemas.translation_constraints"
    assert importlib.util.find_spec(module_name) is not None
    return importlib.import_module(module_name)


def _constraint_routes() -> ModuleType:
    module_name = "verboflex.api.v1.routes.translation_constraints"
    assert importlib.util.find_spec(module_name) is not None
    return importlib.import_module(module_name)


@pytest.fixture(scope="module")
def constraint_api_session_factory() -> Iterator[sessionmaker[Session]]:
    database_name = f"verboflex_constraint_api_{uuid4().hex}"
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
def clean_constraint_api_database(
    constraint_api_session_factory: sessionmaker[Session],
) -> Iterator[None]:
    app.dependency_overrides.clear()
    with constraint_api_session_factory.begin() as session:
        session.execute(text("TRUNCATE products, repositories CASCADE"))
        session.execute(delete(AuthSession))
        session.execute(delete(User))
    yield
    app.dependency_overrides.clear()


def _settings() -> Settings:
    return Settings(jwt_secret_key=SecretStr(SIGNING_SECRET))


def _configure_dependencies(factory: sessionmaker[Session]) -> None:
    def override_session() -> Generator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_settings] = _settings


def _create_authority(
    factory: sessionmaker[Session],
    *,
    role_names: Sequence[str],
) -> str:
    user_id = uuid4()
    auth_session_id = uuid4()
    now = datetime.now(UTC)
    with factory.begin() as session:
        roles = list(session.execute(select(Role).where(Role.name.in_(role_names))).scalars())
        session.add(
            User(
                id=user_id,
                email=f"constraint-api-{user_id}@example.com",
                display_name="Constraint API principal",
                hashed_password=hash_password("principal password phrase!"),
                is_active=True,
                must_change_password=False,
                roles=roles,
            )
        )
        session.add(
            AuthSession(
                id=auth_session_id,
                user_id=user_id,
                family_id=uuid4(),
                token_hash=uuid4().hex + uuid4().hex,
                expires_at=now + timedelta(days=1),
            )
        )
    return issue_access_token(
        user_id=user_id,
        session_id=auth_session_id,
        token_version=0,
        purpose="access",
        settings=_settings(),
        now=now,
    )


def _seed_constraint_group(
    factory: sessionmaker[Session],
    *,
    name: str,
    active: bool = True,
    base_language: str | None = "it",
    complete_dataset: bool = True,
    deleted: bool = False,
) -> dict[str, object]:
    ids = {
        "execution": uuid4(),
        "import": uuid4(),
        "key": uuid4(),
        "mapping": uuid4(),
        "product": uuid4(),
        "repository": uuid4(),
        "revision": uuid4(),
        "scope": uuid4(),
    }
    value_ids = (uuid4(), uuid4())
    now = datetime.now(UTC)
    with factory.begin() as session:
        product = Product(
            id=ids["product"],
            display_name=name,
            name_key=f"{name.casefold()}-{ids['product']}",
            is_active=active,
        )
        session.add(product)
        session.flush()
        revision = ProductRevision(
            id=ids["revision"],
            product_id=ids["product"],
            display_name=name,
            name_key=product.name_key,
            description="constraint API dataset",
            version=1,
            is_published=False,
            published_at=None,
        )
        repository = Repository(
            id=ids["repository"],
            workspace="constraint-api",
            repository_slug=f"translations-{ids['repository'].hex[:12]}",
            descriptive_name=f"{name} translations",
            descriptive_name_key=f"{name.casefold()} translations",
        )
        session.add_all([revision, repository])
        session.flush()
        mapping = ProductRepositoryMapping(
            id=ids["mapping"],
            revision_id=ids["revision"],
            topology="direct",
            identity_key=f'["direct","{ids["repository"]}","main"]',
            base_language=base_language,
            sides=[
                ProductMappingRepositorySide(
                    role="direct",
                    repository_id=ids["repository"],
                    source_branch="main",
                )
            ],
            allowed_targets=[ProductMappingAllowedTarget(branch="main", is_default=True)],
        )
        session.add(mapping)
        session.flush()
        revision.is_published = True
        revision.published_at = now
        session.flush()
        product.active_revision_id = ids["revision"]
        session.add(
            ImportJob(
                id=ids["import"],
                product_id=ids["product"],
                revision_id=ids["revision"],
                mapping_id=ids["mapping"],
                topology="direct",
                state="running",
                current_execution_id=ids["execution"],
                active_baseline_execution_id=None,
                retry_count=0,
                latest_execution_at=now,
            )
        )
        session.flush()
        session.add(
            ImportExecution(
                id=ids["execution"],
                import_job_id=ids["import"],
                sequence=1,
                state="running",
                connection_generation=1,
                started_at=now,
                finished_at=None,
            )
        )
        session.flush()
        session.add(
            ImportSourceReference(
                execution_id=ids["execution"],
                position=0,
                repository_side="direct",
                repository_id=ids["repository"],
                source_branch="main",
                commit_hash="a" * 40,
                path="locales/messages.json",
                size_bytes=1,
                sha256="b" * 64,
            )
        )
        session.flush()
        execution = session.get_one(ImportExecution, ids["execution"])
        execution.state = "succeeded"
        execution.finished_at = now
        import_job = session.get_one(ImportJob, ids["import"])
        import_job.state = "current"
        import_job.active_baseline_execution_id = ids["execution"]
        session.flush()
        session.add(
            LocalizationScope(
                id=ids["scope"],
                product_id=ids["product"],
                mapping_identity_key=mapping.identity_key,
                current_revision_id=ids["revision"],
                current_mapping_id=ids["mapping"],
                active_import_job_id=ids["import"] if complete_dataset else None,
                active_execution_id=ids["execution"] if complete_dataset else None,
                dataset_version=1 if complete_dataset else 0,
            )
        )
        session.flush()
        key = TranslationKey(
            id=ids["key"],
            scope_id=ids["scope"],
            product_id=ids["product"],
            repository_id=ids["repository"],
            configured_branch="main",
            raw_key="status.precision",
            is_deleted=deleted,
            deleted_at=now if deleted else None,
        )
        session.add(key)
        session.flush()
        values = (
            (value_ids[0], b'{"kind":"scalar","schema_version":1,"slot":0}', "", 0),
            (
                value_ids[1],
                b'{"kind":"scalar","schema_version":1,"slot":1}',
                "e\u0301👩🏽‍💻",
                2,
            ),
        )
        for position, (value_id, selector, display_text, actual) in enumerate(values):
            session.add(
                TranslationValue(
                    id=value_id,
                    scope_id=ids["scope"],
                    translation_key_id=ids["key"],
                    language="it",
                    selector_version=1,
                    selector_kind="scalar",
                    selector_bytes=selector,
                    selector_digest=hashlib.sha256(selector).hexdigest(),
                    source_text=display_text,
                    translated_text=display_text,
                    display_text=display_text,
                    structure=[],
                    review_state="draft",
                    grapheme_count=actual,
                    effective_max_chars=None,
                    effective_constraint_source="none",
                    is_over_limit=False,
                    is_deleted=deleted,
                    deleted_at=now if deleted else None,
                )
            )
            if complete_dataset:
                session.flush()
                session.add(
                    TranslationValueLocator(
                        value_id=value_id,
                        translation_key_id=ids["key"],
                        import_job_id=ids["import"],
                        import_execution_id=ids["execution"],
                        source_reference_position=0,
                        repository_side="direct",
                        repository_id=ids["repository"],
                        configured_branch="main",
                        source_commit_hash="a" * 40,
                        format="json",
                        path="locales/messages.json",
                        position=position,
                        structural_address=["status.precision", position],
                        line=position + 1,
                        column=1,
                    )
                )
    return {
        **ids,
        "group": min(value_ids),
        "values": value_ids,
    }


async def _request(
    method: str,
    path: str,
    *,
    token: str | None,
    json: object | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    request_headers = dict(headers or {})
    if token is not None:
        request_headers["Authorization"] = f"Bearer {token}"
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, json=json, headers=request_headers)


@pytest.mark.parametrize("max_chars", [0, 1_048_576])
def test_constraint_schema_accepts_exact_inclusive_maximum_bounds(max_chars: int) -> None:
    schemas = _constraint_schemas()

    request = schemas.PutTranslationConstraintRequest.model_validate(
        {"max_chars": max_chars, "expected_version": 0}
    )

    assert request.model_dump() == {
        "max_chars": max_chars,
        "expected_version": 0,
    }


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"expected_version": 0},
        {"max_chars": 1},
        {"max_chars": None, "expected_version": 0},
        {"max_chars": 1.0, "expected_version": 0},
        {"max_chars": True, "expected_version": 0},
        {"max_chars": "1", "expected_version": 0},
        {"max_chars": -1, "expected_version": 0},
        {"max_chars": 1_048_577, "expected_version": 0},
        {"max_chars": 1, "expected_version": None},
        {"max_chars": 1, "expected_version": 0.0},
        {"max_chars": 1, "expected_version": False},
        {"max_chars": 1, "expected_version": "0"},
        {"max_chars": 1, "expected_version": -1},
        {"max_chars": 1, "expected_version": 0, "status": "client-owned"},
    ],
)
def test_constraint_put_schema_rejects_missing_null_coerced_bound_and_extra_payloads(
    payload: dict[str, object],
) -> None:
    schemas = _constraint_schemas()

    with pytest.raises(ValidationError):
        schemas.PutTranslationConstraintRequest.model_validate(payload)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"expected_version": None},
        {"expected_version": 1.0},
        {"expected_version": True},
        {"expected_version": "1"},
        {"expected_version": -1},
        {"expected_version": 1, "max_chars": 8},
    ],
)
def test_constraint_delete_schema_rejects_inexact_version_and_extra_payloads(
    payload: dict[str, object],
) -> None:
    schemas = _constraint_schemas()

    with pytest.raises(ValidationError):
        schemas.DeleteTranslationConstraintRequest.model_validate(payload)


def test_constraint_projection_preserves_zero_no_limit_and_exact_group_precision() -> None:
    schemas = _constraint_schemas()
    group_id = uuid4()
    equal_value_id = uuid4()
    over_value_id = uuid4()
    no_limit_value_id = uuid4()

    projection = schemas.TranslationConstraintMutationResponse.model_validate(
        {
            "translation_group_id": group_id,
            "language": "it",
            "base_language": "en",
            "explicit_maximum": 0,
            "version": 1,
            "violating_count": 1,
            "total_count": 3,
            "values": [
                {
                    "id": equal_value_id,
                    "language": "it",
                    "constraint": {
                        "actual": 0,
                        "maximum": 0,
                        "source": "language_override",
                        "status": "within_limit",
                        "overage": 0,
                    },
                    "approval_eligible": True,
                    "submission_eligible": True,
                },
                {
                    "id": over_value_id,
                    "language": "it",
                    "constraint": {
                        "actual": 2,
                        "maximum": 0,
                        "source": "language_override",
                        "status": "over_limit",
                        "overage": 2,
                    },
                    "approval_eligible": False,
                    "submission_eligible": False,
                },
                {
                    "id": no_limit_value_id,
                    "language": "en",
                    "constraint": {
                        "actual": 0,
                        "maximum": None,
                        "source": "none",
                        "status": "no_max",
                        "overage": None,
                    },
                    "approval_eligible": True,
                    "submission_eligible": True,
                },
            ],
        }
    ).model_dump()

    assert projection["explicit_maximum"] == 0
    assert projection["violating_count"] == 1
    assert projection["total_count"] == 3
    assert projection["values"][0]["constraint"] == {
        "actual": 0,
        "maximum": 0,
        "source": "language_override",
        "status": "within_limit",
        "overage": 0,
    }
    assert projection["values"][2]["constraint"] == {
        "actual": 0,
        "maximum": None,
        "source": "none",
        "status": "no_max",
        "overage": None,
    }


def test_constraint_schema_uses_visible_character_vocabulary() -> None:
    schemas = _constraint_schemas()
    description = schemas.PutTranslationConstraintRequest.model_json_schema()["properties"][
        "max_chars"
    ]["description"].casefold()

    assert "visible character" in description
    assert all(term not in description for term in ("byte", "code point", "utf"))


def test_constraint_routes_enforce_four_role_matrix_and_keep_detail_readable(
    constraint_api_session_factory: sessionmaker[Session],
) -> None:
    _configure_dependencies(constraint_api_session_factory)
    last_group_id: UUID | None = None

    for role_name in ROLE_NAMES:
        ids = _seed_constraint_group(
            constraint_api_session_factory,
            name=f"Role {role_name}",
        )
        group_id = ids["group"]
        assert isinstance(group_id, UUID)
        last_group_id = group_id
        token = _create_authority(
            constraint_api_session_factory,
            role_names=(role_name,),
        )
        path = f"{TRANSLATIONS_PATH}/{group_id}/constraints/it"

        detail = asyncio.run(_request("GET", f"{TRANSLATIONS_PATH}/{group_id}", token=token))
        assert detail.status_code == 200

        put_response = asyncio.run(
            _request(
                "PUT",
                path,
                token=token,
                json={"max_chars": 0, "expected_version": 0},
            )
        )
        if role_name in ("admin", "product_manager_reviewer"):
            assert put_response.status_code == 200
            assert put_response.json()["explicit_maximum"] == 0
            assert put_response.json()["version"] == 1
            delete_response = asyncio.run(
                _request(
                    "DELETE",
                    path,
                    token=token,
                    json={"expected_version": 1},
                )
            )
            assert delete_response.status_code == 200
            assert delete_response.json()["explicit_maximum"] is None
            assert delete_response.json()["version"] is None
        else:
            assert put_response.status_code == 403
            assert put_response.json() == {"detail": "Insufficient permissions"}
            delete_response = asyncio.run(
                _request(
                    "DELETE",
                    path,
                    token=token,
                    json={"expected_version": 0},
                )
            )
            assert delete_response.status_code == 403
            assert delete_response.json() == {"detail": "Insufficient permissions"}

    assert last_group_id is not None
    anonymous = asyncio.run(
        _request(
            "PUT",
            f"{TRANSLATIONS_PATH}/{last_group_id}/constraints/it",
            token=None,
            json={"max_chars": 1, "expected_version": 0},
        )
    )
    assert anonymous.status_code == 401
    assert anonymous.json() == {"detail": "Invalid access token"}
    with constraint_api_session_factory() as session:
        assert session.scalar(select(func.count()).select_from(TranslationConstraint)) == 0


def test_constraint_payload_validation_prevents_service_dispatch(
    constraint_api_session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    routes = _constraint_routes()
    ids = _seed_constraint_group(constraint_api_session_factory, name="Closed payload")
    group_id = ids["group"]
    assert isinstance(group_id, UUID)
    token = _create_authority(constraint_api_session_factory, role_names=("admin",))
    _configure_dependencies(constraint_api_session_factory)
    calls: list[str] = []

    def forbidden_dispatch(*_args: object, **_kwargs: object) -> None:
        calls.append("dispatched")

    monkeypatch.setattr(routes, "put_translation_constraint_service", forbidden_dispatch)
    monkeypatch.setattr(routes, "delete_translation_constraint_service", forbidden_dispatch)
    path = f"{TRANSLATIONS_PATH}/{group_id}/constraints/it"
    invalid_put_payloads: tuple[object, ...] = (
        {},
        {"max_chars": None, "expected_version": 0},
        {"max_chars": 1.0, "expected_version": 0},
        {"max_chars": True, "expected_version": 0},
        {"max_chars": "1", "expected_version": 0},
        {"max_chars": -1, "expected_version": 0},
        {"max_chars": 1_048_577, "expected_version": 0},
        {"max_chars": 1, "expected_version": None},
        {"max_chars": 1, "expected_version": 0.0},
        {"max_chars": 1, "expected_version": False},
        {"max_chars": 1, "expected_version": "0"},
        {"max_chars": 1, "expected_version": -1},
        {"max_chars": 1, "expected_version": 0, "status": "client-owned"},
    )
    for payload in invalid_put_payloads:
        response = asyncio.run(_request("PUT", path, token=token, json=payload))
        assert response.status_code == 422

    invalid_delete_payloads: tuple[object, ...] = (
        {},
        {"expected_version": None},
        {"expected_version": 1.0},
        {"expected_version": True},
        {"expected_version": "1"},
        {"expected_version": -1},
        {"expected_version": 1, "max_chars": 8},
    )
    for payload in invalid_delete_payloads:
        response = asyncio.run(_request("DELETE", path, token=token, json=payload))
        assert response.status_code == 422

    assert (
        asyncio.run(
            _request(
                "PUT",
                f"{TRANSLATIONS_PATH}/{group_id}/constraints/it_IT",
                token=token,
                json={"max_chars": 1, "expected_version": 0},
            )
        ).status_code
        == 422
    )
    assert (
        asyncio.run(
            _request(
                "PUT",
                f"{TRANSLATIONS_PATH}/not-a-uuid/constraints/it",
                token=token,
                json={"max_chars": 1, "expected_version": 0},
            )
        ).status_code
        == 422
    )
    assert calls == []


def test_constraint_mutations_return_authoritative_unicode_boundary_and_empty_projections(
    constraint_api_session_factory: sessionmaker[Session],
) -> None:
    ids = _seed_constraint_group(constraint_api_session_factory, name="Unicode precision")
    group_id = ids["group"]
    assert isinstance(group_id, UUID)
    admin_token = _create_authority(
        constraint_api_session_factory,
        role_names=("admin",),
    )
    viewer_token = _create_authority(
        constraint_api_session_factory,
        role_names=("viewer",),
    )
    _configure_dependencies(constraint_api_session_factory)
    path = f"{TRANSLATIONS_PATH}/{group_id}/constraints/it"

    equal = asyncio.run(
        _request(
            "PUT",
            path,
            token=admin_token,
            json={"max_chars": 2, "expected_version": 0},
        )
    )
    assert equal.status_code == 200
    assert (equal.json()["violating_count"], equal.json()["total_count"]) == (0, 2)
    by_actual = {item["constraint"]["actual"]: item for item in equal.json()["values"]}
    assert by_actual[0]["constraint"] == {
        "actual": 0,
        "maximum": 2,
        "source": "base_default",
        "status": "within_limit",
        "overage": 0,
    }
    assert by_actual[2]["constraint"] == {
        "actual": 2,
        "maximum": 2,
        "source": "base_default",
        "status": "within_limit",
        "overage": 0,
    }
    assert by_actual[2]["approval_eligible"] is True
    assert by_actual[2]["submission_eligible"] is True

    over = asyncio.run(
        _request(
            "PUT",
            path,
            token=admin_token,
            json={"max_chars": 0, "expected_version": 1},
        )
    )
    assert over.status_code == 200
    assert over.json()["explicit_maximum"] == 0
    assert over.json()["version"] == 2
    assert (over.json()["violating_count"], over.json()["total_count"]) == (1, 2)
    by_actual = {item["constraint"]["actual"]: item for item in over.json()["values"]}
    assert by_actual[0]["constraint"]["status"] == "within_limit"
    assert by_actual[0]["constraint"]["maximum"] == 0
    assert by_actual[2]["constraint"]["status"] == "over_limit"
    assert by_actual[2]["constraint"]["overage"] == 2
    assert by_actual[2]["approval_eligible"] is False
    assert by_actual[2]["submission_eligible"] is False

    detail = asyncio.run(_request("GET", f"{TRANSLATIONS_PATH}/{group_id}", token=viewer_token))
    assert detail.status_code == 200
    detail_by_actual = {
        item["constraint"]["actual"]: item["constraint"] for item in detail.json()["values"]
    }
    assert detail_by_actual == {
        0: {
            "actual": 0,
            "maximum": 0,
            "source": "base_default",
            "status": "within_limit",
            "overage": 0,
        },
        2: {
            "actual": 2,
            "maximum": 0,
            "source": "base_default",
            "status": "over_limit",
            "overage": 2,
        },
    }

    removed = asyncio.run(
        _request(
            "DELETE",
            path,
            token=admin_token,
            json={"expected_version": 2},
        )
    )
    assert removed.status_code == 200
    assert removed.json()["explicit_maximum"] is None
    assert removed.json()["version"] is None
    assert (removed.json()["violating_count"], removed.json()["total_count"]) == (0, 2)
    for item in removed.json()["values"]:
        assert item["constraint"]["maximum"] is None
        assert item["constraint"]["source"] == "none"
        assert item["constraint"]["status"] == "no_max"
        assert item["constraint"]["overage"] is None
        assert item["approval_eligible"] is True
        assert item["submission_eligible"] is True

    with constraint_api_session_factory() as session:
        values = tuple(
            session.scalars(
                select(TranslationValue)
                .where(TranslationValue.id.in_(ids["values"]))
                .order_by(TranslationValue.id)
            )
        )
        assert {value.display_text for value in values} == {"", "e\u0301👩🏽‍💻"}
        assert {value.review_state for value in values} == {"draft"}
        assert session.scalar(select(func.count()).select_from(TranslationConstraint)) == 0


def test_constraint_stale_inaccessible_tombstoned_and_incomplete_errors_do_not_mutate(
    constraint_api_session_factory: sessionmaker[Session],
) -> None:
    ids = _seed_constraint_group(constraint_api_session_factory, name="Current authority")
    group_id = ids["group"]
    assert isinstance(group_id, UUID)
    tombstoned = _seed_constraint_group(
        constraint_api_session_factory,
        name="Deleted authority",
        deleted=True,
    )
    incomplete = _seed_constraint_group(
        constraint_api_session_factory,
        name="Incomplete authority",
        complete_dataset=False,
    )
    inactive = _seed_constraint_group(
        constraint_api_session_factory,
        name="Inactive authority",
        active=False,
    )
    token = _create_authority(constraint_api_session_factory, role_names=("admin",))
    _configure_dependencies(constraint_api_session_factory)
    path = f"{TRANSLATIONS_PATH}/{group_id}/constraints/it"

    created = asyncio.run(
        _request(
            "PUT",
            path,
            token=token,
            json={"max_chars": 1, "expected_version": 0},
        )
    )
    assert created.status_code == 200

    stale_put = asyncio.run(
        _request(
            "PUT",
            path,
            token=token,
            json={"max_chars": 0, "expected_version": 0},
        )
    )
    stale_delete = asyncio.run(
        _request(
            "DELETE",
            path,
            token=token,
            json={"expected_version": 0},
        )
    )
    for response in (stale_put, stale_delete):
        assert response.status_code == 409
        assert response.json() == {"detail": "Translation constraint conflict"}

    unavailable_groups = (
        uuid4(),
        tombstoned["group"],
        incomplete["group"],
        inactive["group"],
    )
    for unavailable_group in unavailable_groups:
        unavailable_path = f"{TRANSLATIONS_PATH}/{unavailable_group}/constraints/it"
        for method, payload in (
            ("PUT", {"max_chars": 1, "expected_version": 0}),
            ("DELETE", {"expected_version": 0}),
        ):
            response = asyncio.run(_request(method, unavailable_path, token=token, json=payload))
            assert response.status_code == 404
            assert response.json() == {"detail": "Translation unavailable"}

    wrong_language = asyncio.run(
        _request(
            "PUT",
            f"{TRANSLATIONS_PATH}/{group_id}/constraints/en",
            token=token,
            json={"max_chars": 1, "expected_version": 1},
        )
    )
    assert wrong_language.status_code == 404
    assert wrong_language.json() == {"detail": "Translation unavailable"}

    with constraint_api_session_factory() as session:
        rule = session.scalar(
            select(TranslationConstraint).where(
                TranslationConstraint.translation_key_id == ids["key"]
            )
        )
        assert rule is not None
        assert (rule.max_chars, rule.version) == (1, 1)
        values = tuple(
            session.scalars(
                select(TranslationValue)
                .where(TranslationValue.id.in_(ids["values"]))
                .order_by(TranslationValue.id)
            )
        )
        assert {
            (
                value.display_text,
                value.grapheme_count,
                value.effective_max_chars,
                value.is_over_limit,
            )
            for value in values
        } == {("", 0, 1, False), ("e\u0301👩🏽‍💻", 2, 1, True)}


def test_constraint_openapi_contract_has_stable_operations_and_closed_errors() -> None:
    schema = app.openapi()
    path = "/api/v1/translations/{translation_group_id}/constraints/{language}"

    assert schema["paths"][path]["put"]["operationId"] == "putTranslationConstraint"
    assert schema["paths"][path]["delete"]["operationId"] == "deleteTranslationConstraint"
    for method in ("put", "delete"):
        operation = schema["paths"][path][method]
        assert operation["requestBody"]["required"] is True
        assert set(operation["responses"]) == {
            "200",
            "401",
            "403",
            "404",
            "409",
            "422",
            "503",
        }


@pytest.mark.parametrize("method", ["PUT", "DELETE"])
def test_constraint_mutation_cors_preflight_allows_registered_methods(method: str) -> None:
    response = asyncio.run(
        _request(
            "OPTIONS",
            f"{TRANSLATIONS_PATH}/{uuid4()}/constraints/it",
            token=None,
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": method,
            },
        )
    )

    assert response.status_code == 200
    assert method in response.headers["access-control-allow-methods"]
