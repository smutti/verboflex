"""Ordinary authenticated translation search and detail HTTP contracts."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Generator, Iterator, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from alembic.config import Config
from psycopg import connect, sql
from pydantic import SecretStr
from sqlalchemy import create_engine, delete, select, text
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
from verboflex.models.user import User

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ADMIN_DATABASE_URL = os.environ.get(
    "VERBOFLEX_TEST_POSTGRES_ADMIN_URL",
    "postgresql://postgres@127.0.0.1:55432/postgres",
)
SIGNING_SECRET = "0123456789abcdef" * 2
TRANSLATIONS_PATH = "/api/v1/translations"
ROLE_NAMES = ("admin", "product_manager_reviewer", "translator", "viewer")


@pytest.fixture(scope="module")
def translation_api_session_factory() -> Iterator[sessionmaker[Session]]:
    database_name = f"verboflex_translation_api_{uuid4().hex}"
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
def clean_translation_api_database(
    translation_api_session_factory: sessionmaker[Session],
) -> Iterator[None]:
    app.dependency_overrides.clear()
    with translation_api_session_factory.begin() as session:
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
                email=f"translation-{user_id}@example.com",
                display_name="Translation reader",
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


def _seed_dataset(
    factory: sessionmaker[Session],
    *,
    name: str,
    active: bool,
) -> tuple[UUID, UUID]:
    product_id = uuid4()
    revision_id = uuid4()
    repository_id = uuid4()
    mapping_id = uuid4()
    import_id = uuid4()
    execution_id = uuid4()
    scope_id = uuid4()
    now = datetime.now(UTC)
    with factory.begin() as session:
        product = Product(
            id=product_id,
            display_name=name,
            name_key=name.casefold(),
            is_active=active,
        )
        session.add(product)
        session.flush()
        revision = ProductRevision(
            id=revision_id,
            product_id=product_id,
            display_name=name,
            name_key=name.casefold(),
            description="search dataset",
            version=1,
            is_published=False,
            published_at=None,
        )
        repository = Repository(
            id=repository_id,
            workspace="search-team",
            repository_slug=f"search-{repository_id.hex[:12]}",
            descriptive_name=f"{name} translations",
            descriptive_name_key=f"{name.casefold()} translations",
        )
        session.add_all([revision, repository])
        session.flush()
        mapping = ProductRepositoryMapping(
            id=mapping_id,
            revision_id=revision_id,
            topology="direct",
            identity_key=f'["direct","{repository_id}","main"]',
            base_language="en",
            sides=[
                ProductMappingRepositorySide(
                    role="direct",
                    repository_id=repository_id,
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
        product.active_revision_id = revision_id
        session.add(
            ImportJob(
                id=import_id,
                product_id=product_id,
                revision_id=revision_id,
                mapping_id=mapping_id,
                topology="direct",
                state="running",
                current_execution_id=execution_id,
                active_baseline_execution_id=None,
                retry_count=0,
                latest_execution_at=now,
            )
        )
        session.flush()
        session.add(
            ImportExecution(
                id=execution_id,
                import_job_id=import_id,
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
                execution_id=execution_id,
                position=0,
                repository_side="direct",
                repository_id=repository_id,
                source_branch="main",
                commit_hash="a" * 40,
                path="locales/messages.json",
                size_bytes=1,
                sha256="b" * 64,
            )
        )
        session.flush()
        execution = session.get_one(ImportExecution, execution_id)
        execution.state = "succeeded"
        execution.finished_at = now
        import_job = session.get_one(ImportJob, import_id)
        import_job.state = "current"
        import_job.active_baseline_execution_id = execution_id
        session.flush()
        session.add(
            LocalizationScope(
                id=scope_id,
                product_id=product_id,
                mapping_identity_key=mapping.identity_key,
                current_revision_id=revision_id,
                current_mapping_id=mapping_id,
                active_import_job_id=import_id,
                active_execution_id=execution_id,
                dataset_version=1,
            )
        )
    return product_id, scope_id


def _add_group(
    factory: sessionmaker[Session],
    *,
    product_id: UUID,
    scope_id: UUID,
    raw_key: str,
    language: str,
    values: tuple[dict[str, object], ...],
    deleted: bool,
) -> UUID:
    with factory.begin() as session:
        scope = session.get_one(LocalizationScope, scope_id)
        mapping = session.get_one(ProductRepositoryMapping, scope.current_mapping_id)
        repository_id = mapping.sides[0].repository_id
        key = TranslationKey(
            id=uuid4(),
            scope_id=scope_id,
            product_id=product_id,
            repository_id=repository_id,
            configured_branch="main",
            raw_key=raw_key,
            is_deleted=deleted,
            deleted_at=datetime.now(UTC) if deleted else None,
        )
        session.add(key)
        session.flush()
        value_ids: list[UUID] = []
        for position, value_data in enumerate(values):
            value_id = uuid4()
            value_ids.append(value_id)
            display_text = str(value_data.get("display_text", ""))
            maximum = value_data.get("max_chars")
            actual = int(value_data.get("grapheme_count", len(display_text)))
            session.add(
                TranslationValue(
                    id=value_id,
                    scope_id=scope_id,
                    translation_key_id=key.id,
                    language=language,
                    selector_version=1,
                    selector_kind=str(value_data.get("selector_kind", "scalar")),
                    selector_bytes=f"selector-{position}".encode(),
                    selector_digest=f"{position + 1:064x}",
                    source_text=value_data.get("source_text"),
                    translated_text=value_data.get("translated_text"),
                    display_text=display_text,
                    structure=list(value_data.get("structure", [])),
                    review_state=str(value_data.get("state", "draft")),
                    grapheme_count=actual,
                    effective_max_chars=maximum,
                    effective_constraint_source=(
                        "language_override" if maximum is not None else "none"
                    ),
                    is_over_limit=maximum is not None and actual > int(maximum),
                    is_deleted=deleted,
                    deleted_at=datetime.now(UTC) if deleted else None,
                )
            )
            session.flush()
            session.add(
                TranslationValueLocator(
                    value_id=value_id,
                    translation_key_id=key.id,
                    import_job_id=scope.active_import_job_id,
                    import_execution_id=scope.active_execution_id,
                    source_reference_position=0,
                    repository_side="direct",
                    repository_id=repository_id,
                    configured_branch="main",
                    source_commit_hash="a" * 40,
                    format="json",
                    path="locales/messages.json",
                    position=position,
                    structural_address=[raw_key, language, position],
                    line=position + 1,
                    column=1,
                )
            )
    return min(value_ids)


async def _request(
    path: str,
    *,
    token: str | None,
    params: dict[str, object] | None = None,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    headers = {"Authorization": f"Bearer {token}"} if token is not None else None
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path, params=params, headers=headers)


def _seed_visible_group(
    factory: sessionmaker[Session],
    *,
    product_name: str = "Mobile",
    active: bool = True,
    deleted: bool = False,
) -> tuple[UUID, UUID]:
    product_id, scope_id = _seed_dataset(factory, name=product_name, active=active)
    group_id = _add_group(
        factory,
        product_id=product_id,
        scope_id=scope_id,
        raw_key="menu.save<script>alert(1)</script>",
        language="it",
        values=(
            {
                "source_text": None,
                "translated_text": None,
                "display_text": "",
                "state": "draft",
                "structure": [{"kind": "text", "value": ""}],
            },
            {
                "source_text": "Save many",
                "translated_text": "Salva tutti",
                "display_text": "Salva tutti 👩🏽‍💻",
                "state": "approved",
                "selector_kind": "android_quantity",
                "structure": [{"quantity": "other"}],
                "max_chars": 5,
                "grapheme_count": 14,
            },
        ),
        deleted=deleted,
    )
    return product_id, group_id


def test_all_authenticated_roles_can_read_and_anonymous_callers_cannot(
    translation_api_session_factory: sessionmaker[Session],
) -> None:
    _product_id, group_id = _seed_visible_group(translation_api_session_factory)
    _configure_dependencies(translation_api_session_factory)

    for path in (
        f"{TRANSLATIONS_PATH}/options",
        TRANSLATIONS_PATH,
        f"{TRANSLATIONS_PATH}/{group_id}",
    ):
        response = asyncio.run(_request(path, token=None))
        assert response.status_code == 401
        assert response.json() == {"detail": "Invalid access token"}

    for role_name in ROLE_NAMES:
        token = _create_authority(
            translation_api_session_factory,
            role_names=(role_name,),
        )
        for path in (
            f"{TRANSLATIONS_PATH}/options",
            TRANSLATIONS_PATH,
            f"{TRANSLATIONS_PATH}/{group_id}",
        ):
            assert asyncio.run(_request(path, token=token)).status_code == 200


def test_options_are_server_ordered_and_exclude_inactive_datasets(
    translation_api_session_factory: sessionmaker[Session],
) -> None:
    zulu_id, _zulu_group = _seed_visible_group(translation_api_session_factory, product_name="Zulu")
    alpha_id, _alpha_group = _seed_visible_group(
        translation_api_session_factory, product_name="Alpha"
    )
    _hidden_id, _hidden_group = _seed_visible_group(
        translation_api_session_factory,
        product_name="Hidden",
        active=False,
    )
    token = _create_authority(translation_api_session_factory, role_names=("viewer",))
    _configure_dependencies(translation_api_session_factory)

    response = asyncio.run(_request(f"{TRANSLATIONS_PATH}/options", token=token))

    assert response.status_code == 200
    assert response.json() == {
        "products": [
            {"id": str(alpha_id), "name": "Alpha"},
            {"id": str(zulu_id), "name": "Zulu"},
        ],
        "languages": [{"code": "it", "label": "Italian"}],
    }


def test_options_scope_languages_without_narrowing_products_or_enumerating_missing_products(
    translation_api_session_factory: sessionmaker[Session],
) -> None:
    alpha_id, alpha_group = _seed_visible_group(
        translation_api_session_factory, product_name="Alpha"
    )
    beta_id, _ = _seed_visible_group(translation_api_session_factory, product_name="Beta")
    hidden_id, _ = _seed_visible_group(
        translation_api_session_factory, product_name="Hidden", active=False
    )
    with translation_api_session_factory.begin() as session:
        value = session.get(TranslationValue, alpha_group)
        assert value is not None
        value.language = "en"
    token = _create_authority(translation_api_session_factory, role_names=("viewer",))
    _configure_dependencies(translation_api_session_factory)
    products = [{"id": str(alpha_id), "name": "Alpha"}, {"id": str(beta_id), "name": "Beta"}]
    for product_id, languages in [
        (alpha_id, [{"code": "en", "label": "English"}]),
        (beta_id, [{"code": "it", "label": "Italian"}]),
        (hidden_id, []),
        (uuid4(), []),
    ]:
        response = asyncio.run(
            _request(
                f"{TRANSLATIONS_PATH}/options", token=token, params={"product_id": str(product_id)}
            )
        )
        assert response.status_code == 200
        assert response.json() == {"products": products, "languages": languages}


def test_search_uses_closed_bounds_literal_filters_and_fixed_cursor_errors(
    translation_api_session_factory: sessionmaker[Session],
) -> None:
    product_id, group_id = _seed_visible_group(translation_api_session_factory)
    token = _create_authority(translation_api_session_factory, role_names=("translator",))
    _configure_dependencies(translation_api_session_factory)

    response = asyncio.run(
        _request(
            TRANSLATIONS_PATH,
            token=token,
            params={"q": "<script>", "product_id": str(product_id), "language": "it"},
        )
    )
    assert response.status_code == 200
    body = response.json()
    assert body["next_cursor"] is None
    assert body["items"] == [
        {
            "id": str(group_id),
            "product_id": str(product_id),
            "product_name": "Mobile",
            "raw_key": "menu.save<script>alert(1)</script>",
            "language": "it",
            "language_label": "Italian",
            "rank": 2,
            "source_text": "Save many",
            "source_language": "en",
            "translated_text": "Salva tutti",
            "selector_kinds": ["android_quantity", "scalar"],
            "provenance": {
                "repository_name": "Mobile translations",
                "branch": "main",
                "path": "locales/messages.json",
            },
            "value_count": 2,
            "over_limit_count": 1,
            "within_limit_count": 0,
            "no_max_count": 1,
            "states": ["approved", "draft"],
            "state_summary": "mixed",
            "has_over_limit": True,
            "has_no_max": True,
            "is_deleted": False,
        }
    ]

    assert asyncio.run(
        _request(
            TRANSLATIONS_PATH,
            token=token,
            params={"product_id": str(uuid4())},
        )
    ).json() == {"items": [], "next_cursor": None}
    for invalid_params in (
        {"q": "x" * 257},
        {"cursor": "tampered"},
        {"page_size": "49"},
        {"unexpected": "value"},
        {"language": "it_IT"},
    ):
        invalid = asyncio.run(_request(TRANSLATIONS_PATH, token=token, params=invalid_params))
        assert invalid.status_code == 422
        if invalid_params == {"cursor": "tampered"}:
            assert invalid.json() == {"detail": "Invalid translation cursor"}


def test_detail_projects_every_selector_constraint_provenance_and_absence(
    translation_api_session_factory: sessionmaker[Session],
) -> None:
    product_id, group_id = _seed_visible_group(translation_api_session_factory)
    token = _create_authority(translation_api_session_factory, role_names=("viewer",))
    _configure_dependencies(translation_api_session_factory)

    response = asyncio.run(_request(f"{TRANSLATIONS_PATH}/{group_id}", token=token))

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(group_id)
    assert body["product_id"] == str(product_id)
    assert body["raw_key"] == "menu.save<script>alert(1)</script>"
    assert body["language"] == "it"
    assert body["language_label"] == "Italian"
    assert body["state_summary"] == "mixed"
    assert body["is_deleted"] is False
    assert body["pending_change"] is None
    assert body["comments"] == []
    assert len(body["values"]) == 2
    assert {value["selector_kind"] for value in body["values"]} == {
        "scalar",
        "android_quantity",
    }
    empty = next(value for value in body["values"] if value["selector_kind"] == "scalar")
    assert empty["source_text"] is None
    assert empty["translated_text"] is None
    assert empty["display_text"] == ""
    assert empty["constraint"] == {
        "actual": 0,
        "maximum": None,
        "source": "none",
        "status": "no_max",
        "overage": None,
    }
    constrained = next(
        value for value in body["values"] if value["selector_kind"] == "android_quantity"
    )
    assert constrained["constraint"] == {
        "actual": 14,
        "maximum": 5,
        "source": "language_override",
        "status": "over_limit",
        "overage": 9,
    }
    assert constrained["provenance"] == {
        "repository_id": constrained["provenance"]["repository_id"],
        "repository_name": "Mobile translations",
        "repository_side": "direct",
        "branch": "main",
        "path": "locales/messages.json",
        "format": "json",
        "commit_hash": "a" * 40,
        "execution_id": constrained["provenance"]["execution_id"],
        "line": 2,
        "column": 1,
    }
    assert constrained["structure"] == [{"quantity": "other"}]


def test_deleted_detail_remains_reachable_and_inaccessible_ids_do_not_enumerate(
    translation_api_session_factory: sessionmaker[Session],
) -> None:
    _active_product, deleted_group_id = _seed_visible_group(
        translation_api_session_factory,
        product_name="Deleted",
        deleted=True,
    )
    _inactive_product, inaccessible_group_id = _seed_visible_group(
        translation_api_session_factory,
        product_name="Inactive",
        active=False,
    )
    token = _create_authority(translation_api_session_factory, role_names=("viewer",))
    _configure_dependencies(translation_api_session_factory)

    deleted = asyncio.run(_request(f"{TRANSLATIONS_PATH}/{deleted_group_id}", token=token))
    assert deleted.status_code == 200
    assert deleted.json()["is_deleted"] is True
    assert all(value["is_deleted"] for value in deleted.json()["values"])

    for group_id in (uuid4(), inaccessible_group_id):
        unavailable = asyncio.run(_request(f"{TRANSLATIONS_PATH}/{group_id}", token=token))
        assert unavailable.status_code == 404
        assert unavailable.json() == {"detail": "Translation unavailable"}


def test_detail_never_accepts_a_non_group_member_uuid(
    translation_api_session_factory: sessionmaker[Session],
) -> None:
    _product_id, group_id = _seed_visible_group(translation_api_session_factory)
    with translation_api_session_factory() as session:
        non_group_uuid = (
            session.execute(
                select(TranslationValue.id)
                .where(TranslationValue.translation_key_id == TranslationValue.translation_key_id)
                .where(TranslationValue.id != group_id)
            )
            .scalars()
            .first()
        )
    assert non_group_uuid is not None
    token = _create_authority(translation_api_session_factory, role_names=("viewer",))
    _configure_dependencies(translation_api_session_factory)

    response = asyncio.run(_request(f"{TRANSLATIONS_PATH}/{non_group_uuid}", token=token))
    assert response.status_code == 404
    assert response.json() == {"detail": "Translation unavailable"}
