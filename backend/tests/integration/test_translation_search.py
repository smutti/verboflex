"""Authorization-safe current-dataset translation search contracts."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic.config import Config
from psycopg import connect, sql
from sqlalchemy import create_engine, event, select, text
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
from verboflex.models.review import (
    TranslationComment,
    TranslationProposal,
    TranslationProposalValue,
)
from verboflex.models.translation import (
    LocalizationScope,
    TranslationKey,
    TranslationValue,
    TranslationValueLocator,
    TranslationValueRevision,
)
from verboflex.models.user import User
from verboflex.services.translation_search import (
    CURSOR_VERSION,
    InvalidTranslationCursor,
    TranslationSearchFilters,
    TranslationSearchInputError,
    _canonical_filter,
    _CursorPosition,
    _encode_cursor,
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
    separate: bool = False,
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
        keys_repository = (
            Repository(workspace="search-team", repository_slug=f"keys-{repository_id.hex[:12]}")
            if separate
            else repository
        )
        if separate:
            session.add(keys_repository)
        session.flush()
        mapping = ProductRepositoryMapping(
            id=mapping_id,
            revision_id=revision_id,
            topology="separate" if separate else "direct",
            identity_key=f'["direct","{repository_id}","main"]',
            base_language="en",
            sides=[
                ProductMappingRepositorySide(
                    role="translations" if separate else "direct",
                    repository_id=repository_id,
                    source_branch="main",
                )
            ]
            + (
                [
                    ProductMappingRepositorySide(
                        role="keys", repository_id=keys_repository.id, source_branch="main"
                    )
                ]
                if separate
                else []
            ),
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
                topology="separate" if separate else "direct",
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
                repository_side="translations" if separate else "direct",
                repository_id=repository_id,
                source_branch="main",
                commit_hash="a" * 40,
                path="locales/messages.json",
                size_bytes=1,
                sha256="b" * 64,
            )
        )
        if separate:
            session.add(
                ImportSourceReference(
                    execution_id=execution_id,
                    position=1,
                    repository_side="keys",
                    repository_id=keys_repository.id,
                    source_branch="main",
                    commit_hash="a" * 40,
                    path="source/messages",
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
        side = next(side for side in mapping.sides if side.role in ("direct", "translations"))
        repository_id = side.repository_id
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
                    repository_side=side.role,
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


def _seed_pending_context(
    factory: sessionmaker[Session],
    *,
    group_id: UUID,
    reconciliation_required: bool = False,
) -> None:
    """Persist one complete pending aggregate plus two visible discussion heads."""
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
        actor = User(
            email=f"pending-{uuid4()}@example.com",
            display_name="Pending editor",
            hashed_password="test-only-password-hash",
            is_active=True,
            must_change_password=False,
        )
        session.add(actor)
        session.flush()
        proposal = TranslationProposal(
            scope_id=anchor.scope_id,
            translation_key_id=anchor.translation_key_id,
            language=anchor.language,
            version=3,
            state="draft",
            reconciliation_required=reconciliation_required,
            created_by=actor.id,
            updated_by=actor.id,
        )
        session.add(proposal)
        session.flush()
        for index, value in enumerate(values):
            locator = session.get_one(TranslationValueLocator, value.id)
            revision_digest = f"{index + 101:064x}"
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
                    author_id=actor.id,
                    current_version=1,
                )
            )


def test_work_filter_precedes_pagination_and_proposal_mutations_expire_cursor(
    search_session_factory,
):
    factory = search_session_factory
    product, scope = _seed_dataset(factory)
    for index in range(55):
        _add_group(
            factory,
            product_id=product,
            scope_id=scope,
            raw_key=f"a-filled-{index:03}",
            language="fr",
            values=({"translated_text": "Filled"},),
        )
    expected = []
    for index in range(55):
        expected.append(
            _add_group(
                factory,
                product_id=product,
                scope_id=scope,
                raw_key=f"b-missing-{index:03}",
                language="fr",
                values=({"translated_text": ""},),
            )
        )
    principal = uuid4()
    filters = TranslationSearchFilters(
        product_id=product, language="fr", work_status="needs_translation"
    )
    page = _search(factory, principal_id=principal, filters=filters)
    assert [row.id for row in page.items] == expected[:50]
    assert page.next_cursor
    last = _search(factory, principal_id=principal, filters=filters, cursor=page.next_cursor)
    assert [row.id for row in last.items] == expected[50:]
    assert last.next_cursor is None
    with pytest.raises(InvalidTranslationCursor):
        _search(
            factory,
            principal_id=principal,
            filters=TranslationSearchFilters(
                product_id=product, language="fr", work_status="needs_review"
            ),
            cursor=page.next_cursor,
        )
    _seed_pending_context(factory, group_id=expected[-1])
    with pytest.raises(InvalidTranslationCursor):
        _search(factory, principal_id=principal, filters=filters, cursor=page.next_cursor)


def test_query_normalization_bounds_and_like_literals() -> None:
    assert normalize_search_query(None) is None
    assert normalize_search_query("") is None
    assert normalize_search_query("  Verbo\t Flex  ") == "verbo flex"
    assert normalize_search_query("Straße") == "strasse"
    assert escape_like_literal(r"100%_done\\") == r"100\%\_done\\\\"
    with pytest.raises(TranslationSearchInputError, match="query"):
        normalize_search_query("x" * 257)


def test_search_projects_canonical_row_metadata_without_per_group_queries(
    search_session_factory: sessionmaker[Session],
) -> None:
    product_id, scope_id = _seed_dataset(search_session_factory)
    for index, kind in enumerate(("scalar", "android_quantity", "json_path")):
        _add_group(
            search_session_factory,
            product_id=product_id,
            scope_id=scope_id,
            raw_key=f"unchanged.[{index}]",
            language="it",
            values=({"selector_kind": kind, "source_text": "Source"},),
            deleted=index == 2,
        )
    statements: list[str] = []
    with search_session_factory() as session:
        connection = session.connection()

        def record_statement(_conn, _cursor, statement, _params, _context, _many):
            statements.append(statement)

        event.listen(connection, "before_cursor_execute", record_statement)
        result = search_translations(
            session,
            principal_id=uuid4(),
            filters=TranslationSearchFilters(deleted="all"),
            cursor=None,
            cursor_secret=CURSOR_SECRET,
        )
    assert len(statements) == 2  # Scope digest plus one bounded group projection.
    assert [item.selector_kinds for item in result.items] == [
        ("scalar",),
        ("android_quantity",),
        ("json_path",),
    ]
    assert all(item.source_language == "en" for item in result.items)
    for item in result.items:
        assert item.value_count == 1  # A single structured value is never scalar.
        assert item.provenance is not None
        assert item.provenance.repository_name == "Mobile translations"
        assert item.provenance.branch == "main"
        assert item.provenance.path == "locales/messages.json"
    assert result.items[-1].is_deleted


def test_search_projects_pending_summary_and_comments_without_n_plus_one(
    search_session_factory: sessionmaker[Session],
) -> None:
    product_id, scope_id = _seed_dataset(search_session_factory)
    group_id = _add_group(
        search_session_factory,
        product_id=product_id,
        scope_id=scope_id,
        raw_key="pending.visible",
        language="it",
        values=(
            {"selector_kind": "scalar", "display_text": "Corrente"},
            {"selector_kind": "android_quantity", "display_text": "Correnti"},
        ),
    )
    with search_session_factory.begin() as session:
        anchor = session.get_one(TranslationValue, group_id)
        locator = session.get_one(TranslationValueLocator, group_id)
        french_id = uuid4()
        session.add(
            TranslationValue(
                id=french_id,
                scope_id=anchor.scope_id,
                translation_key_id=anchor.translation_key_id,
                language="fr",
                selector_version=1,
                selector_kind="scalar",
                selector_bytes=b"french-scalar",
                selector_digest="e" * 64,
                source_text="Current",
                translated_text="Courant",
                display_text="Courant",
                structure=[],
                review_state="draft",
                grapheme_count=7,
                effective_max_chars=None,
                effective_constraint_source="none",
                is_over_limit=False,
                is_deleted=False,
                deleted_at=None,
            )
        )
        session.flush()
        session.add(
            TranslationValueLocator(
                value_id=french_id,
                translation_key_id=anchor.translation_key_id,
                import_job_id=locator.import_job_id,
                import_execution_id=locator.import_execution_id,
                source_reference_position=locator.source_reference_position,
                repository_side=locator.repository_side,
                repository_id=locator.repository_id,
                configured_branch=locator.configured_branch,
                source_commit_hash=locator.source_commit_hash,
                format=locator.format,
                path=locator.path,
                position=20,
                structural_address=["pending.visible", "fr"],
                line=20,
                column=1,
            )
        )
    _seed_pending_context(search_session_factory, group_id=group_id)
    statements: list[str] = []
    with search_session_factory() as session:
        connection = session.connection()

        def record_statement(_conn, _cursor, statement, _params, _context, _many):
            statements.append(statement)

        event.listen(connection, "before_cursor_execute", record_statement)
        page = search_translations(
            session,
            principal_id=uuid4(),
            filters=TranslationSearchFilters(),
            cursor=None,
            cursor_secret=CURSOR_SECRET,
        )

    assert len(statements) == 2
    item = next(item for item in page.items if item.language == "it")
    assert item.pending_change is not None
    assert item.pending_change.state == "draft"
    assert item.pending_change.version == 3
    assert item.pending_change.value_count == 2
    assert item.pending_change.reconciliation_required is False
    assert item.comment_count == 2
    other_language = next(item for item in page.items if item.language == "fr")
    assert other_language.pending_change is None
    assert other_language.comment_count == 0


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
    assert mixed.over_limit_count == 1
    assert mixed.within_limit_count == 0
    assert mixed.no_max_count == 1
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
    repeated_second = _search(
        search_session_factory,
        principal_id=principal_id,
        cursor=first.next_cursor,
    )
    assert repeated_second == second

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
            filters=TranslationSearchFilters(product_id=uuid4()),
            cursor=first.next_cursor,
        )

    encoded_body, _ = first.next_cursor.split(".", 1)
    body = base64.urlsafe_b64decode(encoded_body + "=" * (-len(encoded_body) % 4))
    payload = json.loads(body)
    payload["v"] = CURSOR_VERSION + 1
    resigned_body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    resigned_signature = hmac.digest(CURSOR_SECRET.encode(), resigned_body, "sha256")
    wrong_version = ".".join(
        base64.urlsafe_b64encode(part).rstrip(b"=").decode("ascii")
        for part in (resigned_body, resigned_signature)
    )
    with pytest.raises(InvalidTranslationCursor):
        _search(
            search_session_factory,
            principal_id=principal_id,
            cursor=wrong_version,
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


def test_search_cursor_wire_format_is_frozen_for_shared_codec_migration() -> None:
    filters = TranslationSearchFilters(
        query=" Verbo   Flex ",
        product_id=UUID("10000000-0000-4000-8000-000000000001"),
        language="it",
        state="approved",
        violation="within_limit",
        deleted="all",
    )
    position = _CursorPosition(
        rank=2,
        language="it",
        group_id=UUID("20000000-0000-4000-8000-000000000002"),
    )
    cursor = _encode_cursor(
        scope_digest="f" * 64,
        filters=filters,
        position=position,
        cursor_secret=CURSOR_SECRET,
    )

    assert _canonical_filter(filters) == {
        "deleted": "all",
        "language": "it",
        "page_size": 50,
        "product_id": "10000000-0000-4000-8000-000000000001",
        "query": "verbo flex",
        "state": "approved",
        "violation": "within_limit",
    }
    assert len(cursor) == 330
    assert hashlib.sha256(cursor.encode()).hexdigest() == (
        "4314e2414e9e881b1a1ceaee1c5000947c780d9f9374068ff24194bdf23e18bb"
    )


def test_search_page_size_remains_fixed_before_cursor_decode() -> None:
    with pytest.raises(TranslationSearchInputError, match="page size must be 50"):
        TranslationSearchFilters(page_size=49)


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
                    "WHERE casefold(raw_key COLLATE pg_unicode_fast) LIKE :query ESCAPE '\\'"
                ),
                {"query": "%index%"},
            ).scalars()
        )
    assert "ix_translation_keys_search_raw_key_trgm" in plan
