"""Synthetic import-to-capture authority and failure regression tests."""

import asyncio
import base64
import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import delete, event, select

from tests.integration.test_translation_import_activation import (
    _seed_running_separate_import,
    activation_session_factory,  # noqa: F401
    clean_activation_database,  # noqa: F401
)
from tests.legacy_product_fixtures import shared_reader
from verboflex.auth.principal import Principal, get_current_principal
from verboflex.core.config import Settings, get_settings
from verboflex.db.session import get_db_session
from verboflex.localization.code_keys.catalog import CodeSourceConfig, extract_catalog
from verboflex.localization.code_keys.join import join_code_translations
from verboflex.localization.importing.core import CanonicalParserInput
from verboflex.main import app
from verboflex.models.product_member import ProductMember
from verboflex.models.screenshot import ScreenshotJob
from verboflex.models.translation import TranslationValue
from verboflex.schemas.screenshots import ScreenshotRequest
from verboflex.schemas.users import RoleName
from verboflex.services import screenshots
from verboflex.services.import_jobs import ImportSourceReferenceRecord, finish_import_execution
from verboflex.services.translation_imports import stage_translation_parse, staged_manifest_digest
from verboflex.worker import screenshot_tasks

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a7n8AAAAASUVORK5CYII="
)


@pytest.fixture
def capture_data(activation_session_factory, monkeypatch):  # noqa: F811
    factory = activation_session_factory
    # Synthetic API tests must never publish jobs to an external broker.
    monkeypatch.setattr(screenshot_tasks.app, "send_task", lambda *args, **kwargs: None)
    with factory.begin() as session:
        session.execute(delete(ScreenshotJob))
    identity, keys_repo, translations_repo = _seed_running_separate_import(factory)
    config = CodeSourceConfig.model_validate(
        {
            "compose": {
                "runner_profile": "synthetic",
                "preview_functions": ["demo.PreviewScreen"],
            }
        }
    )
    catalog = extract_catalog(
        {
            "app/Screen.kt": b"""package demo
fun Screen() = Res.strings.title
@Preview @Composable fun PreviewScreen() { Screen() }
"""
        },
        config,
    )
    joined = join_code_translations(
        catalog,
        (
            CanonicalParserInput(
                format="android_xml",
                repository_side="translations",
                path="res/values/strings.xml",
                content=b'<resources><string name="title">Welcome</string></resources>',
                layout_identity="res",
                layout_version=1,
                base_language="en",
            ),
            CanonicalParserInput(
                format="android_xml",
                repository_side="translations",
                path="res/values-it/strings.xml",
                content=b'<resources><string name="title">Benvenuto</string></resources>',
                layout_identity="res",
                layout_version=1,
                base_language="en",
            ),
        ),
    )
    refs = tuple(
        ImportSourceReferenceRecord(
            position=index,
            repository_side=role,
            repository_id=repo,
            source_branch="main",
            commit_hash=("a" if role == "keys" else "c") * 40,
            path=path,
            size_bytes=100,
            sha256="b" * 64,
        )
        for index, (role, repo, path) in enumerate(
            (
                ("keys", keys_repo, "app/Screen.kt"),
                ("translations", translations_repo, "res/values/strings.xml"),
                ("translations", translations_repo, "res/values-it/strings.xml"),
            )
        )
    )
    manifest = stage_translation_parse(
        factory,
        identity=identity,
        references=refs,
        result=joined.result,
        code_catalog={
            "catalog": catalog.model_dump(mode="json"),
            "config": config.model_dump(mode="json"),
            "missing_keys": [],
            "missing_base_keys": [],
            "orphan_keys": [],
        },
    )
    assert manifest is not None
    with factory() as session:
        assert staged_manifest_digest(session, identity=identity) == manifest.digest
    assert finish_import_execution(
        factory, identity=identity, references=refs, canonical_manifest_digest=manifest.digest
    )
    actor = shared_reader(factory)
    principal = Principal(actor, "reader@example.com", "Reader", (RoleName.VIEWER,), False)
    with factory() as session:
        group_id = session.scalar(
            select(TranslationValue.id).where(TranslationValue.language == "it")
        )
        assert group_id is not None
    yield factory, identity, principal, group_id
    app.dependency_overrides.clear()


def _request(factory, principal, group_id, job_id=None, **kwargs):
    with factory.begin() as session:
        return screenshots.request_capture(
            session,
            principal,
            group_id,
            job_id or uuid4(),
            ScreenshotRequest(preview_function="demo.PreviewScreen", **kwargs),
            runner_enabled=True,
        )


def _capture_client(factory, principal, *, before_commit=None):
    def database():
        with factory() as session:
            if before_commit is not None:
                event.listen(session, "before_commit", before_commit)
            yield session

    app.dependency_overrides[get_db_session] = database
    app.dependency_overrides[get_current_principal] = lambda: principal
    app.dependency_overrides[get_settings] = lambda: Settings(screenshot_runner_command=["runner"])
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
    )


def test_api_dispatches_committed_uuid_and_duplicate_delivery_renders_once(
    capture_data, monkeypatch
):
    factory, identity, principal, group_id = capture_data
    job_id = uuid4()
    sent, rendered = [], []

    def send(task, **options):
        # A separate transaction must see the snapshot before Celery receives it.
        with factory() as session:
            row = session.get_one(ScreenshotJob, job_id)
            assert row.state == "queued"
            assert row.inputs["import_execution_id"] == str(identity.execution_id)
        sent.append((task, options))

    monkeypatch.setattr(screenshot_tasks.app, "send_task", send)
    monkeypatch.setattr(screenshot_tasks, "render", lambda inputs: rendered.append(inputs) or PNG)

    async def exercise():
        async with _capture_client(factory, principal) as client:
            path = f"/api/v1/translations/{group_id}/screenshots/{job_id}"
            body = {"preview_function": "demo.PreviewScreen"}
            for _ in range(2):
                response = await client.put(path, json=body)
                assert response.status_code == 202 and response.json()["state"] == "queued"
            assert (
                sent
                == [
                    (
                        "verboflex.screenshot.run",
                        {
                            "args": [str(job_id)],
                            "queue": "screenshots",
                            "serializer": "json",
                            "retry": False,
                        },
                    )
                ]
                * 2
            )
            assert rendered == []
            conflict = await client.put(path, json={**body, "theme": "dark"})
            assert conflict.status_code == 409 and len(sent) == 2
            for _ in sent:
                screenshot_tasks.execute_capture(job_id, factory)
            assert len(rendered) == 1
            completed = await client.put(path, json=body)
            assert completed.status_code == 202 and completed.json()["state"] == "succeeded"
            assert len(sent) == 2
            with factory.begin() as session:
                session.get_one(
                    ProductMember, (identity.product_id, principal.user_id)
                ).active = False
            denied = await client.put(path, json=body)
            assert denied.status_code == 404 and len(sent) == 2

    asyncio.run(exercise())


def test_api_broker_failure_keeps_accepted_job_for_reconciliation(
    capture_data, monkeypatch, caplog
):
    factory, _, principal, group_id = capture_data
    job_id = uuid4()
    # Alembic disables pre-existing loggers while preparing this test database.
    monkeypatch.setattr(screenshots.logger, "disabled", False)
    caplog.set_level(logging.WARNING, logger=screenshots.__name__)

    def unavailable(*args, **kwargs):
        raise RuntimeError("synthetic-private-broker-credentials")

    monkeypatch.setattr(screenshot_tasks.app, "send_task", unavailable)

    async def exercise():
        async with _capture_client(factory, principal) as client:
            response = await client.put(
                f"/api/v1/translations/{group_id}/screenshots/{job_id}",
                json={"preview_function": "demo.PreviewScreen"},
            )
            assert response.status_code == 202 and response.json()["state"] == "queued"
            assert "synthetic-private" not in response.text

    asyncio.run(exercise())
    assert "recovery pending" in caplog.text
    assert "synthetic-private" not in caplog.text
    with factory.begin() as session:
        row = session.get_one(ScreenshotJob, job_id)
        assert row.state == "queued" and row.error_code is None
        row.updated_at = datetime.now(UTC) - timedelta(seconds=31)

    sent, rendered = [], []
    monkeypatch.setattr(screenshot_tasks, "SessionFactory", factory)
    monkeypatch.setattr(screenshot_tasks.app, "send_task", lambda *args, **kw: sent.append(kw))
    monkeypatch.setattr(screenshot_tasks, "render", lambda inputs: rendered.append(inputs) or PNG)
    screenshot_tasks.reconcile_screenshots.run()
    screenshot_tasks.reconcile_screenshots.run()
    assert sent == [{"args": [str(job_id)], "queue": "screenshots"}]
    screenshot_tasks.execute_capture(job_id, factory)
    assert len(rendered) == 1
    with factory() as session:
        assert session.get_one(ScreenshotJob, job_id).state == "succeeded"


def test_api_rollback_never_dispatches(capture_data, monkeypatch):
    factory, _, principal, group_id = capture_data
    job_id = uuid4()
    sent = []
    monkeypatch.setattr(screenshot_tasks.app, "send_task", lambda *args, **kw: sent.append(kw))

    def fail_commit(session):
        raise RuntimeError("synthetic commit failure")

    async def exercise():
        async with _capture_client(factory, principal, before_commit=fail_commit) as client:
            response = await client.put(
                f"/api/v1/translations/{group_id}/screenshots/{job_id}",
                json={"preview_function": "demo.PreviewScreen"},
            )
            assert response.status_code == 500

    asyncio.run(exercise())
    assert sent == []
    with factory() as session:
        assert session.get(ScreenshotJob, job_id) is None


def test_snapshot_is_immutable_idempotent_and_not_rendered_by_http(capture_data, monkeypatch):
    factory, identity, principal, group_id = capture_data
    calls = []
    monkeypatch.setattr(screenshot_tasks, "render", lambda payload: calls.append(payload) or PNG)
    job = _request(factory, principal, group_id)
    again = _request(factory, principal, group_id, job.id)
    assert job.id == again.id and calls == []
    assert job.inputs["code_commit"] == "a" * 40
    assert job.inputs["translations_commit"] == "c" * 40
    assert job.inputs["import_execution_id"] == str(identity.execution_id)
    assert [v["text"] for v in job.inputs["values"]] == ["Welcome", "Benvenuto"]
    screenshot_tasks.execute_capture(job.id, factory)
    screenshot_tasks.execute_capture(job.id, factory)
    assert len(calls) == 1
    with factory.begin() as session:
        ready = screenshots.get_capture(session, principal, group_id, job.id)
        assert ready.state == "succeeded" and ready.image == PNG
    with pytest.raises(screenshots.ScreenshotError, match="identity already used"):
        _request(factory, principal, group_id, job.id, theme="dark")


def test_revocation_and_regrant_during_render_never_publishes(capture_data, monkeypatch):
    factory, identity, principal, group_id = capture_data
    job = _request(factory, principal, group_id)

    def renderer(_payload):
        with factory.begin() as session:
            member = session.get_one(ProductMember, (identity.product_id, principal.user_id))
            member.version = uuid4()
        return PNG

    monkeypatch.setattr(screenshot_tasks, "render", renderer)
    screenshot_tasks.execute_capture(job.id, factory)
    with factory() as session:
        row = session.get_one(ScreenshotJob, job.id)
        assert row.state == "failed" and row.image is None
        assert row.error_code == "source_or_access_changed"


def test_cancellation_and_failed_render_cannot_publish_old_image(capture_data, monkeypatch):
    factory, _, principal, group_id = capture_data
    first = _request(factory, principal, group_id)
    with factory.begin() as session:
        session.get_one(ScreenshotJob, first.id).state = "cancelled"

    def fail(_payload):
        raise RuntimeError("synthetic failure containing private build details")

    monkeypatch.setattr(screenshot_tasks, "render", fail)
    screenshot_tasks.execute_capture(first.id, factory)
    second = _request(factory, principal, group_id)
    screenshot_tasks.execute_capture(second.id, factory)
    with factory() as session:
        assert session.get_one(ScreenshotJob, first.id).state == "cancelled"
        failed = session.get_one(ScreenshotJob, second.id)
        assert failed.state == "failed" and failed.image is None
        assert failed.error_code == "render_failed"


def test_api_context_image_and_foreign_access(capture_data, monkeypatch):
    factory, identity, principal, group_id = capture_data

    def database():
        with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = database
    app.dependency_overrides[get_current_principal] = lambda: principal
    app.dependency_overrides[get_settings] = lambda: Settings(screenshot_runner_command=["runner"])
    monkeypatch.setattr(screenshot_tasks, "render", lambda _: PNG)

    async def exercise():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            prefix = f"/api/v1/translations/{group_id}"
            source = await client.get(prefix + "/code-context")
            assert source.status_code == 200
            assert source.json()["previews"][0]["function"] == "demo.PreviewScreen"
            sources = await client.get(f"/api/v1/products/{identity.product_id}/code-sources")
            assert sources.status_code == 200 and len(sources.json()["items"]) == 1
            scope_id = sources.json()["items"][0]["scope_id"]
            catalog_path = f"/api/v1/localization-scopes/{scope_id}/code-keys"
            catalog = await client.get(catalog_path)
            assert catalog.status_code == 200 and catalog.json()["items"][0]["key"] == "title"
            assert (await client.get(prefix + "/screenshots")).json()["items"] == []
            job_id = uuid4()
            response = await client.put(
                prefix + f"/screenshots/{job_id}", json={"preview_function": "demo.PreviewScreen"}
            )
            assert response.status_code == 202
            assert (await client.get(prefix + f"/screenshots/{job_id}")).json()["state"] == "queued"
            assert (await client.get(prefix + f"/screenshots/{job_id}/image")).status_code == 404
            assert len((await client.get(prefix + "/screenshots")).json()["items"]) == 1
            invalid_cursor = await client.get(prefix + f"/screenshots?after={uuid4()}")
            assert invalid_cursor.status_code == 422
            missing = await client.get(prefix + f"/screenshots/{uuid4()}")
            assert missing.status_code == 404
            second_id = uuid4()
            await client.put(
                prefix + f"/screenshots/{second_id}",
                json={
                    "preview_function": "demo.PreviewScreen",
                },
            )
            limited = await client.put(
                prefix + f"/screenshots/{uuid4()}",
                json={
                    "preview_function": "demo.PreviewScreen",
                },
            )
            assert limited.status_code == 429 and limited.headers["retry-after"] == "60"
            cancelled = await client.delete(prefix + f"/screenshots/{second_id}")
            assert cancelled.status_code == 200 and cancelled.json()["state"] == "cancelled"
            screenshot_tasks.execute_capture(job_id, factory)
            image = await client.get(prefix + f"/screenshots/{job_id}/image")
            assert image.status_code == 200 and image.content == PNG
            assert image.headers["cache-control"] == "private, no-store"
            with factory.begin() as session:
                session.get_one(
                    ProductMember, (identity.product_id, principal.user_id)
                ).active = False
            for path in ("/code-context", "/screenshots", f"/screenshots/{job_id}/image"):
                denied = await client.get(prefix + path)
                assert denied.status_code == 404
            assert (await client.get(catalog_path)).status_code == 404
            assert (
                await client.get(f"/api/v1/products/{identity.product_id}/code-sources")
            ).status_code == 404

    asyncio.run(exercise())


def test_quota_and_expiry(capture_data):
    factory, _, principal, group_id = capture_data
    first = _request(factory, principal, group_id)
    _request(factory, principal, group_id)
    with pytest.raises(screenshots.ScreenshotError) as caught:
        _request(factory, principal, group_id)
    assert caught.value.status == 429
    with factory.begin() as session:
        row = session.get_one(ScreenshotJob, first.id)
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    with factory.begin() as session:
        expired = screenshots.get_capture(session, principal, group_id, first.id)
        assert expired.state == "expired" and expired.inputs == {} and expired.image is None


@pytest.mark.parametrize(
    ("state", "age", "expired", "expected", "dispatch"),
    [
        ("queued", 0, False, "queued", False),
        ("queued", 31, False, "queued", True),
        ("queued", 3601, False, "failed", False),
        ("rendering", 151, False, "failed", False),
        ("succeeded", 0, True, "expired", False),
    ],
)
def test_durable_reconciler_dispatches_and_recovers_bounded_jobs(
    capture_data,
    monkeypatch,
    state,
    age,
    expired,
    expected,
    dispatch,
):
    factory, _, principal, group_id = capture_data
    job = _request(factory, principal, group_id)
    now = datetime.now(UTC)
    with factory.begin() as session:
        row = session.get_one(ScreenshotJob, job.id)
        row.state = state
        row.created_at = row.updated_at = now - timedelta(seconds=age)
        if expired:
            row.image = PNG
            row.expires_at = now - timedelta(seconds=1)
    sent = []
    monkeypatch.setattr(screenshot_tasks, "SessionFactory", factory)
    monkeypatch.setattr(
        screenshot_tasks,
        "get_settings",
        lambda: Settings(
            screenshot_timeout_seconds=30,
        ),
    )
    monkeypatch.setattr(screenshot_tasks.app, "send_task", lambda *args, **kw: sent.append(kw))
    screenshot_tasks.reconcile_screenshots.run()
    screenshot_tasks.reconcile_screenshots.run()
    assert sent == ([{"args": [str(job.id)], "queue": "screenshots"}] if dispatch else [])
    with factory() as session:
        row = session.get_one(ScreenshotJob, job.id)
        assert row.state == expected
        if expired:
            assert row.image is None and row.inputs == {}


def test_changed_bundle_and_source_are_rejected_before_render(capture_data, monkeypatch):
    factory, _, principal, group_id = capture_data
    called = []
    monkeypatch.setattr(screenshot_tasks, "render", lambda data: called.append(data) or PNG)
    tampered = _request(factory, principal, group_id)
    with factory.begin() as session:
        session.get_one(ScreenshotJob, tampered.id).inputs = {"unexpected": "changed"}
    screenshot_tasks.execute_capture(tampered.id, factory)
    stale = _request(factory, principal, group_id)
    with factory.begin() as session:
        session.get_one(ScreenshotJob, stale.id).execution_id = uuid4()
    screenshot_tasks.execute_capture(stale.id, factory)
    assert called == []
    with factory() as session:
        assert session.get_one(ScreenshotJob, tampered.id).error_code == "input_changed"
        assert session.get_one(ScreenshotJob, stale.id).error_code == "source_or_access_changed"


def test_catalog_is_product_scoped_and_saved_version_required(capture_data):
    from verboflex.models.translation import LocalizationScope

    factory, identity, principal, group_id = capture_data
    with factory.begin() as session:
        sources = screenshots.code_sources(session, principal, identity.product_id, None)
        assert len(sources.items) == 1 and sources.items[0].key_count == 1
        scope = session.get_one(LocalizationScope, sources.items[0].scope_id)
        catalog = screenshots.catalog_page(session, principal, scope.id, None)
        assert [item.key for item in catalog.items] == ["title"]
        assert screenshots.catalog_page(session, principal, scope.id, "title").items == []
    with pytest.raises(screenshots.ScreenshotError, match="Save and refresh"):
        _request(factory, principal, group_id, proposal_version=99)
    with factory.begin() as session:
        session.get_one(ProductMember, (identity.product_id, principal.user_id)).active = False
    with factory.begin() as session:
        for read in (
            lambda: screenshots.code_sources(session, principal, identity.product_id, None),
            lambda: screenshots.catalog_page(session, principal, scope.id, None),
        ):
            with pytest.raises(screenshots.ScreenshotError) as denied:
                read()
            assert denied.value.status == 404
