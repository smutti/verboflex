"""Personal dashboard contracts exercised through real auth and migrated PostgreSQL."""

from __future__ import annotations

import asyncio
import hashlib
import importlib
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from alembic.config import Config
from sqlalchemy import delete, event, select, text
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from verboflex.auth.access_tokens import decode_access_token
from verboflex.auth.rate_limits import get_redis_client
from verboflex.main import app
from verboflex.models.auth_session import AuthSession
from verboflex.models.import_job import ImportExecution
from verboflex.models.product import Product, ProductRevision
from verboflex.models.review import ReviewActivity, TranslationComment, TranslationCommentVersion
from verboflex.models.submission import ChangeSet, SubmissionBatch, SubmissionReview
from verboflex.models.translation import LocalizationScope, TranslationKey, TranslationValue
from verboflex.models.user import User

SUPPORT = importlib.import_module("tests.api.test_translation_reviews")
PATH = "/api/v1/dashboard"


@pytest.fixture(scope="module")
def factory() -> Iterator[sessionmaker[Session]]:
    with SUPPORT._review_database() as result:
        yield result


@pytest.fixture(autouse=True)
def clean_database(factory: sessionmaker[Session]) -> Iterator[None]:
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


def authority(factory: sessionmaker[Session], role: str = "translator") -> tuple[str, UUID]:
    token = SUPPORT.SUPPORT._create_authority(factory, role_names=(role,))
    return token, decode_access_token(token, settings=SUPPORT.SUPPORT._settings()).user_id


def request(token: str | None, path: str = PATH):
    return asyncio.run(SUPPORT.SUPPORT._request("GET", path, token=token))


def test_saved_proposal_reaches_only_its_actor_and_resolves_exact_group(factory):
    token, actor_id = authority(factory)
    other_token, other_id = authority(factory)
    ids = SUPPORT._seed_scalar_basis(factory, name="Mobile")
    SUPPORT._save_proposal(ids, token=token)
    other = SUPPORT._seed_scalar_basis(factory, name="Other")
    SUPPORT._save_proposal(other, token=other_token)

    statements = []
    engine = factory.kw["bind"]

    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        response = request(token)
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert response.status_code == 200, response.text
    assert response.headers["Cache-Control"] == "private, no-store"
    body = response.json()
    assert set(body) == {"my_activity", "project_updates"}
    mine = body["my_activity"]
    assert mine["has_more"] is False
    assert len(mine["items"]) == 1
    item = mine["items"][0]
    assert item["kind"] == "proposal_saved"
    assert item["event_id"].startswith("review:")
    assert item["actor"]["id"] == str(actor_id)
    assert item["product"]["id"] == str(ids["product"])
    assert item["translation_group_id"] == str(ids["group"])
    assert item["language"] == "it"
    assert {i["actor"]["id"] for i in body["project_updates"]["items"] if i["actor"]} == {
        str(actor_id),
        str(other_id),
    }
    assert all(s.lstrip().split()[0].upper() in {"SELECT", "WITH"} for s in statements)
    detail = request(token, f"/api/v1/translations/{item['translation_group_id']}")
    assert detail.status_code == 200
    assert detail.json()["product_id"] == str(ids["product"])


def test_anonymous_and_empty(factory):
    assert request(None).status_code == 401
    token, _ = authority(factory, "viewer")
    response = request(token)
    assert response.status_code == 200
    assert response.json() == {
        "my_activity": {"items": [], "has_more": False},
        "project_updates": {"items": [], "has_more": False},
    }


@pytest.mark.parametrize("revision", ["0029_bitbucket_workspace", "0030_submission_reviews"])
@pytest.mark.parametrize("populated", [False, True], ids=["empty", "existing-activity"])
def test_schema_upgrade_restores_dashboard_without_changing_existing_data(
    factory, monkeypatch, revision, populated
):
    """Rehearse the skipped deployment migration in the owned disposable database."""
    # Alembic's environment override must never redirect this rehearsal to a shared DB.
    monkeypatch.delenv("VERBOFLEX_DATABASE_URL", raising=False)
    token, _ = authority(factory)
    if populated:
        ids = SUPPORT._seed_scalar_basis(factory, name="Preserved dashboard activity")
        SUPPORT._save_proposal(ids, token=token)

    engine = factory.kw["bind"]
    config = Config(SUPPORT.BACKEND_ROOT / "alembic.ini")
    config.set_main_option("sqlalchemy.url", engine.url.render_as_string(hide_password=False))
    preserved_tables = (
        "users",
        "products",
        "product_revisions",
        "repositories",
        "product_repository_mappings",
        "import_jobs",
        "import_executions",
        "localization_scopes",
        "translation_keys",
        "translation_values",
        "translation_value_revisions",
        "translation_value_locators",
        "translation_proposals",
        "translation_proposal_values",
        "review_activities",
    )

    def snapshot():
        with factory() as session:
            return {
                table: session.scalar(
                    text(
                        "SELECT jsonb_agg("
                        + (
                            "to_jsonb(row) - 'read_version' - 'language_counts' "
                            "- 'coverage_snapshot'"
                            if table == "localization_scopes"
                            else "to_jsonb(row)"
                        )
                        + " ORDER BY to_jsonb(row)) "
                        f"FROM {table} AS row"
                    )
                )
                for table in preserved_tables
            }

    baseline = snapshot()
    try:
        command.downgrade(config, revision)
        with factory() as session:
            assert session.scalar(text("SELECT to_regclass('change_sets')")) is None
        unavailable = request(token)
        assert unavailable.status_code == 503
        assert unavailable.json() == {"detail": "Dashboard unavailable"}

        command.upgrade(config, "head")
        response = request(token)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["my_activity"]["has_more"] is False
        assert body["project_updates"]["has_more"] is False
        assert [item["kind"] for item in body["my_activity"]["items"]] == (
            ["proposal_saved"] if populated else []
        )
        assert {item["kind"] for item in body["project_updates"]["items"]} == (
            {"proposal_saved", "current_import_completed"} if populated else set()
        )
        assert snapshot() == baseline
        assert request(token).json() == body

        # Counterfactual: removing only the new schema brings the error back.
        command.downgrade(config, revision)
        assert request(token).status_code == 503
        command.upgrade(config, "head")
        assert request(token).json() == body
        assert snapshot() == baseline
    finally:
        # Leave the module's disposable fixture at head for adjacent tests.
        command.upgrade(config, "head")


@pytest.mark.parametrize("unavailable", ["inactive", "deleted", "scope", "foreign_key"])
def test_unreadable_groups_are_absent(factory, unavailable):
    token, actor_id = authority(factory)
    ids = SUPPORT._seed_scalar_basis(factory, name="Unavailable")
    SUPPORT._save_proposal(ids, token=token)
    with factory.begin() as session:
        if unavailable == "inactive":
            session.get_one(Product, ids["product"]).is_active = False
        elif unavailable == "deleted":
            product = session.get_one(Product, ids["product"])
            product.deleted_at = datetime.now(UTC)
            product.deleted_by = actor_id
            product.is_active = False
        elif unavailable == "scope":
            scope = session.get_one(LocalizationScope, ids["scope"])
            scope.active_execution_id = None
            scope.active_import_job_id = None
            scope.dataset_version = 0
        else:
            other = SUPPORT._seed_scalar_basis(factory, name="Foreign")
            # Simulate corrupt legacy ownership only in this disposable database.
            session.execute(text("SET LOCAL session_replication_role = replica"))
            session.get_one(TranslationKey, ids["key"]).product_id = other["product"]
    response = request(token)
    assert response.status_code == 200, response.text
    assert response.json()["my_activity"]["items"] == []
    assert not any(
        item["kind"] == "proposal_saved" for item in response.json()["project_updates"]["items"]
    )


def test_operational_errors_are_sanitized(factory, monkeypatch):
    token, _ = authority(factory)
    routes = importlib.import_module("verboflex.api.v1.routes.dashboard")

    def fail(*args, **kwargs):
        raise RuntimeError("private database URI and provider token")

    monkeypatch.setattr(routes, "get_personal_dashboard", fail)
    response = request(token)
    assert response.status_code == 503
    assert response.json() == {"detail": "Dashboard unavailable"}


def seed_submission(factory, ids, actor_id, occurred_at):
    """Persist minimum valid frozen submission metadata, never call a provider."""
    with factory.begin() as session:
        review = SubmissionReview(
            actor_id=actor_id,
            actor_token_version=0,
            product_id=ids["product"],
            revision_id=ids["revision"],
            selection=[],
            input_digest="a" * 64,
            state="queued",
            expires_at=occurred_at + timedelta(days=1),
        )
        session.add(review)
        session.flush()
        batch = SubmissionBatch(
            actor_id=actor_id,
            actor_token_version=0,
            product_id=ids["product"],
            revision_id=ids["revision"],
            review_id=review.id,
            review_attempt=1,
            request_key=uuid4(),
            request_digest="b" * 64,
            content_digest="c" * 64,
        )
        session.add(batch)
        session.flush()
        change_id = uuid4()
        payload = b"private proof bytes never loaded by dashboard"
        session.add(
            ChangeSet(
                id=change_id,
                batch_id=batch.id,
                repository_id=ids["repository"],
                provider_repository_id=uuid4(),
                workspace="example",
                repository_slug="fixture",
                target_branch="main",
                target_head="a" * 40,
                source_branch=f"verboflex/change-set-{change_id}",
                manifest_digest="c" * 64,
                original_proof_digest=hashlib.sha256(payload).hexdigest(),
                original_prepared_payload=payload,
                proposal_count=1,
                value_count=1,
                file_count=1,
                created_at=occurred_at,
                status="succeeded",
                stage="complete",
                finished_at=occurred_at + timedelta(hours=2),
            )
        )
    return change_id


def add_reviews(factory, ids, actor_id, *, count, occurred_at):
    with factory.begin() as session:
        original = session.scalar(
            select(ReviewActivity).where(ReviewActivity.translation_key_id == ids["key"])
        )
        for _ in range(count):
            session.add(
                ReviewActivity(
                    proposal_id=original.proposal_id,
                    translation_key_id=ids["key"],
                    language="it",
                    kind="state_changed",
                    proposal_version=1,
                    from_state="draft",
                    to_state="approved",
                    actor_id=actor_id,
                    created_at=occurred_at,
                )
            )


@pytest.mark.parametrize("role", ["admin", "product_manager_reviewer", "translator", "viewer"])
def test_every_role_can_read(factory, role):
    token, _ = authority(factory, role)
    assert request(token).status_code == 200


@pytest.mark.parametrize("query", ["actor_id", "user_id", "product_id", "limit"])
def test_caller_cannot_override_actor_or_bounds(factory, query):
    token, _ = authority(factory)
    assert request(token, f"{PATH}?{query}={uuid4()}").status_code == 422


def test_comment_versions_preserve_true_actor_time_and_remove_anchor(factory):
    comments = importlib.import_module("tests.api.test_translation_comments")
    token, actor_id = authority(factory)
    admin, admin_id = authority(factory, "admin")
    ids = SUPPORT._seed_scalar_basis(factory, name="Discussion")
    created = comments._create(ids["group"], token=token, body="private original")
    assert created.status_code == 201, created.text
    comment_id = created.json()["id"]
    updated = comments._update(
        ids["group"], comment_id, token=token, body="private edited", expected_version=1
    )
    assert updated.status_code == 200, updated.text
    items = request(token).json()["my_activity"]["items"]
    assert [item["kind"] for item in items] == ["comment_edited", "comment_created"]
    assert all(item["comment_id"] == comment_id for item in items)
    assert all(item["comment_status"] == "available" for item in items)
    removed = asyncio.run(
        comments._request(
            "DELETE", f"/api/v1/translations/{ids['group']}/comments/{comment_id}", token=admin
        )
    )
    assert removed.status_code == 200, removed.text
    response = request(token)
    assert "private original" not in response.text and "private edited" not in response.text
    items = [
        i for i in response.json()["project_updates"]["items"] if i["kind"].startswith("comment_")
    ]
    assert [i["kind"] for i in items] == ["comment_removed", "comment_edited", "comment_created"]
    assert all(i["comment_status"] == "removed" and i["comment_id"] is None for i in items)
    assert all(i["translation_group_id"] == str(ids["group"]) for i in items)
    assert len(request(token).json()["my_activity"]["items"]) == 2
    assert request(admin).json()["my_activity"]["items"][0]["kind"] == "comment_removed"
    with factory() as session:
        versions = {str(v.id): v for v in session.scalars(select(TranslationCommentVersion))}
    for item in items:
        version = versions[item["event_id"].removeprefix("comment-version:")]
        assert datetime.fromisoformat(item["occurred_at"]) == version.created_at
        assert item["actor"]["id"] == str(version.author_id)
    assert {i["actor"]["id"] for i in items} == {str(actor_id), str(admin_id)}


def test_submission_uses_action_time_and_retains_old_revision_history(factory):
    token, actor_id = authority(factory)
    ids = SUPPORT._seed_scalar_basis(factory, name="History")
    SUPPORT._save_proposal(ids, token=token)
    occurred = datetime(2026, 1, 1, tzinfo=UTC)
    change_id = seed_submission(factory, ids, actor_id, occurred)
    with factory.begin() as session:
        product = session.get_one(Product, ids["product"])
        revision = ProductRevision(
            product_id=product.id,
            display_name=product.display_name,
            name_key=product.name_key,
            description="Later published configuration",
            version=2,
            is_published=False,
        )
        session.add(revision)
        session.flush()
        revision.is_published = True
        revision.published_at = datetime.now(UTC)
        session.flush()
        product.active_revision_id = revision.id
    body = request(token).json()
    item = next(i for i in body["my_activity"]["items"] if i["kind"] == "change_set_submitted")
    assert item["change_set_id"] == str(change_id)
    assert item["current_status"] == "succeeded"
    assert datetime.fromisoformat(item["occurred_at"]) == occurred
    assert item["actor"]["id"] == str(actor_id)
    # Retained readable groups must survive the new configuration, too.
    assert any(i["kind"] == "proposal_saved" for i in body["my_activity"]["items"])
    assert request(token, f"/api/v1/translations/{ids['group']}").status_code == 200
    history = request(token, f"/api/v1/products/{ids['product']}/change-sets")
    assert history.status_code == 200, history.text
    assert history.json()["items"][0]["id"] == str(change_id)
    other_token, _ = authority(factory, "viewer")
    assert request(other_token).json()["my_activity"]["items"] == []
    assert any(
        i["kind"] == "change_set_submitted"
        for i in request(other_token).json()["project_updates"]["items"]
    )


def test_active_import_only_finished_time_and_no_actor(factory):
    token, _ = authority(factory)
    ids = SUPPORT._seed_scalar_basis(factory, name="Imports")
    with factory() as session:
        execution = session.get_one(ImportExecution, ids["execution"])
    body = request(token).json()
    assert body["my_activity"]["items"] == []
    assert len(body["project_updates"]["items"]) == 1
    item = body["project_updates"]["items"][0]
    assert item["kind"] == "current_import_completed"
    assert item["actor"] is None
    assert item["event_id"] == f"import:{ids['product']}:{ids['execution']}"
    assert datetime.fromisoformat(item["occurred_at"]) == execution.finished_at
    # A newer successful execution without activation must never appear.
    with factory.begin() as session:
        session.add(
            ImportExecution(
                id=uuid4(),
                import_job_id=ids["import"],
                sequence=2,
                state="succeeded",
                connection_generation=1,
                started_at=datetime.now(UTC),
                finished_at=datetime.now(UTC),
            )
        )
    assert request(token).json() == body


@pytest.mark.parametrize("state", ["failed", "queued", "running"])
def test_non_successful_active_import_is_not_an_event(factory, state):
    token, _ = authority(factory)
    ids = SUPPORT._seed_scalar_basis(factory, name="Not completed")
    with factory.begin() as session:
        # Adversarial legacy pointers; isolated fixture bypasses immutability triggers.
        session.execute(text("SET LOCAL session_replication_role = replica"))
        execution = session.get_one(ImportExecution, ids["execution"])
        execution.state = state
        execution.finished_at = datetime.now(UTC) if state == "failed" else None
        execution.started_at = None if state == "queued" else datetime.now(UTC)
    assert request(token).json()["project_updates"]["items"] == []


def test_actor_and_access_are_applied_before_lookahead(factory):
    token, actor_id = authority(factory)
    other, other_id = authority(factory)
    ids = SUPPORT._seed_scalar_basis(factory, name="Readable")
    hidden = SUPPORT._seed_scalar_basis(factory, name="Hidden")
    SUPPORT._save_proposal(ids, token=token)
    SUPPORT._save_proposal(hidden, token=token)
    now = datetime.now(UTC)
    add_reviews(factory, ids, actor_id, count=11, occurred_at=now)
    add_reviews(factory, ids, other_id, count=20, occurred_at=now + timedelta(days=1))
    add_reviews(factory, hidden, actor_id, count=20, occurred_at=now + timedelta(days=2))
    with factory.begin() as session:
        session.get_one(Product, hidden["product"]).is_active = False
    first = request(token).json()
    assert request(token).json() == first
    mine, project = first["my_activity"], first["project_updates"]
    assert len(mine["items"]) == 3 and mine["has_more"]
    assert len(project["items"]) == 3 and project["has_more"]
    assert all(i["actor"]["id"] == str(actor_id) for i in mine["items"])
    assert all(i["actor"]["id"] == str(other_id) for i in project["items"])
    assert all(i["product"]["id"] == str(ids["product"]) for i in mine["items"] + project["items"])
    assert [i["event_id"] for i in mine["items"]] == sorted(
        (i["event_id"] for i in mine["items"]), reverse=True
    )
    assert request(other).status_code == 200


def test_unresolved_group_anchor_is_not_projected(factory):
    token, _ = authority(factory)
    ids = SUPPORT._seed_scalar_basis(factory, name="No anchor")
    SUPPORT._save_proposal(ids, token=token)
    with factory.begin() as session:
        session.execute(text("SET LOCAL session_replication_role = replica"))
        session.execute(
            delete(TranslationValue).where(TranslationValue.translation_key_id == ids["key"])
        )
    assert request(token).json()["my_activity"]["items"] == []


def test_get_is_constant_statement_count_and_metadata_only(factory, monkeypatch):
    from celery.app.task import Task
    from httpx import AsyncHTTPTransport, HTTPTransport

    from verboflex.services import submission_codec, submissions

    token, actor_id = authority(factory)
    ids = SUPPORT._seed_scalar_basis(factory, name="First")
    SUPPORT._save_proposal(ids, token=token)
    seed_submission(factory, ids, actor_id, datetime.now(UTC))

    def forbidden(*args, **kwargs):
        pytest.fail("dashboard must not call providers, queues, or decode private proofs")

    monkeypatch.setattr(Task, "apply_async", forbidden)
    monkeypatch.setattr(HTTPTransport, "handle_request", forbidden)
    monkeypatch.setattr(AsyncHTTPTransport, "handle_async_request", forbidden)
    monkeypatch.setattr(submission_codec, "decode_prepared_writeback", forbidden)
    monkeypatch.setattr(submissions, "load_change_set_bundle", forbidden)
    statements = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        assert statement.lstrip().split()[0].upper() in {"SELECT", "WITH"}
        for private in (
            "prepared_payload",
            "before_values",
            "after_values",
            "original_bytes",
            "receipt",
            "comment.body",
        ):
            assert private not in statement
        statements.append(statement)

    def read():
        statements.clear()
        engine = factory.kw["bind"]
        event.listen(engine, "before_cursor_execute", capture)
        try:
            result = request(token)
            assert result.status_code == 200, result.text
        finally:
            event.remove(engine, "before_cursor_execute", capture)
        assert sum("WITH readable_groups" in s for s in statements) == 2
        return len(statements)

    first_count = read()
    for index in range(3):
        more = SUPPORT._seed_scalar_basis(factory, name=f"More {index}")
        SUPPORT._save_proposal(more, token=token)
    assert read() == first_count


def test_mixed_source_ties_have_distinct_stable_ids_and_exact_lookahead(factory):
    token, actor_id = authority(factory)
    ids = SUPPORT._seed_scalar_basis(factory, name="Ties")
    SUPPORT._save_proposal(ids, token=token)
    occurred = datetime(2026, 2, 1, tzinfo=UTC)
    seed_submission(factory, ids, actor_id, occurred)
    with factory.begin() as session:
        # Set immutable fixture timestamps only before observing the GET.
        session.execute(text("SET LOCAL session_replication_role = replica"))
        session.scalar(select(ReviewActivity)).created_at = occurred
        session.get_one(ImportExecution, ids["execution"]).finished_at = occurred
        comment = TranslationComment(
            translation_key_id=ids["key"],
            scope_id=ids["scope"],
            language="it",
            author_id=actor_id,
            current_version=1,
        )
        session.add(comment)
        session.flush()
        session.add(
            TranslationCommentVersion(
                id=UUID(str(session.scalar(select(ReviewActivity.id)))),
                comment_id=comment.id,
                translation_key_id=ids["key"],
                language="it",
                author_id=actor_id,
                version_number=1,
                body="not projected",
                created_at=occurred,
            )
        )
    # Four mixed sources plus sixteen reviews is exactly the full page bound.
    add_reviews(factory, ids, actor_id, count=16, occurred_at=occurred)
    first = request(token).json()
    assert request(token).json() == first
    assert len(first["project_updates"]["items"]) == 3
    assert first["project_updates"]["has_more"] is True
    feed = request(token, f"{PATH}/project-updates").json()
    assert len(feed["items"]) == 20 and feed["next_cursor"] is None
    event_ids = [item["event_id"] for item in feed["items"]]
    assert len(set(event_ids)) == 20 and event_ids == sorted(event_ids, reverse=True)
    assert {i["kind"] for i in feed["items"]} >= {
        "proposal_saved",
        "comment_created",
        "change_set_submitted",
        "current_import_completed",
    }
    add_reviews(factory, ids, actor_id, count=1, occurred_at=occurred)
    assert request(token).json()["project_updates"]["has_more"] is True


def test_import_duplicate_and_foreign_execution_pointers(factory):
    token, _ = authority(factory)
    ids = SUPPORT._seed_scalar_basis(factory, name="Import ownership")
    other = SUPPORT._seed_scalar_basis(factory, name="Other import")
    with factory.begin() as session:
        session.execute(text("SET LOCAL session_replication_role = replica"))
        source = session.get_one(LocalizationScope, ids["scope"])
        session.add(
            LocalizationScope(
                product_id=source.product_id,
                mapping_identity_key="legacy-duplicate",
                current_revision_id=source.current_revision_id,
                current_mapping_id=source.current_mapping_id,
                active_import_job_id=source.active_import_job_id,
                active_execution_id=source.active_execution_id,
                dataset_version=1,
            )
        )
    items = request(token).json()["project_updates"]["items"]
    assert sum(i["product"]["id"] == str(ids["product"]) for i in items) == 1
    with factory.begin() as session:
        session.execute(text("SET LOCAL session_replication_role = replica"))
        for scope in session.scalars(
            select(LocalizationScope).where(LocalizationScope.product_id == ids["product"])
        ):
            scope.active_execution_id = other["execution"]
    items = request(token).json()["project_updates"]["items"]
    assert all(i["product"]["id"] != str(ids["product"]) for i in items)


def test_dashboard_uses_ordinary_read_limiter(factory):
    from verboflex.auth.rate_limits import ORDINARY_READ_LIMIT

    token, _ = authority(factory)

    class Limited:
        def eval(self, *args):
            return [ORDINARY_READ_LIMIT + 1, 60]

    app.dependency_overrides[get_redis_client] = Limited
    result = request(token)
    assert result.status_code == 429
    assert result.headers["Retry-After"] == "60"


@pytest.mark.parametrize("feed", ["project-updates", "my-activity"])
def test_project_updates_keyset_pages_ties_without_duplicates_and_excludes_newer_events(
    feed, factory
):
    token, actor = authority(factory)
    ids = SUPPORT._seed_scalar_basis(factory, name="Paged updates")
    SUPPORT._save_proposal(ids, token=token)
    occurred = datetime.now(UTC)
    add_reviews(factory, ids, actor, count=45, occurred_at=occurred)
    with factory() as session:
        expected = {f"review:{id}" for id in session.scalars(select(ReviewActivity.id))}
    first = request(token, f"{PATH}/{feed}")
    assert first.status_code == 200, first.text
    assert first.headers["Cache-Control"] == "private, no-store"
    page = first.json()
    assert len(page["items"]) == 20 and page["next_cursor"]
    collected = page["items"]
    add_reviews(factory, ids, actor, count=1, occurred_at=occurred + timedelta(days=1))
    for _ in range(3):
        if page["next_cursor"] is None:
            break
        response = request(token, f"{PATH}/{feed}?cursor={page['next_cursor']}")
        assert response.status_code == 200, response.text
        page = response.json()
        assert len(page["items"]) <= 20
        collected += page["items"]
    assert page["next_cursor"] is None
    reviews = [item["event_id"] for item in collected if item["event_id"].startswith("review:")]
    assert len(reviews) == len(set(reviews)) == len(expected)
    assert set(reviews) == expected
    assert [(i["occurred_at"], i["event_id"]) for i in collected] == sorted(
        [(i["occurred_at"], i["event_id"]) for i in collected], reverse=True
    )


@pytest.mark.parametrize("feed", ["project-updates", "my-activity"])
def test_project_updates_cursor_is_signed_and_user_bound(feed, factory):
    token, actor = authority(factory)
    other, _ = authority(factory, "viewer")
    ids = SUPPORT._seed_scalar_basis(factory, name="Cursor authority")
    SUPPORT._save_proposal(ids, token=token)
    add_reviews(factory, ids, actor, count=21, occurred_at=datetime.now(UTC))
    cursor = request(token, f"{PATH}/{feed}").json()["next_cursor"]
    assert cursor
    assert request(other, f"{PATH}/{feed}?cursor={cursor}").status_code == 422
    for invalid in ("invalid", cursor + "x", "x" * 2049):
        assert request(token, f"{PATH}/{feed}?cursor={invalid}").status_code == 422
    assert request(token, f"{PATH}/{feed}?limit=100000").status_code == 422
    assert request(None, f"{PATH}/{feed}").status_code == 401
    other_feed = "my-activity" if feed == "project-updates" else "project-updates"
    assert request(token, f"{PATH}/{other_feed}?cursor={cursor}").status_code == 422


def test_personal_activity_filters_actor_before_pagination(factory):
    token, actor = authority(factory)
    other, other_actor = authority(factory)
    ids = SUPPORT._seed_scalar_basis(factory, name="Private feed")
    SUPPORT._save_proposal(ids, token=token)
    now = datetime.now(UTC)
    add_reviews(factory, ids, actor, count=24, occurred_at=now)
    add_reviews(factory, ids, other_actor, count=25, occurred_at=now + timedelta(days=1))
    first = request(token, f"{PATH}/my-activity").json()
    second = request(token, f"{PATH}/my-activity?cursor={first['next_cursor']}").json()
    assert len(first["items"]) == 20 and len(second["items"]) == 5
    assert second["next_cursor"] is None
    assert all(item["actor"]["id"] == str(actor) for item in first["items"] + second["items"])
    assert all(
        item["actor"]["id"] == str(other_actor)
        for item in request(other, f"{PATH}/my-activity").json()["items"]
    )
    for query in ("actor_id", "user_id", "limit"):
        assert request(token, f"{PATH}/my-activity?{query}={other_actor}").status_code == 422


@pytest.mark.parametrize("feed", ["project-updates", "my-activity"])
def test_project_updates_rechecks_visibility_and_sanitizes_failures(feed, factory, monkeypatch):
    token, actor = authority(factory)
    ids = SUPPORT._seed_scalar_basis(factory, name="Visibility")
    SUPPORT._save_proposal(ids, token=token)
    add_reviews(factory, ids, actor, count=21, occurred_at=datetime.now(UTC))
    cursor = request(token, f"{PATH}/{feed}").json()["next_cursor"]
    with factory.begin() as session:
        session.get_one(Product, ids["product"]).is_active = False
    response = request(token, f"{PATH}/{feed}?cursor={cursor}")
    assert response.status_code == 200
    assert response.json() == {"items": [], "next_cursor": None}
    routes = importlib.import_module("verboflex.api.v1.routes.dashboard")

    def fail(*args, **kwargs):
        raise RuntimeError("private URI or provider token")

    monkeypatch.setattr(routes, "get_project_updates", fail)
    response = request(token, f"{PATH}/{feed}")
    assert response.status_code == 503
    assert response.json() == {
        "detail": "Personal activity unavailable"
        if feed == "my-activity"
        else "Project updates unavailable"
    }
