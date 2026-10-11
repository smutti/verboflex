"""Ordinary authenticated translation search and detail HTTP contracts."""

from __future__ import annotations

import asyncio
import json
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
from sqlalchemy import create_engine, delete, event, select, text
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
from verboflex.models.review import (
    TranslationComment,
    TranslationProposal,
    TranslationProposalValue,
)
from verboflex.models.role import Role
from verboflex.models.translation import (
    LocalizationScope,
    TranslationKey,
    TranslationValue,
    TranslationValueLocator,
    TranslationValueRevision,
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
                    selector_bytes=json.dumps(
                        {
                            "version": 1,
                            "kind": str(value_data.get("selector_kind", "scalar")),
                            "fields": {"quantity": "other"}
                            if value_data.get("selector_kind") == "android_quantity"
                            else {},
                        }
                    ).encode(),
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


def _seed_pending_context(
    factory: sessionmaker[Session],
    *,
    group_id: UUID,
    actor_id: UUID,
    reconciliation_required: bool = False,
) -> None:
    with factory.begin() as session:
        anchor = session.get_one(TranslationValue, group_id)
        values = tuple(
            session.scalars(
                select(TranslationValue)
                .where(
                    TranslationValue.translation_key_id == anchor.translation_key_id,
                    TranslationValue.language == anchor.language,
                )
                .order_by(TranslationValue.selector_digest)
            )
        )
        proposal = TranslationProposal(
            scope_id=anchor.scope_id,
            translation_key_id=anchor.translation_key_id,
            language=anchor.language,
            version=4,
            state="draft",
            reconciliation_required=reconciliation_required,
            created_by=actor_id,
            updated_by=actor_id,
        )
        session.add(proposal)
        session.flush()
        for index, value in enumerate(values):
            locator = session.get_one(TranslationValueLocator, value.id)
            revision_digest = f"{index + 201:064x}"
            session.add(
                TranslationValueRevision(
                    value_id=value.id,
                    translation_key_id=value.translation_key_id,
                    revision_number=1,
                    revision_digest=revision_digest,
                    import_job_id=locator.import_job_id,
                    import_execution_id=locator.import_execution_id,
                    source_reference_position=locator.source_reference_position,
                    source_commit_hash=locator.source_commit_hash,
                    source_text=value.source_text,
                    translated_text=value.translated_text,
                    display_text=value.display_text,
                    structure=value.structure,
                    review_state=value.review_state,
                    is_deleted=value.is_deleted,
                    deleted_at=value.deleted_at,
                )
            )
            proposal.values.append(
                TranslationProposalValue(
                    translation_key_id=value.translation_key_id,
                    language=value.language,
                    translation_value_id=value.id,
                    selector_version=value.selector_version,
                    selector_digest=value.selector_digest,
                    basis_revision_number=1,
                    basis_digest=revision_digest,
                    proposed_text="" if index == 0 else "Nuovo 👩🏽‍💻",
                    grapheme_count=999,
                )
            )
        for _ in range(2):
            session.add(
                TranslationComment(
                    scope_id=anchor.scope_id,
                    translation_key_id=anchor.translation_key_id,
                    language=anchor.language,
                    author_id=actor_id,
                    current_version=1,
                )
            )


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


@pytest.mark.parametrize(
    "endpoint",
    ["search", "import-list", "import-detail", "constraint", "proposal", "comment-edit"],
)
def test_scope_lock_wait_keeps_event_loop_live_until_the_owner_releases(
    translation_api_session_factory: sessionmaker[Session], endpoint: str
) -> None:
    factory = translation_api_session_factory
    product_id, group_id = _seed_visible_group(factory, product_name="Lock contention")
    token = _create_authority(factory, role_names=("admin",))
    _configure_dependencies(factory)
    with factory() as session:
        anchor = session.get_one(TranslationValue, group_id)
        scope_id = anchor.scope_id
        scope = session.get_one(LocalizationScope, scope_id)
        import_id = scope.active_import_job_id
        actor_id = session.scalar(select(User.id))
    path = {
        "search": TRANSLATIONS_PATH,
        "import-list": f"/api/v1/admin/products/{product_id}/published/mapping-imports",
        "import-detail": f"/api/v1/admin/products/{product_id}/imports/{import_id}",
        "constraint": f"{TRANSLATIONS_PATH}/{group_id}/constraints/it",
        "proposal": f"{TRANSLATIONS_PATH}/{group_id}/proposal",
        "comment-edit": f"{TRANSLATIONS_PATH}/{group_id}/comments",
    }[endpoint]
    method = "PUT" if endpoint in {"constraint", "proposal", "comment-edit"} else "GET"
    payload = None
    if endpoint == "constraint":
        payload = {"max_chars": 100, "expected_version": 0}
    elif endpoint == "comment-edit":
        payload = {"body": "Edited comment", "expected_version": 1}
    elif endpoint == "proposal":
        assert actor_id is not None
        _seed_pending_context(factory, group_id=group_id, actor_id=actor_id)
        with factory() as session:
            rows = session.execute(
                select(TranslationValue, TranslationValueRevision).join(
                    TranslationValueRevision,
                    TranslationValueRevision.value_id == TranslationValue.id,
                )
            )
            payload = {
                "expected_version": 4,
                "values": [
                    {
                        "translation_value_id": str(value.id),
                        "selector_version": value.selector_version,
                        "selector_digest": value.selector_digest,
                        "basis_revision_number": revision.revision_number,
                        "basis_digest": revision.revision_digest,
                        "proposed_text": "Edited",
                    }
                    for value, revision in rows
                ],
            }

    def bounded_session() -> Generator[Session]:
        with factory() as session:
            # Bound the red phase: a blocked event loop cannot run asyncio timeouts.
            session.execute(text("SET SESSION lock_timeout = '2s'"))
            session.commit()
            try:
                yield session
            finally:
                session.rollback()
                session.execute(text("RESET lock_timeout"))
                session.commit()

    app.dependency_overrides[get_db_session] = bounded_session

    async def run() -> None:
        loop = asyncio.get_running_loop()
        started = asyncio.Event()
        request_path = path
        comment_id = None
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        if endpoint == "comment-edit":
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                created = await client.post(
                    path,
                    json={"body": "Original comment"},
                    headers={"Authorization": f"Bearer {token}"},
                )
            assert created.status_code == 201, created.text
            comment_id = UUID(created.json()["id"])
            request_path = f"{path}/{comment_id}"
        with factory() as owner:
            if comment_id is not None:
                owner.execute(
                    select(TranslationComment)
                    .where(TranslationComment.id == comment_id)
                    .with_for_update()
                )
            else:
                owner.execute(
                    select(LocalizationScope)
                    .where(LocalizationScope.id == scope_id)
                    .with_for_update(read=endpoint != "search")
                )
            owner_pid = owner.scalar(text("SELECT pg_backend_pid()"))
            engine = owner.get_bind()

            def mark_lock_attempt(_connection, _cursor, statement, _params, _context, _many):
                if any(
                    table in statement for table in ("localization_scopes", "translation_comments")
                ) and ("FOR UPDATE" in statement or "FOR SHARE" in statement):
                    loop.call_soon_threadsafe(started.set)

            event.listen(engine, "before_cursor_execute", mark_lock_attempt)
            try:
                async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                    request = asyncio.create_task(
                        client.request(
                            method,
                            request_path,
                            json=payload,
                            headers={"Authorization": f"Bearer {token}"},
                        )
                    )
                    await asyncio.wait_for(started.wait(), timeout=5)
                    try:
                        waiting = 0
                        for _ in range(50):
                            with factory() as observer:
                                waiting = observer.scalar(
                                    text(
                                        "SELECT count(*) FROM pg_stat_activity "
                                        "WHERE :owner = ANY(pg_blocking_pids(pid))"
                                    ),
                                    {"owner": owner_pid},
                                )
                            if waiting:
                                break
                            await asyncio.sleep(0.01)
                        assert waiting == 1, "SQL must wait without occupying the event loop"
                        health = await asyncio.wait_for(client.get("/api/v1/health"), timeout=0.5)
                        assert health.status_code == 200
                        assert not request.done(), "The scope lock must remain effective"
                    finally:
                        owner.rollback()
                        response = await asyncio.wait_for(request, timeout=5)
                    assert response.status_code == 200, response.text
            finally:
                event.remove(engine, "before_cursor_execute", mark_lock_attempt)

    asyncio.run(run())


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
        for member in session.scalars(
            select(TranslationValue).where(
                TranslationValue.translation_key_id == value.translation_key_id
            )
        ):
            member.language = "en"
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
            "pending_change": None,
            "comment_count": 0,
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
    assert body["base_language"] == "en"
    assert body["explicit_maximum"] is None
    assert body["constraint_version"] is None
    assert body["base_maximum"] is None
    assert body["state_summary"] == "mixed"
    assert body["is_deleted"] is False
    assert body["pending_change"] is None
    assert body["comment_count"] == 0
    assert body["mutation_eligible"] is True
    assert body["review_eligible"] is False
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
    assert constrained["selector_fields"] == [{"name": "quantity", "value": "other"}]
    assert constrained["history"] == []
    assert constrained["history_has_more"] is False


def test_detail_projects_complete_pending_aggregate_and_server_eligibility(
    translation_api_session_factory: sessionmaker[Session],
) -> None:
    _product_id, group_id = _seed_visible_group(translation_api_session_factory)
    token = _create_authority(
        translation_api_session_factory,
        role_names=("product_manager_reviewer",),
    )
    with translation_api_session_factory() as session:
        actor_id = session.scalars(select(User)).one().id
    _seed_pending_context(
        translation_api_session_factory,
        group_id=group_id,
        actor_id=actor_id,
    )
    _configure_dependencies(translation_api_session_factory)

    response = asyncio.run(_request(f"{TRANSLATIONS_PATH}/{group_id}", token=token))

    assert response.status_code == 200
    body = response.json()
    assert body["comment_count"] == 2
    assert body["mutation_eligible"] is True
    assert body["review_eligible"] is False  # One pending value exceeds its current maximum.
    pending = body["pending_change"]
    assert pending is not None
    assert pending["state"] == "draft"
    assert pending["version"] == 4
    assert pending["updated_by"] == str(actor_id)
    assert pending["updated_at"]
    assert pending["reconciliation_required"] is False
    assert len(pending["values"]) == 2
    assert {item["translation_value_id"] for item in pending["values"]} == {
        item["id"] for item in body["values"]
    }
    empty = next(item for item in pending["values"] if item["text"] == "")
    assert empty["grapheme_count"] == 0
    assert empty["is_over_limit"] is False
    constrained = next(item for item in pending["values"] if item["text"] != "")
    assert constrained["text"] == "Nuovo 👩🏽‍💻"
    assert constrained["grapheme_count"] == 7
    assert constrained["maximum"] == 5
    assert constrained["is_over_limit"] is True
    assert constrained["approval_eligible"] is False
    assert constrained["submission_eligible"] is False
    assert set(constrained) == {
        "translation_value_id",
        "selector_version",
        "selector_digest",
        "basis_revision_number",
        "basis_digest",
        "text",
        "grapheme_count",
        "maximum",
        "is_over_limit",
        "approval_eligible",
        "submission_eligible",
    }

    with translation_api_session_factory.begin() as session:
        current = session.get_one(TranslationValue, UUID(constrained["translation_value_id"]))
        locator = session.get_one(TranslationValueLocator, current.id)
        session.add(
            TranslationValueRevision(
                value_id=current.id,
                translation_key_id=current.translation_key_id,
                revision_number=2,
                revision_digest="f" * 64,
                import_job_id=locator.import_job_id,
                import_execution_id=locator.import_execution_id,
                source_reference_position=locator.source_reference_position,
                source_commit_hash=locator.source_commit_hash,
                source_text=current.source_text,
                translated_text="Aggiornato",
                display_text="Aggiornato",
                structure=current.structure,
                review_state=current.review_state,
                is_deleted=current.is_deleted,
                deleted_at=current.deleted_at,
            )
        )
    stale = asyncio.run(_request(f"{TRANSLATIONS_PATH}/{group_id}", token=token)).json()
    assert stale["pending_change"]["reconciliation_required"] is True
    assert stale["review_eligible"] is False
    assert all(
        not item["approval_eligible"] and not item["submission_eligible"]
        for item in stale["pending_change"]["values"]
    )


def test_detail_reads_exact_rule_versions_and_bounded_newest_history(
    translation_api_session_factory: sessionmaker[Session],
) -> None:
    from verboflex.models.translation import TranslationValueRevision
    from verboflex.models.translation_constraint import TranslationConstraint

    _, group_id = _seed_visible_group(translation_api_session_factory)
    token = _create_authority(translation_api_session_factory, role_names=("admin",))
    _configure_dependencies(translation_api_session_factory)
    with translation_api_session_factory.begin() as session:
        value = session.get_one(TranslationValue, group_id)
        locator = session.get_one(TranslationValueLocator, group_id)
        actor = session.scalars(select(User)).one()
        for language, maximum, version in (("en", 80, 2), ("it", 5, 3)):
            session.add(
                TranslationConstraint(
                    scope_id=value.scope_id,
                    translation_key_id=value.translation_key_id,
                    language=language,
                    max_chars=maximum,
                    version=version,
                    created_by=actor.id,
                    updated_by=actor.id,
                )
            )
        for number in range(1, 52):
            session.add(
                TranslationValueRevision(
                    value_id=value.id,
                    translation_key_id=value.translation_key_id,
                    revision_number=number,
                    revision_digest=f"{number:064x}",
                    import_job_id=locator.import_job_id,
                    import_execution_id=locator.import_execution_id,
                    source_reference_position=0,
                    source_commit_hash="a" * 40,
                    source_text=None,
                    translated_text="old",
                    display_text="old",
                    structure=[],
                    review_state="approved",
                    is_deleted=False,
                    deleted_at=None,
                )
            )
    response = asyncio.run(_request(f"{TRANSLATIONS_PATH}/{group_id}", token=token))
    assert response.status_code == 200
    body = response.json()
    assert (body["base_maximum"], body["explicit_maximum"], body["constraint_version"]) == (
        80,
        5,
        3,
    )
    value = next(item for item in body["values"] if item["id"] == str(group_id))
    assert value["history_has_more"] is True
    assert [entry["revision_number"] for entry in value["history"]] == list(range(51, 1, -1))
    assert value["history"][0]["review_state"] == "approved"
    assert value["history"][0]["commit_hash"] == "a" * 40
    assert set(value["history"][0]) == {
        "revision_number",
        "revision_digest",
        "review_state",
        "is_deleted",
        "created_at",
        "commit_hash",
        "execution_id",
    }


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
    with translation_api_session_factory() as session:
        actor_id = session.scalars(select(User)).one().id
    _seed_pending_context(
        translation_api_session_factory,
        group_id=deleted_group_id,
        actor_id=actor_id,
    )
    _configure_dependencies(translation_api_session_factory)

    deleted = asyncio.run(_request(f"{TRANSLATIONS_PATH}/{deleted_group_id}", token=token))
    assert deleted.status_code == 200
    assert deleted.json()["is_deleted"] is True
    assert all(value["is_deleted"] for value in deleted.json()["values"])
    assert deleted.json()["pending_change"] is not None
    assert deleted.json()["mutation_eligible"] is False
    assert deleted.json()["review_eligible"] is False
    assert all(
        not item["approval_eligible"] and not item["submission_eligible"]
        for item in deleted.json()["pending_change"]["values"]
    )

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
