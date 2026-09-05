"""Authorization-safe current-dataset translation search contracts."""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic.config import Config
from psycopg import connect, sql
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from verboflex.models.import_job import ImportExecution, ImportJob, ImportSourceReference
from verboflex.models.product import Product, ProductRevision
from verboflex.models.product_mapping import (
    ProductMappingAllowedTarget,
    ProductMappingRepositorySide,
    ProductRepositoryMapping,
)
from verboflex.models.repository import Repository
from verboflex.models.translation import (
    LocalizationScope,
    TranslationKey,
    TranslationValue,
    TranslationValueLocator,
)
from verboflex.services.translation_search import (
    InvalidTranslationCursor,
    TranslationSearchFilters,
    TranslationSearchInputError,
    escape_like_literal,
    normalize_search_query,
    search_translations,
)

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ADMIN_DATABASE_URL = os.environ.get(
    "VERBOFLEX_TEST_POSTGRES_ADMIN_URL",
    "postgresql://postgres@127.0.0.1:55432/postgres",
)
CURSOR_SECRET = "translation-search-test-secret-32-bytes"


@pytest.fixture(scope="module")
def search_session_factory() -> Iterator[sessionmaker[Session]]:
    database_name = f"verboflex_translation_search_{uuid4().hex}"
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
        engine.dispose()
        with connect(ADMIN_DATABASE_URL, autocommit=True) as admin_connection:
            admin_connection.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database_name))
            )


@pytest.fixture(autouse=True)
def clean_search_database(
    search_session_factory: sessionmaker[Session],
) -> Iterator[None]:
    with search_session_factory.begin() as session:
        session.execute(text("TRUNCATE products, repositories CASCADE"))
    yield


def _seed_dataset(
    factory: sessionmaker[Session],
    *,
    name: str = "Mobile",
    active: bool = True,
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
    deleted: bool = False,
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
            max_chars = value_data.get("max_chars")
            is_over_limit = bool(
                max_chars is not None and int(value_data.get("grapheme_count", 0)) > max_chars
            )
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
                    grapheme_count=int(value_data.get("grapheme_count", len(display_text))),
                    effective_max_chars=max_chars,
                    effective_constraint_source=(
                        "language_override" if max_chars is not None else "none"
                    ),
                    is_over_limit=is_over_limit,
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


def _search(
    factory: sessionmaker[Session],
    *,
    principal_id: UUID,
    filters: TranslationSearchFilters | None = None,
    cursor: str | None = None,
):
    with factory() as session:
        return search_translations(
            session,
            principal_id=principal_id,
            filters=filters or TranslationSearchFilters(),
            cursor=cursor,
            cursor_secret=CURSOR_SECRET,
        )


def test_query_normalization_bounds_and_like_literals() -> None:
    assert normalize_search_query(None) is None
    assert normalize_search_query("") is None
    assert normalize_search_query("  Verbo\t Flex  ") == "verbo flex"
    assert normalize_search_query("Straße") == "strasse"
    assert escape_like_literal(r"100%_done\\") == r"100\%\_done\\\\"
    with pytest.raises(TranslationSearchInputError, match="query"):
        normalize_search_query("x" * 257)


def test_search_groups_values_ranks_matches_and_preserves_mixed_state(
    search_session_factory: sessionmaker[Session],
) -> None:
    product_id, scope_id = _seed_dataset(search_session_factory)
    principal_id = uuid4()
    _add_group(
        search_session_factory,
        product_id=product_id,
        scope_id=scope_id,
        raw_key="menu.save",
        language="it",
        values=(
            {"source_text": "Save", "display_text": "Salva", "state": "draft"},
            {
                "source_text": "Save many",
                "display_text": "Salva tutti",
                "state": "approved",
                "selector_kind": "android_quantity",
                "max_chars": 4,
                "grapheme_count": 11,
            },
        ),
    )
    _add_group(
        search_session_factory,
        product_id=product_id,
        scope_id=scope_id,
        raw_key="save.later",
        language="it",
        values=({"source_text": "Later", "display_text": "Dopo"},),
    )
    _add_group(
        search_session_factory,
        product_id=product_id,
        scope_id=scope_id,
        raw_key="dialog.action",
        language="it",
        values=({"source_text": "Press Save now", "display_text": "Salva ora"},),
    )

    page = _search(
        search_session_factory,
        principal_id=principal_id,
        filters=TranslationSearchFilters(query="SAVE"),
    )

    assert [(item.raw_key, item.rank) for item in page.items] == [
        ("menu.save", 0),
        ("save.later", 1),
        ("dialog.action", 2),
    ]
    mixed = page.items[0]
    assert mixed.value_count == 2
    assert mixed.states == ("approved", "draft")
    assert mixed.state_summary == "mixed"
    assert mixed.has_over_limit is True
    assert mixed.has_no_max is True


def test_literal_wildcards_unicode_exact_filters_and_deleted_modes(
    search_session_factory: sessionmaker[Session],
) -> None:
    product_id, scope_id = _seed_dataset(search_session_factory)
    inactive_id, inactive_scope_id = _seed_dataset(
        search_session_factory, name="Inactive", active=False
    )
    principal_id = uuid4()
    for raw_key, deleted in (
        ("literal.%_\\quote'", False),
        ("literal.XYquote'", False),
        ("emoji.👩🏽‍💻.Straße", True),
    ):
        _add_group(
            search_session_factory,
            product_id=product_id,
            scope_id=scope_id,
            raw_key=raw_key,
            language="de-DE",
            values=({"source_text": None, "translated_text": None, "display_text": ""},),
            deleted=deleted,
        )
    _add_group(
        search_session_factory,
        product_id=inactive_id,
        scope_id=inactive_scope_id,
        raw_key="literal.%_\\quote'",
        language="de-DE",
        values=({"display_text": "hidden"},),
    )

    literal = _search(
        search_session_factory,
        principal_id=principal_id,
        filters=TranslationSearchFilters(query=r"%_\quote'"),
    )
    assert [item.raw_key for item in literal.items] == ["literal.%_\\quote'"]
    assert literal.items[0].source_text is None
    assert literal.items[0].translated_text is None

    deleted = _search(
        search_session_factory,
        principal_id=principal_id,
        filters=TranslationSearchFilters(query="STRASSE", deleted="deleted"),
    )
    assert [item.raw_key for item in deleted.items] == ["emoji.👩🏽‍💻.Straße"]
    assert deleted.items[0].is_deleted is True

    all_rows = _search(
        search_session_factory,
        principal_id=principal_id,
        filters=TranslationSearchFilters(language="de-DE", deleted="all"),
    )
    assert len(all_rows.items) == 3
    assert (
        _search(
            search_session_factory,
            principal_id=principal_id,
            filters=TranslationSearchFilters(language="de-de", deleted="all"),
        ).items
        == ()
    )
    assert (
        _search(
            search_session_factory,
            principal_id=principal_id,
            filters=TranslationSearchFilters(product_id=inactive_id),
        ).items
        == ()
    )
    assert (
        _search(
            search_session_factory,
            principal_id=principal_id,
            filters=TranslationSearchFilters(product_id=uuid4()),
        ).items
        == ()
    )


def test_state_and_constraint_filters_match_any_member_without_pruning_group(
    search_session_factory: sessionmaker[Session],
) -> None:
    product_id, scope_id = _seed_dataset(search_session_factory)
    principal_id = uuid4()
    _add_group(
        search_session_factory,
        product_id=product_id,
        scope_id=scope_id,
        raw_key="mixed",
        language="en",
        values=(
            {"display_text": "ok", "state": "approved"},
            {
                "display_text": "too long",
                "state": "rejected",
                "max_chars": 3,
                "grapheme_count": 8,
            },
        ),
    )

    for filters in (
        TranslationSearchFilters(state="rejected"),
        TranslationSearchFilters(violation="over_limit"),
        TranslationSearchFilters(violation="no_max"),
    ):
        page = _search(
            search_session_factory,
            principal_id=principal_id,
            filters=filters,
        )
        assert len(page.items) == 1
        assert page.items[0].value_count == 2
        assert page.items[0].states == ("approved", "rejected")


def test_keyset_cursor_is_bounded_tamper_proof_scope_bound_and_stale_safe(
    search_session_factory: sessionmaker[Session],
) -> None:
    product_id, scope_id = _seed_dataset(search_session_factory)
    principal_id = uuid4()
    for number in range(51):
        _add_group(
            search_session_factory,
            product_id=product_id,
            scope_id=scope_id,
            raw_key=f"key.{number:03d}",
            language="en",
            values=({"display_text": f"Value {number}"},),
        )

    first = _search(search_session_factory, principal_id=principal_id)
    assert len(first.items) == 50
    assert first.next_cursor is not None
    assert len(first.next_cursor) <= 2048
    second = _search(
        search_session_factory,
        principal_id=principal_id,
        cursor=first.next_cursor,
    )
    assert len(second.items) == 1
    assert second.next_cursor is None
    assert set(item.id for item in first.items).isdisjoint(item.id for item in second.items)

    with pytest.raises(InvalidTranslationCursor):
        _search(
            search_session_factory,
            principal_id=principal_id,
            cursor=first.next_cursor[:-1] + ("A" if first.next_cursor[-1] != "A" else "B"),
        )
    with pytest.raises(InvalidTranslationCursor):
        _search(
            search_session_factory,
            principal_id=uuid4(),
            cursor=first.next_cursor,
        )
    with pytest.raises(InvalidTranslationCursor):
        _search(
            search_session_factory,
            principal_id=principal_id,
            filters=TranslationSearchFilters(query="key"),
            cursor=first.next_cursor,
        )

    with search_session_factory.begin() as session:
        scope = session.get_one(LocalizationScope, scope_id)
        scope.dataset_version += 1
    with pytest.raises(InvalidTranslationCursor):
        _search(
            search_session_factory,
            principal_id=principal_id,
            cursor=first.next_cursor,
        )


def test_partial_search_plan_can_reach_project_owned_trigram_index(
    search_session_factory: sessionmaker[Session],
) -> None:
    product_id, scope_id = _seed_dataset(search_session_factory)
    _add_group(
        search_session_factory,
        product_id=product_id,
        scope_id=scope_id,
        raw_key="search.index.probe",
        language="en",
        values=({"source_text": "index probe", "display_text": "indice"},),
    )
    with search_session_factory.begin() as session:
        session.execute(text("SET LOCAL enable_seqscan = off"))
        plan = "\n".join(
            session.execute(
                text(
                    "EXPLAIN (COSTS OFF) SELECT id FROM translation_keys "
                    "WHERE replace(lower(raw_key), 'ß', 'ss') LIKE :query ESCAPE '\\'"
                ),
                {"query": "%index%"},
            ).scalars()
        )
    assert "ix_translation_keys_search_raw_key_trgm" in plan
