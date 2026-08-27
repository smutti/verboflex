"""Durable administrator preview-job integration contracts."""

from __future__ import annotations

import asyncio
import importlib
import os
import time
from collections.abc import Generator, Iterator
from dataclasses import dataclass, field
from dataclasses import replace as dataclass_replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from alembic.config import Config
from celery import Celery
from psycopg import connect, sql
from pydantic import SecretStr
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from verboflex.auth.access_tokens import issue_access_token
from verboflex.auth.passwords import hash_password
from verboflex.core.config import Settings, get_settings
from verboflex.db.session import get_db_session
from verboflex.integrations.bitbucket.client import (
    BitbucketBranch,
    BitbucketSourceEntry,
    BitbucketSourcePage,
)
from verboflex.main import app
from verboflex.models.auth_session import AuthSession
from verboflex.models.bitbucket_connection import BitbucketConnection
from verboflex.models.preview_job import PreviewJob
from verboflex.models.product import Product, ProductRevision
from verboflex.models.product_mapping import (
    ProductMappingAllowedTarget,
    ProductMappingRepositorySide,
    ProductRepositoryMapping,
)
from verboflex.models.repository import Repository
from verboflex.models.role import Role
from verboflex.models.user import User
from verboflex.services.preview_jobs import (
    PreviewJobConflict,
    PreviewJobNotFound,
    _complete_sides,
    _current_failure_code,
    _finish_preview_job,
    _matches_started_identity,
    _record,
    _start_preview_job,
    create_or_reuse_preview_job,
    execute_preview_job,
    get_preview_job,
    skeleton_preview_processor,
)

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ADMIN_DATABASE_URL = os.environ.get(
    "VERBOFLEX_TEST_POSTGRES_ADMIN_URL",
    "postgresql://postgres@127.0.0.1:55432/postgres",
)
SIGNING_SECRET = "0123456789abcdef" * 2
COMMIT_HASH = "a" * 40


@pytest.fixture(scope="module")
def preview_session_factory() -> Iterator[sessionmaker[Session]]:
    """Migrate one isolated PostgreSQL database for the durable worker proof."""
    database_name = f"verboflex_preview_jobs_{uuid4().hex}"
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
        if hasattr(app.state, "preview_job_enqueuer"):
            del app.state.preview_job_enqueuer
        engine.dispose()
        with connect(ADMIN_DATABASE_URL, autocommit=True) as admin_connection:
            admin_connection.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database_name))
            )


@pytest.fixture(autouse=True)
def clean_preview_database(
    preview_session_factory: sessionmaker[Session],
) -> Iterator[None]:
    """Keep the preview tracer independent from all other integration examples."""
    app.dependency_overrides.clear()
    if hasattr(app.state, "preview_job_enqueuer"):
        del app.state.preview_job_enqueuer
    with preview_session_factory.begin() as session:
        session.execute(text("TRUNCATE products, repositories CASCADE"))
        connection = session.get(BitbucketConnection, 1)
        assert connection is not None
        connection.generation = 0
        connection.access_token_ciphertext = None
        connection.refresh_token_ciphertext = None
        connection.scope_profile = None
        connection.provider_expires_at = None
        connection.connected_at = None
        connection.revoked_at = None
        session.execute(text("TRUNCATE users CASCADE"))
    yield
    app.dependency_overrides.clear()
    if hasattr(app.state, "preview_job_enqueuer"):
        del app.state.preview_job_enqueuer


def _settings() -> Settings:
    return Settings(jwt_secret_key=SecretStr(SIGNING_SECRET))


def _configure_dependencies(factory: sessionmaker[Session]) -> None:
    def override_session() -> Generator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_settings] = _settings


def _create_authority(factory: sessionmaker[Session], *, role_name: str) -> str:
    user_id = uuid4()
    auth_session_id = uuid4()
    now = datetime.now(UTC)
    with factory.begin() as session:
        role = session.execute(select(Role).where(Role.name == role_name)).scalar_one()
        session.add(
            User(
                id=user_id,
                email=f"{role_name}-{user_id}@example.com",
                display_name=role_name.title(),
                hashed_password=hash_password("principal password phrase!"),
                is_active=True,
                must_change_password=False,
                roles=[role],
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
        settings=_settings(),
        now=now,
    )


def _seed_preview_graph(
    factory: sessionmaker[Session],
) -> tuple[UUID, UUID, UUID, UUID]:
    """Create active/candidate revisions, one direct mapping, and OAuth generation."""
    product_id = uuid4()
    active_id = uuid4()
    candidate_id = uuid4()
    repository_id = uuid4()
    mapping_id = uuid4()
    now = datetime.now(UTC)
    with factory.begin() as session:
        product = Product(
            id=product_id,
            display_name=f"Preview Product {product_id}",
            name_key=f"preview product {product_id}",
            is_active=True,
        )
        session.add(product)
        session.flush()
        session.add_all(
            [
                ProductRevision(
                    id=active_id,
                    product_id=product_id,
                    description="published",
                    version=3,
                    is_published=True,
                    published_at=now,
                ),
                ProductRevision(
                    id=candidate_id,
                    product_id=product_id,
                    description="candidate",
                    version=4,
                    is_published=False,
                ),
                Repository(
                    id=repository_id,
                    workspace="preview-team",
                    repository_slug=f"repo-{repository_id.hex[:12]}",
                ),
            ]
        )
        session.flush()
        session.add(
            ProductRepositoryMapping(
                id=mapping_id,
                revision_id=candidate_id,
                topology="direct",
                identity_key=f'["direct","{repository_id}","main"]',
                sides=[
                    ProductMappingRepositorySide(
                        role="direct",
                        repository_id=repository_id,
                        source_branch="main",
                    )
                ],
                allowed_targets=[ProductMappingAllowedTarget(branch="release/1", is_default=True)],
            )
        )
        product.active_revision_id = active_id
        product.candidate_revision_id = candidate_id
        connection = session.get(BitbucketConnection, 1)
        assert connection is not None
        connection.generation = 7
        connection.access_token_ciphertext = "encrypted-access"
        connection.refresh_token_ciphertext = "encrypted-refresh"
        connection.scope_profile = "repository"
        connection.provider_expires_at = now + timedelta(hours=1)
        connection.connected_at = now
        connection.revoked_at = None
    return product_id, active_id, candidate_id, mapping_id


@dataclass
class PersistedUuidEnqueuer:
    """Record the UUID-only payload after proving the queued row already committed."""

    factory: sessionmaker[Session]
    payloads: list[tuple[str]] = field(default_factory=list)

    def __call__(self, job_id: UUID) -> None:
        with self.factory() as session:
            row = session.execute(
                text("SELECT id, state FROM preview_jobs WHERE id = :job_id"),
                {"job_id": job_id},
            ).one()
        assert row.id == job_id
        assert row.state == "queued"
        self.payloads.append((str(job_id),))


@dataclass
class ReadOnlyAndroidSourceAdapter:
    """Provider mock exposing only the Plan 07 read boundary."""

    files: dict[str, bytes]
    events: list[tuple[str, str]] = field(default_factory=list)

    async def resolve_repository_branch(
        self,
        _session: Session,
        *,
        workspace: str,
        repository_slug: str,
        branch: str,
    ) -> BitbucketBranch:
        self.events.append(("resolve", f"{workspace}/{repository_slug}:{branch}"))
        return BitbucketBranch(name=branch, commit_hash=COMMIT_HASH)

    async def list_repository_source_page(
        self,
        _session: Session,
        *,
        workspace: str,
        repository_slug: str,
        commit_hash: str,
        directory_path: str | None,
        next_url: str | None = None,
    ) -> BitbucketSourcePage:
        assert directory_path is None
        assert next_url is None
        self.events.append(("list", f"{workspace}/{repository_slug}@{commit_hash}"))
        return BitbucketSourcePage(
            entries=tuple(
                BitbucketSourceEntry(path=path, kind="file", size=len(content))
                for path, content in reversed(tuple(self.files.items()))
            ),
            next_url=None,
        )

    async def read_repository_source_file(
        self,
        _session: Session,
        *,
        workspace: str,
        repository_slug: str,
        commit_hash: str,
        path: str,
        max_bytes: int,
    ) -> bytes:
        content = self.files[path]
        assert len(content) <= max_bytes
        self.events.append(("read", f"{workspace}/{repository_slug}@{commit_hash}:{path}"))
        return content


async def _request(
    method: str,
    path: str,
    *,
    access_token: str,
    json: dict[str, Any] | None = None,
) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        return await client.request(
            method,
            path,
            headers={"Authorization": f"Bearer {access_token}"},
            json=json,
        )


def test_android_preview_completes_read_only(
    preview_session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Run commit-bound Android discovery through the durable worker and API."""
    _configure_dependencies(preview_session_factory)
    admin_token = _create_authority(preview_session_factory, role_name="admin")
    product_id, _active_id, candidate_id, mapping_id = _seed_preview_graph(preview_session_factory)
    enqueuer = PersistedUuidEnqueuer(preview_session_factory)
    app.state.preview_job_enqueuer = enqueuer
    adapter = ReadOnlyAndroidSourceAdapter(
        files={
            "mobile/src/main/res/values-it/strings.xml": (
                b'<resources><string name="welcome.title">Benvenuto</string>'
                b'<string name="button.ok">Va bene</string></resources>'
            ),
            "mobile/src/main/res/values/strings.xml": (
                b'<resources><string name="welcome.title">Welcome</string>'
                b'<string name="button.ok">OK</string></resources>'
            ),
        }
    )
    path = f"/api/v1/admin/products/{product_id}/candidate/mappings/{mapping_id}/preview-jobs"

    created = asyncio.run(
        _request(
            "POST",
            path,
            access_token=admin_token,
            json={
                "expected_candidate_version": 4,
                "commits": [{"role": "direct", "commit_hash": COMMIT_HASH}],
            },
        )
    )
    assert created.status_code == 202
    created_body = created.json()
    assert created_body["candidate_revision_id"] == str(candidate_id)

    preview_tasks = importlib.import_module("verboflex.worker.preview_tasks")
    process_android_preview = preview_tasks.process_android_preview
    monkeypatch.setattr(preview_tasks, "SessionFactory", preview_session_factory)
    monkeypatch.setattr(
        preview_tasks,
        "preview_processor",
        lambda identity: process_android_preview(
            identity,
            factory=preview_session_factory,
            adapter=adapter,
        ),
    )
    test_celery = Celery(
        "verboflex-android-preview-integration",
        broker="memory://",
        backend="cache+memory://",
    )
    test_celery.task(
        name="verboflex.preview.run",
        serializer="json",
        ignore_result=True,
    )(preview_tasks.run_preview_job.run)
    from celery.contrib.testing.worker import start_worker

    with start_worker(
        test_celery,
        pool="solo",
        perform_ping_check=False,
        loglevel="ERROR",
    ):
        test_celery.send_task("verboflex.preview.run", args=list(enqueuer.payloads[0]))
        deadline = time.monotonic() + 5
        status_body: dict[str, Any] | None = None
        while time.monotonic() < deadline:
            response = asyncio.run(
                _request(
                    "GET",
                    f"/api/v1/admin/preview-jobs/{created_body['id']}",
                    access_token=admin_token,
                )
            )
            assert response.status_code == 200
            status_body = response.json()
            if status_body["state"] in {"succeeded", "failed", "timed_out"}:
                break
            time.sleep(0.02)
    test_celery.close()

    assert status_body is not None
    assert status_body["state"] == "succeeded"
    result = status_body["result"]
    assert result["digest"] == created_body["input_digest"]
    assert len(result["layout_candidates"]) == 1
    layout = result["layout_candidates"][0]
    UUID(layout["id"])
    assert layout == {
        "id": layout["id"],
        "version": 1,
        "repository_side": "direct",
        "format": "android_xml",
        "layout_identity": "mobile/src/main/res",
        "confidence": 1.0,
        "files": [
            "mobile/src/main/res/values-it/strings.xml",
            "mobile/src/main/res/values/strings.xml",
        ],
        "languages": ["default", "it"],
        "keys": ["button.ok", "welcome.title"],
        "samples": [
            {"language": "default", "key": "button.ok", "translation": "OK"},
            {
                "language": "default",
                "key": "welcome.title",
                "translation": "Welcome",
            },
            {"language": "it", "key": "button.ok", "translation": "Va bene"},
            {
                "language": "it",
                "key": "welcome.title",
                "translation": "Benvenuto",
            },
        ],
        "samples_are_partial": True,
    }
    assert [event[0] for event in adapter.events] == ["resolve", "list", "read", "read"]
    assert all(
        COMMIT_HASH in detail or operation == "resolve" for operation, detail in adapter.events
    )
    with preview_session_factory() as session:
        assert session.scalar(text("SELECT count(*) FROM preview_jobs")) == 1
        product = session.get(Product, product_id)
        assert product is not None
        assert product.candidate_revision_id == candidate_id


def test_all_four_formats_return_separate_exact_layout_candidates(
    preview_session_factory: sessionmaker[Session],
) -> None:
    """Persist four deterministic candidates through one durable worker processor."""
    product_id, _active_id, _candidate_id, mapping_id = _seed_preview_graph(
        preview_session_factory
    )
    with preview_session_factory() as session:
        created = create_or_reuse_preview_job(
            session,
            product_id=product_id,
            mapping_id=mapping_id,
            expected_candidate_version=4,
            commits={"direct": COMMIT_HASH},
            enqueuer=lambda _job_id: None,
        )
    adapter = ReadOnlyAndroidSourceAdapter(
        files={
            "mobile/src/main/res/values/strings.xml": (
                b'<resources><string name="hello">Hello</string></resources>'
            ),
            "desktop/app_en.ts": (
                b'<TS version="2.1" language="en"><context><name>Main</name>'
                b'<message><source>hello</source><translation>Hello</translation>'
                b"</message></context></TS>"
            ),
            "web/catalog.json": b'{"en":{"hello":"Hello"}}',
            "ios/en.lproj/Localizable.strings": b'"hello" = "Hello";',
        }
    )
    preview_tasks = importlib.import_module("verboflex.worker.preview_tasks")

    execute_preview_job(
        preview_session_factory,
        job_id=created.id,
        processor=lambda identity: preview_tasks.process_preview(
            identity,
            factory=preview_session_factory,
            adapter=adapter,
        ),
    )

    with preview_session_factory() as session:
        completed = get_preview_job(session, job_id=created.id)
    assert completed.state == "succeeded"
    assert completed.result is not None
    candidates = completed.result["layout_candidates"]
    assert [candidate["format"] for candidate in candidates] == [
        "android_xml",
        "ios_strings",
        "json",
        "qt_ts",
    ]
    assert len({candidate["id"] for candidate in candidates}) == 4
    assert all(candidate["confidence"] == 1.0 for candidate in candidates)
    assert all(candidate["repository_side"] == "direct" for candidate in candidates)
    assert [candidate["files"] for candidate in candidates] == [
        ["mobile/src/main/res/values/strings.xml"],
        ["ios/en.lproj/Localizable.strings"],
        ["web/catalog.json"],
        ["desktop/app_en.ts"],
    ]
    assert [candidate["languages"] for candidate in candidates] == [
        ["default"],
        ["en"],
        ["en"],
        ["en"],
    ]
    assert [candidate["samples"][0]["translation"] for candidate in candidates] == [
        "Hello",
        "Hello",
        "Hello",
        "Hello",
    ]
    assert [event[0] for event in adapter.events] == [
        "resolve",
        "list",
        "read",
        "read",
        "read",
        "read",
    ]


def test_admin_job_runs_api_to_distinct_worker_and_persists_terminal_state(
    preview_session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Trace one UUID from 202 persistence through a Celery worker to PostgreSQL."""
    _configure_dependencies(preview_session_factory)
    admin_token = _create_authority(preview_session_factory, role_name="admin")
    product_id, active_id, candidate_id, mapping_id = _seed_preview_graph(preview_session_factory)
    enqueuer = PersistedUuidEnqueuer(preview_session_factory)
    app.state.preview_job_enqueuer = enqueuer
    path = f"/api/v1/admin/products/{product_id}/candidate/mappings/{mapping_id}/preview-jobs"

    created = asyncio.run(
        _request(
            "POST",
            path,
            access_token=admin_token,
            json={
                "expected_candidate_version": 4,
                "commits": [{"role": "direct", "commit_hash": COMMIT_HASH}],
            },
        )
    )

    assert created.status_code == 202
    created_body = created.json()
    assert created_body["state"] == "queued"
    assert created_body["attempt"] == 1
    assert created_body["candidate_revision_id"] == str(candidate_id)
    assert created_body["candidate_revision_version"] == 4
    assert created_body["connection_generation"] == 7
    assert created_body["is_current"] is True
    assert enqueuer.payloads == [(created_body["id"],)]

    preview_tasks = importlib.import_module("verboflex.worker.preview_tasks")
    monkeypatch.setattr(preview_tasks, "SessionFactory", preview_session_factory)
    monkeypatch.setattr(
        preview_tasks,
        "preview_processor",
        lambda identity: {
            "detector_version": identity.detector_version,
            "digest": identity.input_digest,
            "layout_candidates": [],
        },
    )
    test_celery = Celery(
        "verboflex-preview-integration",
        broker="memory://",
        backend="cache+memory://",
    )
    test_celery.task(
        name="verboflex.preview.run",
        serializer="json",
        ignore_result=True,
    )(preview_tasks.run_preview_job.run)
    from celery.contrib.testing.worker import start_worker

    with start_worker(
        test_celery,
        pool="solo",
        perform_ping_check=False,
        loglevel="ERROR",
    ):
        test_celery.send_task("verboflex.preview.run", args=list(enqueuer.payloads[0]))
        deadline = time.monotonic() + 5
        status_body: dict[str, Any] | None = None
        while time.monotonic() < deadline:
            response = asyncio.run(
                _request(
                    "GET",
                    f"/api/v1/admin/preview-jobs/{created_body['id']}",
                    access_token=admin_token,
                )
            )
            assert response.status_code == 200
            status_body = response.json()
            if status_body["state"] == "succeeded":
                break
            time.sleep(0.02)
    test_celery.close()

    assert status_body is not None
    assert status_body["state"] == "succeeded"
    assert status_body["result"] == {
        "detector_version": "preview-skeleton-v1",
        "digest": created_body["input_digest"],
        "layout_candidates": [],
    }
    assert set(status_body) == {
        "id",
        "input_digest",
        "attempt",
        "state",
        "product_id",
        "candidate_revision_id",
        "candidate_revision_version",
        "mapping_id",
        "connection_generation",
        "detector_version",
        "repository_sides",
        "result",
        "error_code",
        "created_at",
        "started_at",
        "finished_at",
        "is_current",
    }
    assert status_body["repository_sides"] == [
        {
            "role": "direct",
            "repository_id": status_body["repository_sides"][0]["repository_id"],
            "source_branch": "main",
            "commit_hash": COMMIT_HASH,
        }
    ]

    repeated = asyncio.run(
        _request(
            "POST",
            path,
            access_token=admin_token,
            json={
                "expected_candidate_version": 4,
                "commits": [{"role": "direct", "commit_hash": COMMIT_HASH}],
            },
        )
    )
    assert repeated.status_code == 202
    assert repeated.json() == status_body
    assert enqueuer.payloads == [(created_body["id"],)]

    with preview_session_factory() as session:
        product = session.get(Product, product_id)
        assert product is not None
        assert product.active_revision_id == active_id
        assert product.candidate_revision_id == candidate_id
        assert session.scalar(text("SELECT count(*) FROM preview_jobs")) == 1


def test_succeeded_result_remains_inspectable_but_is_not_current_after_revision_change(
    preview_session_factory: sessionmaker[Session],
) -> None:
    """Retain historical output while projecting currentness from live authority."""
    product_id, _active_id, candidate_id, mapping_id = _seed_preview_graph(preview_session_factory)
    with preview_session_factory() as session:
        created = create_or_reuse_preview_job(
            session,
            product_id=product_id,
            mapping_id=mapping_id,
            expected_candidate_version=4,
            commits={"direct": COMMIT_HASH},
            enqueuer=lambda _job_id: None,
        )
    execute_preview_job(
        preview_session_factory,
        job_id=created.id,
        processor=skeleton_preview_processor,
    )
    with preview_session_factory() as session:
        current = get_preview_job(session, job_id=created.id)
    assert current.state == "succeeded"
    assert current.is_current is True
    assert current.result == {
        "detector_version": "preview-skeleton-v1",
        "digest": created.input_digest,
        "layout_candidates": [],
    }

    with preview_session_factory.begin() as session:
        revision = session.get(ProductRevision, candidate_id)
        assert revision is not None
        revision.version = 5

    with preview_session_factory() as session:
        historical = get_preview_job(session, job_id=created.id)
    assert historical.state == "succeeded"
    assert historical.is_current is False
    assert historical.result == current.result


@pytest.mark.parametrize(
    ("field_name", "replacement"),
    [
        ("attempt", 2),
        ("candidate_revision_version", 5),
        ("connection_generation", 8),
        ("detector_version", "preview-skeleton-v2"),
        ("layout_identity", "automatic-layout-discovery-v2"),
    ],
)
def test_terminal_write_requires_the_complete_started_identity(
    preview_session_factory: sessionmaker[Session],
    field_name: str,
    replacement: object,
) -> None:
    """A stale or altered worker identity cannot write a terminal payload."""
    product_id, _active_id, _candidate_id, mapping_id = _seed_preview_graph(preview_session_factory)
    with preview_session_factory() as session:
        created = create_or_reuse_preview_job(
            session,
            product_id=product_id,
            mapping_id=mapping_id,
            expected_candidate_version=4,
            commits={"direct": COMMIT_HASH},
            enqueuer=lambda _job_id: None,
        )
    identity = _start_preview_job(preview_session_factory, job_id=created.id)
    assert identity is not None
    altered = dataclass_replace(identity, **{field_name: replacement})

    _finish_preview_job(
        preview_session_factory,
        identity=altered,
        state="succeeded",
        result={
            "detector_version": identity.detector_version,
            "digest": identity.input_digest,
            "layout_candidates": [],
        },
    )

    with preview_session_factory() as session:
        row = session.get(PreviewJob, created.id)
        assert row is not None
        assert row.state == "running"
        assert row.result is None
        assert row.finished_at is None

    _finish_preview_job(
        preview_session_factory,
        identity=identity,
        state="succeeded",
        result={
            "detector_version": identity.detector_version,
            "digest": identity.input_digest,
            "layout_candidates": [],
        },
    )
    with preview_session_factory() as session:
        completed = get_preview_job(session, job_id=created.id)
    assert completed.state == "succeeded"


@pytest.mark.parametrize(
    "forbidden_field",
    [
        "source_bytes",
        "access_token",
        "provider_body",
        "celery_result",
        "canonical_translation",
        "confirmed",
    ],
)
def test_processor_output_rejects_forbidden_or_noncanonical_fields_without_persisting_them(
    preview_session_factory: sessionmaker[Session],
    forbidden_field: str,
) -> None:
    """Fail closed before arbitrary processor data reaches PostgreSQL or the API."""
    product_id, _active_id, _candidate_id, mapping_id = _seed_preview_graph(preview_session_factory)
    with preview_session_factory() as session:
        created = create_or_reuse_preview_job(
            session,
            product_id=product_id,
            mapping_id=mapping_id,
            expected_candidate_version=4,
            commits={"direct": COMMIT_HASH},
            enqueuer=lambda _job_id: None,
        )

    def unsafe_processor(identity: object) -> dict[str, object]:
        assert hasattr(identity, "input_digest")
        return {
            "detector_version": "preview-skeleton-v1",
            "digest": created.input_digest,
            "layout_candidates": [],
            forbidden_field: "must-not-persist",
        }

    execute_preview_job(
        preview_session_factory,
        job_id=created.id,
        processor=unsafe_processor,
    )

    with preview_session_factory() as session:
        row = session.get(PreviewJob, created.id)
        assert row is not None
        assert row.state == "failed"
        assert row.error_code == "processing_failed"
        assert row.result is None
        assert forbidden_field not in str(row.repository_sides)


@pytest.mark.parametrize(
    "forbidden_field",
    [
        "source_bytes",
        "access_token",
        "provider_body",
        "celery_result",
        "canonical_translation",
        "confirmed",
    ],
)
def test_create_request_rejects_forbidden_or_confirmation_shortcut_fields(
    preview_session_factory: sessionmaker[Session],
    forbidden_field: str,
) -> None:
    """Keep secrets, source content, worker internals, and confirmation out of input."""
    _configure_dependencies(preview_session_factory)
    admin_token = _create_authority(preview_session_factory, role_name="admin")
    product_id, _active_id, _candidate_id, mapping_id = _seed_preview_graph(preview_session_factory)
    app.state.preview_job_enqueuer = PersistedUuidEnqueuer(preview_session_factory)
    path = f"/api/v1/admin/products/{product_id}/candidate/mappings/{mapping_id}/preview-jobs"

    response = asyncio.run(
        _request(
            "POST",
            path,
            access_token=admin_token,
            json={
                "expected_candidate_version": 4,
                "commits": [{"role": "direct", "commit_hash": COMMIT_HASH}],
                forbidden_field: "must-not-accept",
            },
        )
    )

    assert response.status_code == 422
    with preview_session_factory() as session:
        assert session.scalar(text("SELECT count(*) FROM preview_jobs")) == 0


def test_preview_job_model_is_registered_in_explicit_metadata_exports() -> None:
    """Alembic model discovery must not depend on incidental route imports."""
    models = importlib.import_module("verboflex.models")

    assert models.PreviewJob is PreviewJob
    assert models.PreviewJob.__table__.metadata.tables["preview_jobs"] is PreviewJob.__table__


def test_enqueue_failure_is_bounded_current_and_retryable(
    preview_session_factory: sessionmaker[Session],
) -> None:
    """Convert transport failure to a closed durable attempt without leaking the exception."""
    product_id, _active_id, _candidate_id, mapping_id = _seed_preview_graph(preview_session_factory)

    def unavailable_enqueuer(_job_id: UUID) -> None:
        raise RuntimeError("broker diagnostics must not escape")

    with preview_session_factory() as session:
        failed = create_or_reuse_preview_job(
            session,
            product_id=product_id,
            mapping_id=mapping_id,
            expected_candidate_version=4,
            commits={"direct": COMMIT_HASH},
            enqueuer=unavailable_enqueuer,
        )
    assert failed.state == "failed"
    assert failed.error_code == "enqueue_failed"
    assert failed.is_current is True
    assert failed.result is None

    with preview_session_factory() as session:
        retried = create_or_reuse_preview_job(
            session,
            product_id=product_id,
            mapping_id=mapping_id,
            expected_candidate_version=4,
            commits={"direct": COMMIT_HASH},
            enqueuer=lambda _job_id: None,
        )
    assert retried.attempt == 2
    assert retried.state == "queued"


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("state", "provider_raw_state"),
        ("error_code", "provider_exception_body"),
        (
            "result",
            {
                "detector_version": "wrong-version",
                "digest": "f" * 64,
                "layout_candidates": [],
            },
        ),
        (
            "result",
            {
                "detector_version": "preview-skeleton-v1",
                "digest": COMMIT_HASH,
                "layout_candidates": [{}],
            },
        ),
    ],
)
def test_structurally_invalid_persisted_projection_fails_closed(
    preview_session_factory: sessionmaker[Session],
    field_name: str,
    value: object,
) -> None:
    """Reject corrupted status/error/result values instead of projecting them publicly."""
    product_id, _active_id, _candidate_id, mapping_id = _seed_preview_graph(preview_session_factory)
    with preview_session_factory() as session:
        created = create_or_reuse_preview_job(
            session,
            product_id=product_id,
            mapping_id=mapping_id,
            expected_candidate_version=4,
            commits={"direct": COMMIT_HASH},
            enqueuer=lambda _job_id: None,
        )
    with preview_session_factory() as session:
        row = session.get(PreviewJob, created.id)
        assert row is not None
        session.expunge(row)
    setattr(row, field_name, value)

    with pytest.raises((PreviewJobConflict, ValueError), match="persisted|result rejected"):
        _record(row, is_current=True)


def test_corrupted_started_identity_and_missing_mapping_fail_closed(
    preview_session_factory: sessionmaker[Session],
) -> None:
    """Treat malformed repository sides and absent mapping identity as stale."""
    product_id, _active_id, _candidate_id, mapping_id = _seed_preview_graph(preview_session_factory)
    with preview_session_factory() as session:
        created = create_or_reuse_preview_job(
            session,
            product_id=product_id,
            mapping_id=mapping_id,
            expected_candidate_version=4,
            commits={"direct": COMMIT_HASH},
            enqueuer=lambda _job_id: None,
        )
    identity = _start_preview_job(preview_session_factory, job_id=created.id)
    assert identity is not None

    with preview_session_factory() as session:
        malformed = session.get(PreviewJob, created.id)
        assert malformed is not None
        session.expunge(malformed)
    malformed.repository_sides = []
    assert _matches_started_identity(malformed, identity) is False
    with preview_session_factory() as session:
        assert _current_failure_code(session, malformed, for_update=False) == "stale_identity"

    with preview_session_factory() as session:
        missing_mapping = session.get(PreviewJob, created.id)
        assert missing_mapping is not None
        session.expunge(missing_mapping)
    missing_mapping.mapping_id = uuid4()
    with preview_session_factory() as session:
        assert _current_failure_code(session, missing_mapping, for_update=False) == "stale_identity"


def test_mapping_branch_drift_makes_historical_attempt_noncurrent(
    preview_session_factory: sessionmaker[Session],
) -> None:
    """Bind currentness to the exact repository side even if revision version was not advanced."""
    product_id, _active_id, _candidate_id, mapping_id = _seed_preview_graph(preview_session_factory)
    with preview_session_factory() as session:
        created = create_or_reuse_preview_job(
            session,
            product_id=product_id,
            mapping_id=mapping_id,
            expected_candidate_version=4,
            commits={"direct": COMMIT_HASH},
            enqueuer=lambda _job_id: None,
        )
    with preview_session_factory.begin() as session:
        side = session.execute(
            select(ProductMappingRepositorySide).where(
                ProductMappingRepositorySide.mapping_id == mapping_id
            )
        ).scalar_one()
        side.source_branch = "release/drift"

    with preview_session_factory() as session:
        historical = get_preview_job(session, job_id=created.id)
    assert historical.is_current is False
    assert historical.repository_sides[0].source_branch == "main"


def test_preview_projection_covers_missing_and_mismatched_durable_authority(
    preview_session_factory: sessionmaker[Session],
) -> None:
    """Exercise each closed currentness outcome through durable authority changes."""
    product_id, _active_id, _candidate_id, mapping_id = _seed_preview_graph(preview_session_factory)
    with preview_session_factory() as session:
        mapping = session.get(ProductRepositoryMapping, mapping_id)
        assert mapping is not None
        with pytest.raises(PreviewJobConflict, match="commit identity rejected"):
            _complete_sides(mapping, {})
    with (
        preview_session_factory() as session,
        pytest.raises(PreviewJobNotFound, match="job unavailable"),
    ):
        get_preview_job(session, job_id=uuid4())

    def unavailable_enqueuer(_job_id: UUID) -> None:
        raise RuntimeError("broker unavailable")

    with preview_session_factory() as session:
        first = create_or_reuse_preview_job(
            session,
            product_id=product_id,
            mapping_id=mapping_id,
            expected_candidate_version=4,
            commits={"direct": COMMIT_HASH},
            enqueuer=unavailable_enqueuer,
        )
    with preview_session_factory() as session:
        second = create_or_reuse_preview_job(
            session,
            product_id=product_id,
            mapping_id=mapping_id,
            expected_candidate_version=4,
            commits={"direct": COMMIT_HASH},
            enqueuer=lambda _job_id: None,
        )
        assert get_preview_job(session, job_id=first.id).is_current is False

    with preview_session_factory.begin() as session:
        connection = session.get(BitbucketConnection, 1)
        assert connection is not None
        connection.generation += 1
    with preview_session_factory() as session:
        assert get_preview_job(session, job_id=second.id).is_current is False
        detached = session.get(PreviewJob, second.id)
        assert detached is not None
        session.expunge(detached)
    detached.product_id = uuid4()
    with preview_session_factory() as session:
        assert _current_failure_code(session, detached, for_update=False) == "stale_candidate"


def test_worker_closes_attempt_when_candidate_changes_before_start(
    preview_session_factory: sessionmaker[Session],
) -> None:
    """Persist the stale-candidate terminal timestamps before processor invocation."""
    product_id, _active_id, candidate_id, mapping_id = _seed_preview_graph(preview_session_factory)
    with preview_session_factory() as session:
        created = create_or_reuse_preview_job(
            session,
            product_id=product_id,
            mapping_id=mapping_id,
            expected_candidate_version=4,
            commits={"direct": COMMIT_HASH},
            enqueuer=lambda _job_id: None,
        )
    with preview_session_factory.begin() as session:
        revision = session.get(ProductRevision, candidate_id)
        assert revision is not None
        revision.version += 1

    processor_called = False

    def processor(_identity: object) -> dict[str, object]:
        nonlocal processor_called
        processor_called = True
        return {}

    execute_preview_job(preview_session_factory, job_id=created.id, processor=processor)

    assert processor_called is False
    with preview_session_factory() as session:
        row = session.get(PreviewJob, created.id)
        assert row is not None
        assert row.state == "failed"
        assert row.error_code == "stale_candidate"
        assert row.finished_at is not None
        assert row.updated_at == row.finished_at
