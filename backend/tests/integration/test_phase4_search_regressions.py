"""Independent-review regressions over real PostgreSQL search authority."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import text

from alembic import command
from tests.integration.test_migrations import migrated_database
from tests.integration.test_translation_constraints import (
    _seed_constraint_dataset,
)
from tests.integration.test_translation_search import (
    _add_group,
    _search,
    _seed_dataset,
    clean_search_database,
    search_session_factory,
)
from verboflex.models.import_job import ImportExecution, ImportJob
from verboflex.models.translation import LocalizationScope
from verboflex.models.user import User
from verboflex.services.translation_constraints import (
    delete_translation_constraint,
    put_translation_constraint,
)
from verboflex.services.translation_search import (
    InvalidTranslationCursor,
    TranslationSearchFilters,
    get_translation_group,
)

__all__ = ["clean_search_database", "search_session_factory", "migrated_database"]


def test_separate_repository_detail_projects_base_default_before_and_after_override_removal(
    search_session_factory,
):
    ids = _seed_constraint_dataset(search_session_factory)
    import_id, execution_id = uuid4(), uuid4()
    now = datetime.now(UTC)
    with search_session_factory.begin() as session:
        session.add(
            ImportJob(
                id=import_id,
                product_id=ids["product"],
                revision_id=ids["revision"],
                mapping_id=ids["mapping"],
                topology="separate",
                state="running",
                current_execution_id=execution_id,
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
                state="succeeded",
                connection_generation=1,
                started_at=now,
                finished_at=now,
            )
        )
        session.flush()
        job = session.get_one(ImportJob, import_id)
        job.state = "current"
        job.active_baseline_execution_id = execution_id
        session.flush()
        scope = session.get_one(LocalizationScope, ids["scope"])
        scope.active_import_job_id = import_id
        scope.active_execution_id = execution_id
        scope.dataset_version = 1
        put_translation_constraint(
            session,
            translation_group_id=ids["base_value"],
            language="en",
            max_chars=3,
            expected_version=0,
            actor_id=ids["actor"],
        )
    with search_session_factory() as session:
        inherited = get_translation_group(session, group_id=ids["target_value"])
    assert inherited.base_maximum == 3
    assert inherited.explicit_maximum is None
    assert inherited.values[0].constraint.maximum == 3
    assert inherited.values[0].constraint.source == "base_default"
    with search_session_factory.begin() as session:
        override = put_translation_constraint(
            session,
            translation_group_id=ids["target_value"],
            language="it",
            max_chars=8,
            expected_version=0,
            actor_id=ids["actor"],
        )
    with search_session_factory.begin() as session:
        removed = delete_translation_constraint(
            session,
            translation_group_id=ids["target_value"],
            language="it",
            expected_version=override.version,
        )
    with search_session_factory() as session:
        restored = get_translation_group(session, group_id=ids["target_value"])
    assert removed.explicit_maximum is None
    assert restored.base_maximum == 3
    assert restored.explicit_maximum is None
    assert restored.values[0].constraint.maximum == 3
    assert restored.values[0].constraint.status == "over_limit"


def test_long_key_boundary_cursor_is_bounded_and_preserves_exact_order(search_session_factory):
    product_id, scope_id = _seed_dataset(search_session_factory)
    ids = []
    for index in range(51):
        ids.append(
            _add_group(
                search_session_factory,
                product_id=product_id,
                scope_id=scope_id,
                raw_key=f"{index:03d}" + "k" * 1600,
                language="en",
                values=({},),
            )
        )
    principal = uuid4()
    first = _search(search_session_factory, principal_id=principal)
    assert [item.id for item in first.items] == ids[:50]
    assert first.next_cursor is not None
    assert len(first.next_cursor) <= 2048
    second = _search(search_session_factory, principal_id=principal, cursor=first.next_cursor)
    assert [item.id for item in second.items] == ids[50:]
    assert second.next_cursor is None


@pytest.mark.parametrize("original,folded", [("ﬀ", "ff"), ("ς", "σ"), ("ﬃ", "ffi")])
@pytest.mark.parametrize("field", ["raw_key", "source_text", "display_text"])
def test_unicode_caseless_matching_agrees_for_key_source_and_target(
    search_session_factory, original, folded, field
):
    product_id, scope_id = _seed_dataset(search_session_factory)
    values = {field: original} if field != "raw_key" else {}
    group_id = _add_group(
        search_session_factory,
        product_id=product_id,
        scope_id=scope_id,
        raw_key=original if field == "raw_key" else "unrelated",
        language="en",
        values=(values,),
    )
    for query in (original, folded, folded.upper()):
        page = _search(
            search_session_factory,
            principal_id=uuid4(),
            filters=TranslationSearchFilters(query=query),
        )
        assert [(item.id, item.rank) for item in page.items] == [(group_id, 0)]


def test_unicode_search_indexes_round_trip_without_changing_external_extension(migrated_database):
    config, engine = migrated_database
    command.upgrade(config, "0018_constraint_generation")
    query = text(
        "SELECT indexname, indexdef FROM pg_indexes WHERE indexname IN "
        "('ix_translation_keys_search_raw_key_pattern',"
        " 'ix_translation_keys_search_raw_key_trgm',"
        " 'ix_translation_values_search_source_text_trgm',"
        " 'ix_translation_values_search_display_text_trgm') ORDER BY indexname"
    )
    with engine.connect() as connection:
        original = dict(connection.execute(query).all())
        extension = connection.execute(
            text("SELECT oid, extversion FROM pg_extension WHERE extname = 'pg_trgm'")
        ).one()
    assert len(original) == 4
    command.upgrade(config, "0019_unicode_search_indexes")
    with engine.connect() as connection:
        updated = dict(connection.execute(query).all())
        assert all(
            "casefold" in definition and "pg_unicode_fast" in definition
            for definition in updated.values()
        )
        assert "256" in updated["ix_translation_keys_search_raw_key_pattern"]
        assert (
            connection.execute(
                text("SELECT oid, extversion FROM pg_extension WHERE extname = 'pg_trgm'")
            ).one()
            == extension
        )
    command.downgrade(config, "0018_constraint_generation")
    with engine.connect() as connection:
        assert dict(connection.execute(query).all()) == original
    command.upgrade(config, "0019_unicode_search_indexes")
    with engine.connect() as connection:
        assert dict(connection.execute(query).all()) == updated


def test_constraint_change_invalidates_search_cursor_but_idempotent_retry_preserves_it(
    search_session_factory,
):
    factory = search_session_factory
    product_id, scope_id = _seed_dataset(factory)
    group_ids = [
        _add_group(
            factory,
            product_id=product_id,
            scope_id=scope_id,
            raw_key=f"constraint-{index:03d}",
            language="en",
            values=({"display_text": "A"},),
        )
        for index in range(51)
    ]
    actor = uuid4()
    with factory.begin() as session:
        session.add(
            User(
                id=actor,
                email=f"cursor-{actor}@example.com",
                display_name="Cursor reviewer",
                hashed_password="unused",
                is_active=True,
                must_change_password=False,
            )
        )
    filters = TranslationSearchFilters(violation="no_max")
    first = _search(factory, principal_id=actor, filters=filters)
    assert first.next_cursor is not None
    with factory.begin() as session:
        changed = put_translation_constraint(
            session,
            translation_group_id=group_ids[0],
            language="en",
            max_chars=0,
            expected_version=0,
            actor_id=actor,
        )
    with pytest.raises(InvalidTranslationCursor):
        _search(factory, principal_id=actor, filters=filters, cursor=first.next_cursor)
    refreshed = _search(factory, principal_id=actor)
    assert refreshed.next_cursor is not None
    with factory.begin() as session:
        unchanged = put_translation_constraint(
            session,
            translation_group_id=group_ids[0],
            language="en",
            max_chars=0,
            expected_version=changed.version,
            actor_id=actor,
        )
    assert unchanged.version == changed.version
    remaining = _search(factory, principal_id=actor, cursor=refreshed.next_cursor)
    assert [item.id for item in remaining.items] == group_ids[50:]
