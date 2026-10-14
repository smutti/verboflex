"""Imported product coverage through real auth and migrated PostgreSQL."""

from __future__ import annotations

import asyncio
import hashlib
import importlib
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from itertools import islice, product
from string import ascii_lowercase
from threading import get_ident
from uuid import uuid4

import pytest
from sqlalchemy import delete, event, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from verboflex.auth.rate_limits import get_redis_client
from verboflex.main import app
from verboflex.models.auth_session import AuthSession
from verboflex.models.import_job import ImportExecution, ImportJob
from verboflex.models.product import Product, ProductRevision
from verboflex.models.product_mapping import ProductRepositoryMapping
from verboflex.models.translation import LocalizationScope, TranslationKey, TranslationValue
from verboflex.models.user import User

SUPPORT = importlib.import_module("tests.api.test_translation_reviews")


@pytest.fixture(scope="module")
def factory() -> Iterator[sessionmaker[Session]]:
    with SUPPORT._review_database() as result:
        yield result


@pytest.fixture(autouse=True)
def clean_database(factory):
    app.dependency_overrides.clear()
    with factory.begin() as session:
        session.execute(text("TRUNCATE products, repositories CASCADE"))
        session.execute(delete(AuthSession))
        session.execute(delete(User))
    SUPPORT.SUPPORT._configure_dependencies(factory)
    rate_support = importlib.import_module("tests.api.test_rate_limits")
    app.dependency_overrides[get_redis_client] = lambda: rate_support.CountingRedis()
    yield
    app.dependency_overrides.clear()


def authority(factory, role="admin"):
    return SUPPORT.SUPPORT._create_authority(factory, role_names=(role,))


def request(token, product_id):
    return asyncio.run(
        SUPPORT.SUPPORT._request("GET", f"/api/v1/admin/products/{product_id}/summary", token=token)
    )


def add_key(session, ids, name):
    key = TranslationKey(
        scope_id=ids["scope"],
        product_id=ids["product"],
        repository_id=ids["repository"],
        configured_branch="main",
        raw_key=name,
    )
    session.add(key)
    session.flush()
    return key.id


def add_value(
    session,
    ids,
    key,
    language,
    *,
    source=None,
    translated="Filled",
    slot=0,
    structure=None,
    deleted=False,
):
    selector = f'{{"slot":{slot}}}'.encode()
    value = TranslationValue(
        scope_id=ids["scope"],
        translation_key_id=key,
        language=language,
        selector_version=1,
        selector_kind="scalar",
        selector_bytes=selector,
        selector_digest=hashlib.sha256(selector).hexdigest(),
        source_text=source,
        translated_text=translated,
        display_text=translated or source or "",
        structure=structure or [],
        review_state="draft",
        grapheme_count=0,
        effective_constraint_source="none",
        is_over_limit=False,
        is_deleted=deleted,
        deleted_at=datetime.now(UTC) if deleted else None,
    )
    session.add(value)
    return value


def seed_two_keys(factory, name="Coverage"):
    ids = SUPPORT.SUPPORT._seed_constraint_group(factory, name=name, base_language="it")
    with factory.begin() as session:
        second = add_key(session, ids, "second")
        add_value(session, ids, second, "it", source="Second", translated=None)
        add_value(session, ids, ids["key"], "vi", translated="Hoàn thành")
    return {**ids, "second": second}


def test_imported_source_catalog_counts_absent_target_group(factory):
    token = authority(factory)
    ids = seed_two_keys(factory)
    response = request(token, ids["product"])
    assert response.status_code == 200, response.text
    assert response.headers["Cache-Control"] == "private, no-store"
    body = response.json()
    assert body["source_string_count"] == 2
    assert body["target_language_count"] == 1
    assert body["expected_translation_count"] == 2
    assert body["translated_count"] == 1
    assert body["missing_count"] == 1
    assert body["coverage_percent"] == 50
    assert body["imported_scope_count"] == 1
    assert body["unimported_scope_count"] == 0
    assert body["last_imported_at"] is not None
    assert body["languages"] == [
        {
            "language": "vi",
            "expected_count": 2,
            "translated_count": 1,
            "missing_count": 1,
            "coverage_percent": 50,
        }
    ]
    assert body["languages_has_more"] is False


@pytest.mark.parametrize("role", ["anonymous", "viewer", "translator", "product_manager_reviewer"])
def test_only_admin_can_read_summary(factory, role):
    ids = seed_two_keys(factory)
    token = None if role == "anonymous" else authority(factory, role)
    response = request(token, ids["product"])
    assert response.status_code == (401 if role == "anonymous" else 403)


def test_product_not_found_and_deleted_are_indistinguishable(factory):
    token = authority(factory)
    ids = seed_two_keys(factory)
    with factory.begin() as session:
        actor_id = session.scalar(select(User.id))
        row = session.get_one(Product, ids["product"])
        row.is_active = False
        row.deleted_at = datetime.now(UTC)
        row.deleted_by = actor_id
    for product_id in (ids["product"], uuid4()):
        response = request(token, product_id)
        assert response.status_code == 404
        assert response.json() == {"detail": "Product unavailable"}


@pytest.mark.parametrize("kind", ["base_only", "no_baseline", "draft_only", "no_source"])
def test_unknown_or_zero_denominators_are_not_complete(factory, kind):
    token = authority(factory)
    ids = SUPPORT.SUPPORT._seed_constraint_group(
        factory, name=kind, complete_dataset=kind != "no_baseline"
    )
    with factory.begin() as session:
        if kind == "draft_only":
            session.get_one(Product, ids["product"]).active_revision_id = None
        elif kind == "no_source":
            for value in session.scalars(select(TranslationValue)):
                value.source_text = None
                value.language = "vi"
    response = request(token, ids["product"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["expected_translation_count"] == body["missing_count"] == 0
    assert body["translated_count"] == 0
    assert body["coverage_percent"] is None
    assert body["source_string_count"] == (1 if kind == "base_only" else 0)
    assert body["imported_scope_count"] == (1 if kind in {"base_only", "no_source"} else 0)
    assert body["unimported_scope_count"] == (1 if kind == "no_baseline" else 0)
    assert body["target_language_count"] == (1 if kind == "no_source" else 0)
    if kind == "no_source":
        assert body["languages"][0]["coverage_percent"] is None


@pytest.mark.parametrize("missing", [None, "", " \t\n", "\u00a0\u2007\u202f\u3000"])
def test_every_live_variant_must_have_non_whitespace_imported_text(factory, missing):
    token = authority(factory)
    ids = seed_two_keys(factory)
    with factory.begin() as session:
        add_value(session, ids, ids["key"], "vi", translated=missing, slot=1)
    body = request(token, ids["product"]).json()
    assert body["translated_count"] == 0
    assert body["missing_count"] == 2


@pytest.mark.parametrize(
    "selector_kind",
    ["android_quantity", "android_array_item", "qt_numerus", "qt_length_variant", "json_path"],
)
def test_filled_variants_count_once_without_requiring_source_selector_parity(
    factory, selector_kind
):
    token = authority(factory)
    ids = seed_two_keys(factory)
    with factory.begin() as session:
        extra = add_value(session, ids, ids["key"], "vi", translated="Another form", slot=2)
        extra.selector_kind = selector_kind
    body = request(token, ids["product"]).json()
    assert (body["source_string_count"], body["translated_count"], body["missing_count"]) == (
        2,
        1,
        1,
    )


def test_qt_embedded_source_unfinished_and_independent_draft_review_state(factory):
    token = authority(factory)
    ids = SUPPORT.SUPPORT._seed_constraint_group(factory, name="Qt")
    with factory.begin() as session:
        for value in session.scalars(select(TranslationValue)):
            value.language = "vi"
            value.translated_text = "Filled"
            value.source_text = "Embedded source"
        value.structure = [
            {
                "kind": "qt_ts:translation",
                "fields": [
                    {"name": "status", "value": "unfinished"},
                    {"name": "review_state", "value": "draft"},
                ],
            }
        ]
        value_id = value.id
    body = request(token, ids["product"]).json()
    assert (body["source_string_count"], body["translated_count"], body["missing_count"]) == (
        1,
        0,
        1,
    )
    with factory.begin() as session:
        # An unrelated structure node's status must not mark a translation unfinished.
        session.get_one(TranslationValue, value_id).structure = [
            {"kind": "qt_ts:message", "fields": [{"name": "status", "value": "unfinished"}]}
        ]
    body = request(token, ids["product"]).json()
    assert body["translated_count"] == 1
    assert body["coverage_percent"] == 100


def test_deleted_orphan_and_foreign_data_never_inflate_coverage(factory):
    token = authority(factory)
    ids = seed_two_keys(factory)
    seed_two_keys(factory, name="Foreign product")
    with factory.begin() as session:
        orphan = add_key(session, ids, "target.only")
        add_value(session, ids, orphan, "fr")  # Known target, but no source identity.
        add_value(session, ids, ids["second"], "vi", deleted=True)
        add_value(session, ids, ids["second"], "de", source="Deleted", deleted=True)
        deleted_key = add_key(session, ids, "deleted.key")
        row = session.get_one(TranslationKey, deleted_key)
        row.is_deleted, row.deleted_at = True, datetime.now(UTC)
        add_value(session, ids, deleted_key, "es", source="Deleted key")
        add_value(session, ids, ids["key"], "vi", translated=None, deleted=True, slot=2)
    body = request(token, ids["product"]).json()
    assert body["source_string_count"] == 2
    assert body["target_language_count"] == 2
    assert body["expected_translation_count"] == 4
    assert body["translated_count"] == 1
    assert [row["language"] for row in body["languages"]] == ["fr", "vi"]
    assert [row["missing_count"] for row in body["languages"]] == [2, 1]


def test_imported_empty_source_is_still_a_key_and_proposals_do_not_fill_coverage(factory):
    token = authority(factory)
    ids = SUPPORT._seed_scalar_basis(factory, name="Local proposals")
    with factory.begin() as session:
        # The review fixture has embedded source, and one empty imported variant.
        for value in session.scalars(select(TranslationValue)):
            value.language = "fr"
            value.source_text = ""
    # Save an actual pending proposal using the existing real HTTP helper, then
    # compare imported coverage. Its language is inferred from the exact group.
    saved = SUPPORT._save_proposal(ids, token=token)
    assert saved["state"] == "draft"
    body = request(token, ids["product"]).json()
    assert body["source_string_count"] == body["expected_translation_count"] == 1
    assert body["translated_count"] == 0
    assert body["missing_count"] == 1


def test_inactive_product_and_failed_refresh_retain_successful_baseline(factory):
    token = authority(factory)
    ids = seed_two_keys(factory)
    before = request(token, ids["product"]).json()
    with factory.begin() as session:
        session.get_one(Product, ids["product"]).is_active = False
        old = session.get_one(ImportExecution, ids["execution"])
        new = ImportExecution(
            import_job_id=ids["import"],
            sequence=2,
            state="failed",
            connection_generation=1,
            started_at=old.finished_at + timedelta(minutes=1),
            finished_at=old.finished_at + timedelta(minutes=2),
        )
        session.add(new)
        session.flush()
        job = session.get_one(ImportJob, ids["import"])
        job.current_execution_id = new.id
        job.state = "import_failed"
        job.error_category, job.error_message = "provider_unavailable", "Refresh failed"
    response = request(token, ids["product"])
    assert response.status_code == 200, response.text
    assert response.json() == before


@pytest.mark.parametrize("invalid", ["failed_execution", "foreign_execution", "foreign_key"])
def test_only_owned_successful_baselines_and_keys_contribute(factory, invalid):
    token = authority(factory)
    ids = seed_two_keys(factory)
    other = seed_two_keys(factory, name="Another product")
    if invalid == "failed_execution":
        before = request(token, ids["product"]).json()
        with (
            pytest.raises(IntegrityError, match="activation authority violation"),
            factory.begin() as session,
        ):
            now = datetime.now(UTC)
            execution = ImportExecution(
                import_job_id=ids["import"],
                sequence=2,
                state="failed",
                connection_generation=1,
                started_at=now,
                finished_at=now,
            )
            session.add(execution)
            session.flush()
            scope = session.get_one(LocalizationScope, ids["scope"])
            scope.active_execution_id = execution.id
        assert request(token, ids["product"]).json() == before
        return
    with factory.begin() as session:
        # Model constraints normally forbid mismatched ownership. Simulate
        # legacy corruption only in this disposable test database.
        session.execute(text("SET LOCAL session_replication_role = replica"))
        if invalid == "foreign_execution":
            scope = session.get_one(LocalizationScope, ids["scope"])
            scope.active_execution_id = other["execution"]
        else:
            session.get_one(TranslationKey, ids["key"]).product_id = other["product"]
    body = request(token, ids["product"]).json()
    assert body["source_string_count"] == (1 if invalid == "foreign_key" else 0)
    assert body["expected_translation_count"] == body["translated_count"] == 0


def add_retained_scope(factory, ids, *, retain_original=True):
    """Publish a second mapping while keeping the first authentic baseline readable."""
    with factory.begin() as session:
        revision = ProductRevision(
            product_id=ids["product"],
            display_name="Next",
            name_key="next",
            version=2,
            is_published=False,
        )
        session.add(revision)
        session.flush()
        mapping = ProductRepositoryMapping(
            revision_id=revision.id,
            topology="direct",
            identity_key="second-mapping",
            base_language="en",
        )
        pending_mapping = ProductRepositoryMapping(
            revision_id=revision.id,
            topology="direct",
            identity_key="pending-mapping",
            base_language="en",
        )
        if retain_original:
            original = session.get_one(ProductRepositoryMapping, ids["mapping"])
            session.add(
                ProductRepositoryMapping(
                    revision_id=revision.id,
                    topology=original.topology,
                    identity_key=original.identity_key,
                    base_language=original.base_language,
                )
            )
        session.add_all([mapping, pending_mapping])
        session.flush()
        now = datetime.now(UTC)
        revision.is_published, revision.published_at = True, now
        session.flush()
        session.get_one(Product, ids["product"]).active_revision_id = revision.id
        execution_id = uuid4()
        job = ImportJob(
            product_id=ids["product"],
            revision_id=revision.id,
            mapping_id=mapping.id,
            topology="direct",
            state="running",
            current_execution_id=execution_id,
            latest_execution_at=now,
        )
        session.add(job)
        session.flush()
        session.add(
            ImportExecution(
                id=execution_id,
                import_job_id=job.id,
                sequence=1,
                state="succeeded",
                connection_generation=1,
                started_at=now,
                finished_at=now,
            )
        )
        session.flush()
        job.state, job.active_baseline_execution_id = "current", execution_id
        scope = LocalizationScope(
            product_id=ids["product"],
            current_revision_id=revision.id,
            current_mapping_id=mapping.id,
            mapping_identity_key=mapping.identity_key,
            active_import_job_id=job.id,
            active_execution_id=execution_id,
            dataset_version=1,
        )
        session.add(scope)
        session.flush()
        next_ids = {**ids, "scope": scope.id, "mapping": mapping.id, "revision": revision.id}
        key = add_key(session, next_ids, "status.precision")  # Same raw name, distinct scope.
        add_value(session, next_ids, key, "de", source="Embedded", translated="Fertig")
    return next_ids


@pytest.mark.parametrize("retain_original", [False, True])
def test_scope_local_language_denominators_retained_scopes_and_unimported_mapping(
    factory, retain_original
):
    token = authority(factory)
    ids = seed_two_keys(factory)
    add_retained_scope(factory, ids, retain_original=retain_original)
    body = request(token, ids["product"]).json()
    assert body["source_string_count"] == (3 if retain_original else 1)
    assert body["expected_translation_count"] == (3 if retain_original else 1)
    assert body["translated_count"] == (2 if retain_original else 1)
    assert body["imported_scope_count"] == (2 if retain_original else 1)
    assert body["unimported_scope_count"] == (2 if retain_original else 1)
    assert [(row["language"], row["expected_count"]) for row in body["languages"]] == (
        [("vi", 2), ("de", 1)] if retain_original else [("de", 1)]
    )
    search = asyncio.run(
        SUPPORT.SUPPORT._request(
            "GET", f"/api/v1/translations?product_id={ids['product']}", token=token
        )
    )
    assert search.status_code == 200, search.text
    assert {item["language"] for item in search.json()["items"]} == (
        {"it", "vi", "de"} if retain_original else {"de"}
    )


def test_bounded_sorted_languages_keep_all_totals_and_one_read_only_domain_query(factory):
    from verboflex.services.product_summary import get_product_summary

    token = authority(factory)
    ids = seed_two_keys(factory)
    engine = factory.kw["bind"]
    statements = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        with factory() as session:
            get_product_summary(session, product_id=ids["product"])
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert len(statements) == 1
    assert statements[0].lstrip().startswith("WITH product AS")
    with factory.begin() as session:
        for parts in islice(product(ascii_lowercase, repeat=3), 502):
            add_value(session, ids, ids["key"], "".join(parts), translated=None)
    statements.clear()
    event.listen(engine, "before_cursor_execute", capture)
    try:
        with factory() as session:
            result = get_product_summary(session, product_id=ids["product"])
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert len(statements) == 1
    assert statements[0].lstrip().startswith("WITH product AS")
    assert result.target_language_count == 503
    assert result.expected_translation_count == 1006
    assert result.translated_count == 1
    assert result.missing_count == 1005
    assert len(result.languages) == 500
    assert result.languages_has_more is True
    assert [row.language for row in result.languages] == sorted(
        row.language for row in result.languages
    )
    assert request(token, ids["product"]).json() == result.model_dump(mode="json")


def test_sanitized_operational_error(factory, monkeypatch):
    token = authority(factory)
    ids = seed_two_keys(factory)
    routes = importlib.import_module("verboflex.api.v1.routes.admin_products")

    def fail(*args, **kwargs):
        raise RuntimeError("private database URI and provider token")

    monkeypatch.setattr(routes, "get_product_summary", fail)
    response = request(token, ids["product"])
    assert response.status_code == 503
    assert response.json() == {"detail": "Product summary unavailable"}


def test_summary_database_work_runs_outside_the_event_loop(factory, monkeypatch):
    token = authority(factory)
    ids = seed_two_keys(factory)
    routes = importlib.import_module("verboflex.api.v1.routes.admin_products")
    original = routes.get_product_summary
    request_thread = get_ident()
    database_threads = []

    def observe(*args, **kwargs):
        database_threads.append(get_ident())
        return original(*args, **kwargs)

    monkeypatch.setattr(routes, "get_product_summary", observe)
    assert request(token, ids["product"]).status_code == 200
    assert database_threads and all(thread != request_thread for thread in database_threads)
