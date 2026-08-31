"""Durable administrator preview-job integration contracts."""

from __future__ import annotations

import asyncio
import importlib
import inspect
import os
import time
from collections.abc import Generator, Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from dataclasses import replace as dataclass_replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier
from typing import Any, Literal, cast
from uuid import UUID, uuid4

import httpx
import pytest
from alembic.config import Config
from celery import Celery
from psycopg import connect, sql
from pydantic import SecretStr, ValidationError
from sqlalchemy import create_engine, func, select, text
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
from verboflex.localization.preview.core import build_layout_candidate
from verboflex.main import app
from verboflex.models.auth_session import AuthSession
from verboflex.models.bitbucket_connection import BitbucketConnection
from verboflex.models.preview_job import (
    ActiveRevisionRevalidationConfirmation,
    PreviewJob,
)
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
    PreviewJobIdentity,
    PreviewJobNotFound,
    PreviewJobRecord,
    _closed_result,
    _complete_sides,
    _current_failure_code,
    _finish_preview_job,
    _identity,
    _matches_started_identity,
    _record,
    _start_preview_job,
    confirm_preview_job,
    create_or_reuse_preview_job,
    execute_preview_job,
    get_preview_job,
    skeleton_preview_processor,
)
from verboflex.services.publication import (
    PublicationBlocked,
    deactivate_product,
    publish_product_candidate,
    reactivate_product,
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
        connection.refresh_token_ciphertext = None
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
    access_token: str | None,
    json: dict[str, Any] | None = None,
) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        headers = {"Authorization": f"Bearer {access_token}"} if access_token is not None else None
        return await client.request(
            method,
            path,
            headers=headers,
            json=json,
        )


def _candidate(
    *,
    format_name: Literal["android_xml", "json"] = "android_xml",
    layout_identity: str = "mobile/src/main/res",
) -> dict[str, object]:
    return build_layout_candidate(
        repository_side="direct",
        format=format_name,
        layout_identity=layout_identity,
        files=(f"{layout_identity}/values/strings.xml",),
        values={"default": {"hello": "Hello"}},
    ).to_mapping()


def _confirmable_processor(identity: object) -> dict[str, object]:
    assert hasattr(identity, "detector_version")
    assert hasattr(identity, "input_digest")
    return {
        "detector_version": identity.detector_version,
        "digest": identity.input_digest,
        "layout_candidates": [
            _candidate(),
            _candidate(format_name="json", layout_identity="web/{locale}.json"),
        ],
    }


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
    assert result["digest"] != created_body["input_digest"]
    assert len(result["digest"]) == 64
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
    adapter = ReadOnlyAndroidSourceAdapter(
        files={
            "mobile/src/main/res/values/strings.xml": (
                b'<resources><string name="hello">Hello</string></resources>'
            ),
            "desktop/app_en.ts": (
                b'<TS version="2.1" language="en"><context><name>Main</name>'
                b"<message><source>hello</source><translation>Hello</translation>"
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


def test_production_preview_processor_closes_its_registry_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The production wrapper delegates once and always closes provider resources."""
    preview_tasks = importlib.import_module("verboflex.worker.preview_tasks")
    closed: list[bool] = []
    sentinel_identity = object()

    class ClosableAdapter:
        async def aclose(self) -> None:
            closed.append(True)

    adapter = ClosableAdapter()

    async def fake_process(
        identity: object, *, factory: object, adapter: object
    ) -> dict[str, object]:
        assert identity is sentinel_identity
        assert factory is preview_tasks.SessionFactory
        assert adapter is not None
        return {"layout_candidates": []}

    monkeypatch.setattr(preview_tasks, "get_settings", lambda: object())
    monkeypatch.setattr(preview_tasks, "BitbucketOAuthTokenExchange", lambda: object())
    monkeypatch.setattr(
        preview_tasks,
        "BitbucketOAuthService",
        lambda **_kwargs: object(),
    )
    monkeypatch.setattr(preview_tasks, "BitbucketHttpAdapter", lambda **_kwargs: adapter)
    monkeypatch.setattr(preview_tasks, "_process_preview", fake_process)

    result = preview_tasks.production_preview_processor(sentinel_identity)

    assert result == {"layout_candidates": []}
    assert closed == [True]


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
    complete_digest = status_body["result"]["digest"]
    assert complete_digest != created_body["input_digest"]
    assert len(complete_digest) == 64
    assert status_body["result"] == {
        "detector_version": "preview-skeleton-v1",
        "digest": complete_digest,
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
    assert current.result is not None
    complete_digest = current.result["digest"]
    assert complete_digest != created.input_digest
    assert current.result == {
        "detector_version": "preview-skeleton-v1",
        "digest": complete_digest,
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


def _create_running_attempt(
    factory: sessionmaker[Session],
    *,
    product_id: UUID,
    mapping_id: UUID,
    commit_hash: str,
    started_at: datetime,
) -> tuple[PreviewJobRecord, PreviewJobIdentity]:
    """Commit one durable running attempt at an exact watchdog age."""
    with factory() as session:
        created = create_or_reuse_preview_job(
            session,
            product_id=product_id,
            mapping_id=mapping_id,
            expected_candidate_version=4,
            commits={"direct": commit_hash},
            enqueuer=lambda _job_id: None,
        )
    identity = _start_preview_job(factory, job_id=created.id)
    assert identity is not None
    with factory.begin() as session:
        row = session.get_one(PreviewJob, created.id)
        row.started_at = started_at
    return created, identity


def test_reconciler_source_keeps_skip_locked_and_complete_cas_identity() -> None:
    """Mutation armor preserves the lock policy and exact attempt ownership CAS."""
    service = importlib.import_module("verboflex.services.preview_jobs")
    reconcile_source = inspect.getsource(service.reconcile_stale_preview_jobs)
    claim_source = inspect.getsource(service._claim_current_running_attempt)

    assert ".with_for_update(skip_locked=True)" in reconcile_source
    assert 'PreviewJob.state == "running"' in reconcile_source
    assert "PreviewJob.started_at <= cutoff" in reconcile_source
    assert "PreviewJob.id == job_id" in claim_source
    assert "PreviewJob.attempt == attempt" in claim_source
    assert "PreviewJob.connection_generation == connection_generation" in claim_source
    assert 'PreviewJob.state == "running"' in claim_source
    assert "finished_at=finished_at" in claim_source


def test_watchdog_rejects_invalid_bounds_and_naive_clock_before_database_access() -> None:
    """Finite positive limits and timezone-aware time are mandatory inputs."""
    service = importlib.import_module("verboflex.services.preview_jobs")

    def forbidden_factory() -> Session:
        raise AssertionError("invalid watchdog inputs must fail before database access")

    factory = cast(sessionmaker[Session], forbidden_factory)
    for hard_limit_seconds, grace_seconds in ((0, 1), (1, 0), (-1, 1), (1, -1)):
        with pytest.raises(ValueError, match="watchdog limits must be positive"):
            service.reconcile_stale_preview_jobs(
                factory,
                hard_time_limit_seconds=hard_limit_seconds,
                watchdog_grace_seconds=grace_seconds,
            )
    with pytest.raises(ValueError, match="watchdog clock must be timezone-aware"):
        service.reconcile_stale_preview_jobs(
            factory,
            hard_time_limit_seconds=75,
            watchdog_grace_seconds=15,
            clock=lambda: datetime(2030, 1, 2, 3, 4, 5),
        )


def test_watchdog_lost_claim_leaves_the_current_running_attempt_unchanged(
    preview_session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A CAS loser does not count or terminalize authority owned by another actor."""
    service = importlib.import_module("verboflex.services.preview_jobs")
    now = datetime(2030, 1, 2, 3, 4, 5, tzinfo=UTC)
    product_id, _active_id, _candidate_id, mapping_id = _seed_preview_graph(preview_session_factory)
    created, _identity_record = _create_running_attempt(
        preview_session_factory,
        product_id=product_id,
        mapping_id=mapping_id,
        commit_hash="0" * 40,
        started_at=now - timedelta(seconds=90),
    )
    monkeypatch.setattr(service, "_claim_current_running_attempt", lambda *_args, **_kwargs: False)

    assert (
        service.reconcile_stale_preview_jobs(
            preview_session_factory,
            hard_time_limit_seconds=75,
            watchdog_grace_seconds=15,
            clock=lambda: now,
        )
        == 0
    )
    with preview_session_factory() as session:
        running = session.get_one(PreviewJob, created.id)
        assert running.state == "running"
        assert running.finished_at is None


def test_watchdog_terminalizes_at_exact_hard_limit_plus_grace_threshold(
    preview_session_factory: sessionmaker[Session],
) -> None:
    """Threshold-minus-one remains running while the exact threshold times out."""
    service = importlib.import_module("verboflex.services.preview_jobs")
    now = datetime(2030, 1, 2, 3, 4, 5, tzinfo=UTC)
    hard_limit_seconds = 75
    grace_seconds = 15
    cutoff = now - timedelta(seconds=hard_limit_seconds + grace_seconds)
    product_id, _active_id, _candidate_id, mapping_id = _seed_preview_graph(preview_session_factory)
    created, _identity_record = _create_running_attempt(
        preview_session_factory,
        product_id=product_id,
        mapping_id=mapping_id,
        commit_hash="1" * 40,
        started_at=cutoff + timedelta(seconds=1),
    )

    early_count = service.reconcile_stale_preview_jobs(
        preview_session_factory,
        hard_time_limit_seconds=hard_limit_seconds,
        watchdog_grace_seconds=grace_seconds,
        clock=lambda: now,
    )
    with preview_session_factory() as session:
        early = session.get_one(PreviewJob, created.id)
        assert early.state == "running"
        assert early.finished_at is None
    assert early_count == 0

    with preview_session_factory.begin() as session:
        row = session.get_one(PreviewJob, created.id)
        row.started_at = cutoff
    threshold_count = service.reconcile_stale_preview_jobs(
        preview_session_factory,
        hard_time_limit_seconds=hard_limit_seconds,
        watchdog_grace_seconds=grace_seconds,
        clock=lambda: now,
    )

    assert threshold_count == 1
    with preview_session_factory() as session:
        terminal = session.get_one(PreviewJob, created.id)
        assert terminal.state == "timed_out"
        assert terminal.error_code == "time_limit_exceeded"
        assert terminal.finished_at == now
        assert terminal.updated_at == now
        assert terminal.result is None


def test_watchdog_claims_exactly_one_hundred_stale_rows_and_uses_partial_index(
    preview_session_factory: sessionmaker[Session],
) -> None:
    """The Plan 36 access path feeds deterministic 100-row recovery batches."""
    service = importlib.import_module("verboflex.services.preview_jobs")
    now = datetime(2030, 2, 3, 4, 5, 6, tzinfo=UTC)
    cutoff = now - timedelta(seconds=90)
    product_id, _active_id, _candidate_id, mapping_id = _seed_preview_graph(preview_session_factory)
    for ordinal in range(101):
        _create_running_attempt(
            preview_session_factory,
            product_id=product_id,
            mapping_id=mapping_id,
            commit_hash=f"{ordinal + 1:040x}",
            started_at=cutoff - timedelta(seconds=ordinal),
        )

    with preview_session_factory.begin() as session:
        session.execute(text("SET LOCAL enable_seqscan = off"))
        plan = session.scalar(
            text(
                "EXPLAIN (FORMAT JSON) "
                "SELECT id, state, started_at FROM preview_jobs "
                "WHERE state = 'running' AND started_at <= :cutoff "
                "ORDER BY started_at, id LIMIT 100 FOR UPDATE SKIP LOCKED"
            ),
            {"cutoff": cutoff},
        )
    assert "ix_preview_jobs_watchdog_state_started_at" in str(plan)

    first = service.reconcile_stale_preview_jobs(
        preview_session_factory,
        hard_time_limit_seconds=75,
        watchdog_grace_seconds=15,
        clock=lambda: now,
    )
    with preview_session_factory() as session:
        assert (
            session.scalar(
                select(func.count()).select_from(PreviewJob).where(PreviewJob.state == "timed_out")
            )
            == 100
        )
        assert (
            session.scalar(
                select(func.count()).select_from(PreviewJob).where(PreviewJob.state == "running")
            )
            == 1
        )

    second = service.reconcile_stale_preview_jobs(
        preview_session_factory,
        hard_time_limit_seconds=75,
        watchdog_grace_seconds=15,
        clock=lambda: now,
    )
    assert (first, second) == (100, 1)


def test_watchdog_watchdog_and_late_success_race_has_one_legal_terminal_winner(
    preview_session_factory: sessionmaker[Session],
) -> None:
    """Duplicate watchdog delivery and a late worker cannot overwrite each other."""
    service = importlib.import_module("verboflex.services.preview_jobs")
    now = datetime(2030, 3, 4, 5, 6, 7, tzinfo=UTC)
    product_id, _active_id, _candidate_id, mapping_id = _seed_preview_graph(preview_session_factory)
    created, identity = _create_running_attempt(
        preview_session_factory,
        product_id=product_id,
        mapping_id=mapping_id,
        commit_hash="2" * 40,
        started_at=now - timedelta(seconds=90),
    )
    barrier = Barrier(3)

    def reconcile() -> int:
        barrier.wait()
        return service.reconcile_stale_preview_jobs(
            preview_session_factory,
            hard_time_limit_seconds=75,
            watchdog_grace_seconds=15,
            clock=lambda: now,
        )

    def finish() -> None:
        barrier.wait()
        _finish_preview_job(
            preview_session_factory,
            identity=identity,
            state="succeeded",
            result=_confirmable_processor(identity),
        )

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(reconcile), executor.submit(reconcile), executor.submit(finish)]
        counts = [futures[0].result(), futures[1].result()]
        futures[2].result()

    assert sum(counts) in {0, 1}
    with preview_session_factory() as session:
        terminal = session.get_one(PreviewJob, created.id)
        assert terminal.state in {"succeeded", "timed_out"}
        assert terminal.finished_at is not None
        if terminal.state == "timed_out":
            assert terminal.error_code == "time_limit_exceeded"
            assert terminal.result is None
        else:
            assert terminal.error_code is None
            assert terminal.result is not None


def test_hard_timeout_and_watchdog_race_share_one_idempotent_terminal_outcome(
    preview_session_factory: sessionmaker[Session],
) -> None:
    """Callback timeout and watchdog recovery converge on one closed response."""
    service = importlib.import_module("verboflex.services.preview_jobs")
    now = datetime(2030, 4, 5, 6, 7, 8, tzinfo=UTC)
    product_id, _active_id, _candidate_id, mapping_id = _seed_preview_graph(preview_session_factory)
    created, identity = _create_running_attempt(
        preview_session_factory,
        product_id=product_id,
        mapping_id=mapping_id,
        commit_hash="3" * 40,
        started_at=now - timedelta(seconds=90),
    )
    barrier = Barrier(2)

    def reconcile() -> int:
        barrier.wait()
        return service.reconcile_stale_preview_jobs(
            preview_session_factory,
            hard_time_limit_seconds=75,
            watchdog_grace_seconds=15,
            clock=lambda: now,
        )

    def finish_timeout() -> None:
        barrier.wait()
        _finish_preview_job(
            preview_session_factory,
            identity=identity,
            state="timed_out",
            error_code="time_limit_exceeded",
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        watchdog_future = executor.submit(reconcile)
        timeout_future = executor.submit(finish_timeout)
        watchdog_count = watchdog_future.result()
        timeout_future.result()

    assert watchdog_count in {0, 1}
    with preview_session_factory() as session:
        terminal = session.get_one(PreviewJob, created.id)
        assert terminal.state == "timed_out"
        assert terminal.error_code == "time_limit_exceeded"
        assert terminal.finished_at is not None
        assert terminal.result is None


def test_retry_after_watchdog_timeout_isolated_from_old_worker_completion(
    preview_session_factory: sessionmaker[Session],
) -> None:
    """Retry keeps the timed-out original immutable and succeeds as a new UUID attempt."""
    service = importlib.import_module("verboflex.services.preview_jobs")
    now = datetime(2030, 5, 6, 7, 8, 9, tzinfo=UTC)
    product_id, _active_id, _candidate_id, mapping_id = _seed_preview_graph(preview_session_factory)
    original, original_identity = _create_running_attempt(
        preview_session_factory,
        product_id=product_id,
        mapping_id=mapping_id,
        commit_hash="4" * 40,
        started_at=now - timedelta(seconds=90),
    )
    assert (
        service.reconcile_stale_preview_jobs(
            preview_session_factory,
            hard_time_limit_seconds=75,
            watchdog_grace_seconds=15,
            clock=lambda: now,
        )
        == 1
    )

    with preview_session_factory() as session:
        retry = create_or_reuse_preview_job(
            session,
            product_id=product_id,
            mapping_id=mapping_id,
            expected_candidate_version=4,
            commits={"direct": "4" * 40},
            enqueuer=lambda _job_id: None,
        )
    assert retry.id != original.id
    assert retry.attempt == original.attempt + 1
    retry_identity = _start_preview_job(preview_session_factory, job_id=retry.id)
    assert retry_identity is not None

    _finish_preview_job(
        preview_session_factory,
        identity=original_identity,
        state="succeeded",
        result=_confirmable_processor(original_identity),
    )
    _finish_preview_job(
        preview_session_factory,
        identity=retry_identity,
        state="succeeded",
        result=_confirmable_processor(retry_identity),
    )

    with preview_session_factory() as session:
        original_row = session.get_one(PreviewJob, original.id)
        retry_row = session.get_one(PreviewJob, retry.id)
        assert original_row.state == "timed_out"
        assert original_row.error_code == "time_limit_exceeded"
        assert original_row.result is None
        assert retry_row.state == "succeeded"
        assert retry_row.error_code is None
        assert retry_row.result is not None


def test_preview_watchdog_settings_define_one_finite_terminalization_bound() -> None:
    """Central defaults retain the exact 60/75/15/5 second recovery contract."""
    settings = Settings()

    assert settings.preview_soft_time_limit_seconds == 60
    assert settings.preview_hard_time_limit_seconds == 75
    assert settings.preview_watchdog_grace_seconds == 15
    assert settings.preview_watchdog_interval_seconds == 5
    assert settings.preview_max_terminalization_seconds == 95


@pytest.mark.parametrize(
    "overrides",
    [
        {"preview_soft_time_limit_seconds": 0},
        {"preview_hard_time_limit_seconds": 0},
        {"preview_watchdog_grace_seconds": 0},
        {"preview_watchdog_interval_seconds": 0},
        {
            "preview_soft_time_limit_seconds": 75,
            "preview_hard_time_limit_seconds": 75,
        },
        {
            "preview_soft_time_limit_seconds": 76,
            "preview_hard_time_limit_seconds": 75,
        },
        {
            "preview_watchdog_grace_seconds": 5,
            "preview_watchdog_interval_seconds": 5,
        },
        {
            "preview_hard_time_limit_seconds": 280,
            "preview_watchdog_grace_seconds": 15,
            "preview_watchdog_interval_seconds": 10,
        },
    ],
)
def test_preview_watchdog_settings_reject_unbounded_or_inverted_limits(
    overrides: dict[str, int],
) -> None:
    """Every configured limit is positive, ordered, and below the documented cap."""
    with pytest.raises(ValidationError):
        Settings(**overrides)


def test_preview_watchdog_schedule_uses_validated_interval_and_named_task() -> None:
    """Celery beat delivers the named idempotent command within the grace window."""
    celery_app = importlib.import_module("verboflex.worker.celery_app")
    settings = Settings(
        preview_soft_time_limit_seconds=10,
        preview_hard_time_limit_seconds=20,
        preview_watchdog_grace_seconds=8,
        preview_watchdog_interval_seconds=2,
    )

    application = celery_app.create_celery_app(settings)
    entry = application.conf.beat_schedule["preview-stale-job-watchdog"]

    assert entry == {
        "task": "verboflex.preview.reconcile_stale_jobs",
        "schedule": 2.0,
    }
    assert application.conf.beat_max_loop_interval == 2
    annotations = application.conf.task_annotations
    assert annotations["verboflex.preview.run"] == {
        "acks_late": True,
        "reject_on_worker_lost": True,
        "soft_time_limit": 10,
        "time_limit": 20,
    }
    application.close()


def test_preview_task_delivery_uses_central_limits_and_worker_loss_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """UUID delivery and execution share Settings-owned limits and late acknowledgement."""
    service = importlib.import_module("verboflex.services.preview_jobs")
    celery_app = importlib.import_module("verboflex.worker.celery_app")
    preview_tasks = importlib.import_module("verboflex.worker.preview_tasks")
    settings = Settings(
        preview_soft_time_limit_seconds=11,
        preview_hard_time_limit_seconds=21,
        preview_watchdog_grace_seconds=8,
        preview_watchdog_interval_seconds=2,
    )
    sent: list[tuple[str, tuple[str], dict[str, object]]] = []

    class RecordingApp:
        def send_task(self, name: str, args: list[str], **kwargs: object) -> None:
            sent.append((name, tuple(args), kwargs))

    monkeypatch.setattr(service, "get_settings", lambda: settings)
    monkeypatch.setattr(celery_app, "app", RecordingApp())
    job_id = uuid4()

    service.enqueue_preview_job(job_id)

    assert sent == [
        (
            "verboflex.preview.run",
            (str(job_id),),
            {
                "task_id": str(job_id),
                "serializer": "json",
                "soft_time_limit": 11,
                "time_limit": 21,
            },
        )
    ]
    assert preview_tasks.run_preview_job.acks_late is True
    assert preview_tasks.run_preview_job.reject_on_worker_lost is True
    assert preview_tasks.run_preview_job.soft_time_limit == 60
    assert preview_tasks.run_preview_job.time_limit == 75


def test_named_watchdog_task_passes_validated_threshold_to_reconciler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The scheduler task delegates once to the fixed-batch database authority."""
    preview_tasks = importlib.import_module("verboflex.worker.preview_tasks")
    settings = Settings(
        preview_soft_time_limit_seconds=12,
        preview_hard_time_limit_seconds=22,
        preview_watchdog_grace_seconds=9,
        preview_watchdog_interval_seconds=3,
    )
    calls: list[tuple[object, int, int]] = []

    def reconcile(
        factory: object,
        *,
        hard_time_limit_seconds: int,
        watchdog_grace_seconds: int,
    ) -> int:
        calls.append((factory, hard_time_limit_seconds, watchdog_grace_seconds))
        return 100

    factory = object()
    monkeypatch.setattr(preview_tasks, "get_settings", lambda: settings)
    monkeypatch.setattr(preview_tasks, "SessionFactory", factory)
    monkeypatch.setattr(preview_tasks, "reconcile_stale_preview_jobs", reconcile)

    assert preview_tasks.reconcile_stale_jobs.run() == 100
    assert calls == [(factory, 22, 9)]
    assert preview_tasks.reconcile_stale_jobs.name == "verboflex.preview.reconcile_stale_jobs"


def _complete_confirmable_preview(
    factory: sessionmaker[Session],
) -> tuple[UUID, UUID, UUID, object, dict[str, object]]:
    product_id, _active_id, candidate_id, mapping_id = _seed_preview_graph(factory)
    with factory() as session:
        created = create_or_reuse_preview_job(
            session,
            product_id=product_id,
            mapping_id=mapping_id,
            expected_candidate_version=4,
            commits={"direct": COMMIT_HASH},
            enqueuer=lambda _job_id: None,
        )
    execute_preview_job(
        factory,
        job_id=created.id,
        processor=_confirmable_processor,
    )
    with factory() as session:
        completed = get_preview_job(session, job_id=created.id)
    assert completed.result is not None
    return product_id, candidate_id, mapping_id, completed, completed.result


def test_admin_explicitly_confirms_one_exact_current_layout(
    preview_session_factory: sessionmaker[Session],
) -> None:
    """Bind actor, complete digest, job identity, and exactly one layout selection."""
    _configure_dependencies(preview_session_factory)
    admin_token = _create_authority(preview_session_factory, role_name="admin")
    viewer_token = _create_authority(preview_session_factory, role_name="viewer")
    _product_id, _candidate_id, mapping_id, completed, result = _complete_confirmable_preview(
        preview_session_factory
    )
    candidates = result["layout_candidates"]
    assert isinstance(candidates, list)
    selected = candidates[1]
    assert isinstance(selected, dict)
    assert completed.state == "succeeded"
    assert completed.is_current is True
    assert result["digest"] != completed.input_digest
    assert len(str(result["digest"])) == 64
    path = f"/api/v1/admin/preview-jobs/{completed.id}/confirmation"
    payload = {
        "preview_digest": result["digest"],
        "layout_candidate_id": selected["id"],
        "layout_candidate_version": selected["version"],
    }

    anonymous = asyncio.run(_request("POST", path, access_token=None, json=payload))
    viewer = asyncio.run(_request("POST", path, access_token=viewer_token, json=payload))
    wrong_digest = asyncio.run(
        _request(
            "POST",
            path,
            access_token=admin_token,
            json={**payload, "preview_digest": "f" * 64},
        )
    )
    confirmed = asyncio.run(_request("POST", path, access_token=admin_token, json=payload))

    assert anonymous.status_code == 401
    assert viewer.status_code == 403
    assert wrong_digest.status_code == 409
    assert confirmed.status_code == 200
    body = confirmed.json()
    assert body == {
        "job_id": str(completed.id),
        "mapping_id": str(mapping_id),
        "preview_digest": result["digest"],
        "layout_candidate_id": selected["id"],
        "layout_candidate_version": 1,
        "confirmed_by": body["confirmed_by"],
        "confirmed_at": body["confirmed_at"],
    }
    with preview_session_factory() as session:
        mapping = session.get(ProductRepositoryMapping, mapping_id)
        assert mapping is not None
        assert mapping.selected_layout_candidate_id == UUID(str(selected["id"]))
        assert mapping.selected_layout_version == 1
        assert mapping.confirmed_preview_job_id == completed.id
        assert mapping.confirmed_preview_digest == result["digest"]
        assert str(mapping.preview_confirmed_by) == body["confirmed_by"]
        assert mapping.preview_confirmed_at is not None
        assert session.scalar(text("SELECT to_regclass('public.translations')")) is None

    repeated = asyncio.run(_request("POST", path, access_token=admin_token, json=payload))
    assert repeated.status_code == 200
    assert repeated.json() == body


@pytest.mark.parametrize(
    "mutation",
    [
        "candidate_version",
        "topology",
        "branch",
        "connection_generation",
        "detector_version",
        "layout_identity",
        "new_commit",
    ],
)
def test_confirmation_is_invalid_after_every_live_identity_change(
    preview_session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    """Preserve historical output but reject confirmation after any authority drift."""
    _configure_dependencies(preview_session_factory)
    admin_token = _create_authority(preview_session_factory, role_name="admin")
    product_id, candidate_id, mapping_id, completed, result = _complete_confirmable_preview(
        preview_session_factory
    )
    selected = result["layout_candidates"][0]
    path = f"/api/v1/admin/preview-jobs/{completed.id}/confirmation"
    payload = {
        "preview_digest": result["digest"],
        "layout_candidate_id": selected["id"],
        "layout_candidate_version": selected["version"],
    }
    assert (
        asyncio.run(_request("POST", path, access_token=admin_token, json=payload)).status_code
        == 200
    )

    if mutation == "new_commit":
        with preview_session_factory() as session:
            replacement = create_or_reuse_preview_job(
                session,
                product_id=product_id,
                mapping_id=mapping_id,
                expected_candidate_version=4,
                commits={"direct": "b" * 40},
                enqueuer=lambda _job_id: None,
            )
        assert replacement.id != completed.id
    elif mutation in {"detector_version", "layout_identity"}:
        module = importlib.import_module("verboflex.services.preview_jobs")
        constant = (
            "PREVIEW_DETECTOR_VERSION"
            if mutation == "detector_version"
            else "PREVIEW_LAYOUT_IDENTITY"
        )
        monkeypatch.setattr(module, constant, f"changed-{mutation}-v2")
    else:
        with preview_session_factory.begin() as session:
            if mutation == "candidate_version":
                revision = session.get(ProductRevision, candidate_id)
                assert revision is not None
                revision.version += 1
            elif mutation == "connection_generation":
                connection = session.get(BitbucketConnection, 1)
                assert connection is not None
                connection.generation += 1
            elif mutation == "topology":
                mapping = session.get(ProductRepositoryMapping, mapping_id)
                assert mapping is not None
                mapping.topology = "separate"
            else:
                side = session.execute(
                    select(ProductMappingRepositorySide).where(
                        ProductMappingRepositorySide.mapping_id == mapping_id
                    )
                ).scalar_one()
                side.source_branch = "release/drift"

    rejected = asyncio.run(_request("POST", path, access_token=admin_token, json=payload))
    historical = asyncio.run(
        _request(
            "GET",
            f"/api/v1/admin/preview-jobs/{completed.id}",
            access_token=admin_token,
        )
    )
    assert rejected.status_code == 409
    assert historical.status_code == 200
    assert historical.json()["is_current"] is False
    assert historical.json()["state"] == "succeeded"
    assert historical.json()["result"] == result


def test_new_commit_makes_an_inflight_completion_stale_and_nonconfirmable(
    preview_session_factory: sessionmaker[Session],
) -> None:
    """A worker started for an older commit cannot restore current confirmation authority."""
    _configure_dependencies(preview_session_factory)
    admin_token = _create_authority(preview_session_factory, role_name="admin")
    product_id, _active_id, _candidate_id, mapping_id = _seed_preview_graph(preview_session_factory)
    with preview_session_factory() as session:
        stale = create_or_reuse_preview_job(
            session,
            product_id=product_id,
            mapping_id=mapping_id,
            expected_candidate_version=4,
            commits={"direct": COMMIT_HASH},
            enqueuer=lambda _job_id: None,
        )
    stale_identity = _start_preview_job(preview_session_factory, job_id=stale.id)
    assert stale_identity is not None
    with preview_session_factory() as session:
        current = create_or_reuse_preview_job(
            session,
            product_id=product_id,
            mapping_id=mapping_id,
            expected_candidate_version=4,
            commits={"direct": "b" * 40},
            enqueuer=lambda _job_id: None,
        )
    with preview_session_factory() as session:
        historical_reuse = create_or_reuse_preview_job(
            session,
            product_id=product_id,
            mapping_id=mapping_id,
            expected_candidate_version=4,
            commits={"direct": COMMIT_HASH},
            enqueuer=lambda _job_id: None,
        )
    assert historical_reuse.id == stale.id
    assert historical_reuse.is_current is False

    stale_result = _confirmable_processor(stale_identity)
    _finish_preview_job(
        preview_session_factory,
        identity=stale_identity,
        state="succeeded",
        result=stale_result,
    )

    with preview_session_factory() as session:
        stale_row = session.get(PreviewJob, stale.id)
        assert stale_row is not None
        session.expunge(stale_row)
    with preview_session_factory() as session:
        current_record = get_preview_job(session, job_id=current.id)
    assert stale_row is not None
    assert current_record.is_current is True
    assert stale_row.state == "failed"
    assert stale_row.error_code == "stale_identity"
    assert stale_row.result is None
    confirm = asyncio.run(
        _request(
            "POST",
            f"/api/v1/admin/preview-jobs/{stale.id}/confirmation",
            access_token=admin_token,
            json={
                "preview_digest": "f" * 64,
                "layout_candidate_id": _candidate()["id"],
                "layout_candidate_version": 1,
            },
        )
    )
    assert confirm.status_code == 409


@pytest.mark.parametrize("terminal", ["queued", "empty", "failed", "timed_out"])
def test_nonconfirmable_preview_states_expose_no_confirmation_action(
    preview_session_factory: sessionmaker[Session],
    terminal: str,
) -> None:
    """Queued, empty, failed, and timed-out work cannot assign a mapping layout."""
    _configure_dependencies(preview_session_factory)
    admin_token = _create_authority(preview_session_factory, role_name="admin")
    product_id, _active_id, _candidate_id, mapping_id = _seed_preview_graph(preview_session_factory)
    commit_hash = {"queued": "1", "empty": "2", "failed": "3", "timed_out": "4"}[terminal] * 40
    with preview_session_factory() as session:
        job = create_or_reuse_preview_job(
            session,
            product_id=product_id,
            mapping_id=mapping_id,
            expected_candidate_version=4,
            commits={"direct": commit_hash},
            enqueuer=lambda _job_id: None,
        )
    if terminal == "empty":
        execute_preview_job(
            preview_session_factory, job_id=job.id, processor=skeleton_preview_processor
        )
    elif terminal == "failed":
        execute_preview_job(
            preview_session_factory,
            job_id=job.id,
            processor=lambda _identity: {"malformed": True},
        )
    elif terminal == "timed_out":
        from verboflex.services.preview_jobs import PreviewJobTimedOut

        def time_out(_identity: object) -> dict[str, object]:
            raise PreviewJobTimedOut

        execute_preview_job(preview_session_factory, job_id=job.id, processor=time_out)

    response = asyncio.run(
        _request(
            "POST",
            f"/api/v1/admin/preview-jobs/{job.id}/confirmation",
            access_token=admin_token,
            json={
                "preview_digest": "f" * 64,
                "layout_candidate_id": _candidate()["id"],
                "layout_candidate_version": 1,
            },
        )
    )
    assert response.status_code == 409
    with preview_session_factory() as session:
        mapping = session.get(ProductRepositoryMapping, mapping_id)
        assert mapping is not None
        assert mapping.selected_layout_candidate_id is None
        assert mapping.confirmed_preview_job_id is None


def test_confirmation_rejects_missing_candidate_and_wrong_repository_side(
    preview_session_factory: sessionmaker[Session],
) -> None:
    """Closed confirmation authority rejects unavailable and cross-side identities."""
    actor_id = uuid4()
    with (
        preview_session_factory() as session,
        pytest.raises(PreviewJobNotFound, match="preview job unavailable"),
    ):
        confirm_preview_job(
            session,
            job_id=uuid4(),
            preview_digest="f" * 64,
            layout_candidate_id=uuid4(),
            layout_candidate_version=1,
            actor_id=actor_id,
        )

    _product_id, _candidate_id, _mapping_id, completed, result = _complete_confirmable_preview(
        preview_session_factory
    )
    with (
        preview_session_factory() as session,
        pytest.raises(PreviewJobConflict, match="preview confirmation unavailable"),
    ):
        confirm_preview_job(
            session,
            job_id=completed.id,
            preview_digest=str(result["digest"]),
            layout_candidate_id=uuid4(),
            layout_candidate_version=1,
            actor_id=actor_id,
        )

    _product_id, _candidate_id, _mapping_id, completed, _result = _complete_confirmable_preview(
        preview_session_factory
    )
    with preview_session_factory.begin() as session:
        row = session.get_one(PreviewJob, completed.id)
        candidate = build_layout_candidate(
            repository_side="translations",
            format="android_xml",
            layout_identity="mobile/src/main/res",
            files=("mobile/src/main/res/values/strings.xml",),
            values={"default": {"hello": "Hello"}},
        ).to_mapping()
        row.result = _closed_result(
            _identity(row),
            {
                "detector_version": row.detector_version,
                "digest": row.input_digest,
                "layout_candidates": [candidate],
            },
        )
        rejected_digest = str(row.result["digest"])
    with (
        preview_session_factory() as session,
        pytest.raises(PreviewJobConflict, match="preview confirmation unavailable"),
    ):
        confirm_preview_job(
            session,
            job_id=completed.id,
            preview_digest=rejected_digest,
            layout_candidate_id=UUID(str(candidate["id"])),
            layout_candidate_version=1,
            actor_id=actor_id,
        )


def _published_configuration_snapshot(
    factory: sessionmaker[Session],
    *,
    product_id: UUID,
) -> tuple[object, ...]:
    """Capture the complete published graph while excluding operational activation."""
    with factory() as session:
        product = session.execute(
            select(
                Product.id,
                Product.active_revision_id,
                Product.candidate_revision_id,
                Product.display_name,
                Product.name_key,
            ).where(Product.id == product_id)
        ).one()
        revisions = tuple(
            session.execute(
                select(
                    ProductRevision.id,
                    ProductRevision.version,
                    ProductRevision.display_name,
                    ProductRevision.name_key,
                    ProductRevision.description,
                    ProductRevision.is_published,
                    ProductRevision.published_at,
                )
                .where(ProductRevision.product_id == product_id)
                .order_by(ProductRevision.id)
            ).all()
        )
        revision_ids = tuple(revision.id for revision in revisions)
        mappings = tuple(
            session.execute(
                select(
                    ProductRepositoryMapping.id,
                    ProductRepositoryMapping.revision_id,
                    ProductRepositoryMapping.topology,
                    ProductRepositoryMapping.identity_key,
                    ProductRepositoryMapping.selected_layout_candidate_id,
                    ProductRepositoryMapping.selected_layout_version,
                    ProductRepositoryMapping.confirmed_preview_job_id,
                    ProductRepositoryMapping.confirmed_preview_digest,
                    ProductRepositoryMapping.preview_confirmed_by,
                    ProductRepositoryMapping.preview_confirmed_at,
                )
                .where(ProductRepositoryMapping.revision_id.in_(revision_ids))
                .order_by(ProductRepositoryMapping.id)
            ).all()
        )
        mapping_ids = tuple(mapping.id for mapping in mappings)
        sides = tuple(
            session.execute(
                select(
                    ProductMappingRepositorySide.mapping_id,
                    ProductMappingRepositorySide.role,
                    ProductMappingRepositorySide.repository_id,
                    ProductMappingRepositorySide.source_branch,
                )
                .where(ProductMappingRepositorySide.mapping_id.in_(mapping_ids))
                .order_by(
                    ProductMappingRepositorySide.mapping_id,
                    ProductMappingRepositorySide.role,
                )
            ).all()
        )
        targets = tuple(
            session.execute(
                select(
                    ProductMappingAllowedTarget.mapping_id,
                    ProductMappingAllowedTarget.branch,
                    ProductMappingAllowedTarget.is_default,
                )
                .where(ProductMappingAllowedTarget.mapping_id.in_(mapping_ids))
                .order_by(
                    ProductMappingAllowedTarget.mapping_id,
                    ProductMappingAllowedTarget.branch,
                )
            ).all()
        )
    return (tuple(product), revisions, mappings, sides, targets)


def _seed_active_revalidation_authority(
    factory: sessionmaker[Session],
    *,
    invalid_mapping: bool = False,
) -> tuple[UUID, UUID, UUID, UUID, UUID]:
    """Project the standard preview fixture into one inactive published revision."""
    product_id, _old_active_id, revision_id, mapping_id = _seed_preview_graph(factory)
    actor_id = uuid4()
    selected_layout_id = UUID(str(_candidate()["id"]))
    with factory.begin() as session:
        mapping = session.get_one(ProductRepositoryMapping, mapping_id)
        if invalid_mapping:
            mapping.topology = "separate"
            mapping.selected_layout_candidate_id = None
            mapping.selected_layout_version = None
        else:
            mapping.selected_layout_candidate_id = selected_layout_id
            mapping.selected_layout_version = 1
        session.flush()
        revision = session.get_one(ProductRevision, revision_id)
        revision.is_published = True
        revision.published_at = datetime.now(UTC)
        session.flush()
        product = session.get_one(Product, product_id)
        product.is_active = False
        product.active_revision_id = revision_id
        product.candidate_revision_id = None
        session.add(
            User(
                id=actor_id,
                email=f"revalidation-coverage-{actor_id}@example.com",
                display_name="Revalidation Coverage Admin",
                hashed_password=hash_password("revalidation coverage administrator phrase!"),
                is_active=True,
                must_change_password=False,
            )
        )
    return product_id, revision_id, mapping_id, actor_id, selected_layout_id


def _complete_active_revalidation(
    factory: sessionmaker[Session],
    *,
    product_id: UUID,
    revision_id: UUID,
    mapping_id: UUID,
    commit_hash: str = COMMIT_HASH,
) -> tuple[PreviewJobRecord, dict[str, object]]:
    preview_jobs = importlib.import_module("verboflex.services.preview_jobs")
    with factory() as session:
        job = preview_jobs.create_or_reuse_active_revision_revalidation_job(
            session,
            product_id=product_id,
            active_revision_id=revision_id,
            mapping_id=mapping_id,
            expected_active_revision_version=4,
            commits={"direct": commit_hash},
            enqueuer=lambda _job_id: None,
        )
    execute_preview_job(factory, job_id=job.id, processor=_confirmable_processor)
    with factory() as session:
        completed = preview_jobs.get_active_revision_revalidation_job(
            session,
            job_id=job.id,
        )
    assert completed.result is not None
    return completed, completed.result


def test_inactive_active_revision_can_revalidate_confirm_and_reactivate_without_graph_mutation(
    preview_session_factory: sessionmaker[Session],
) -> None:
    """Recover an exact published graph through read-only work and sidecar authority."""
    product_id, _old_active_id, candidate_id, mapping_id = _seed_preview_graph(
        preview_session_factory
    )
    actor_id = uuid4()
    with preview_session_factory.begin() as session:
        session.add(
            User(
                id=actor_id,
                email=f"revalidation-{actor_id}@example.com",
                display_name="Revalidation Admin",
                hashed_password=hash_password("revalidation administrator phrase!"),
                is_active=True,
                must_change_password=False,
            )
        )
    with preview_session_factory() as session:
        candidate_job = create_or_reuse_preview_job(
            session,
            product_id=product_id,
            mapping_id=mapping_id,
            expected_candidate_version=4,
            commits={"direct": COMMIT_HASH},
            enqueuer=lambda _job_id: None,
        )
    execute_preview_job(
        preview_session_factory,
        job_id=candidate_job.id,
        processor=_confirmable_processor,
    )
    with preview_session_factory() as session:
        completed_candidate = get_preview_job(session, job_id=candidate_job.id)
        assert completed_candidate.result is not None
        selected = cast(list[dict[str, object]], completed_candidate.result["layout_candidates"])[0]
        confirm_preview_job(
            session,
            job_id=candidate_job.id,
            preview_digest=str(completed_candidate.result["digest"]),
            layout_candidate_id=UUID(str(selected["id"])),
            layout_candidate_version=1,
            actor_id=actor_id,
        )
    with preview_session_factory() as session:
        published = publish_product_candidate(
            session,
            product_id=product_id,
            candidate_revision_id=candidate_id,
            expected_candidate_version=4,
        )
    assert published.active_revision_id == candidate_id
    assert published.candidate_revision_id is None
    with preview_session_factory() as session:
        deactivate_product(session, product_id=product_id)
    before_revalidation = _published_configuration_snapshot(
        preview_session_factory,
        product_id=product_id,
    )

    with preview_session_factory.begin() as session:
        connection = session.get_one(BitbucketConnection, 1)
        connection.generation += 1
    with (
        preview_session_factory() as session,
        pytest.raises(PublicationBlocked, match="product publication blocked"),
    ):
        reactivate_product(
            session,
            product_id=product_id,
            active_revision_id=candidate_id,
            expected_active_version=4,
        )

    preview_jobs = importlib.import_module("verboflex.services.preview_jobs")
    create_active_job = preview_jobs.create_or_reuse_active_revision_revalidation_job
    with preview_session_factory() as session:
        active_job = create_active_job(
            session,
            product_id=product_id,
            active_revision_id=candidate_id,
            mapping_id=mapping_id,
            expected_active_revision_version=4,
            commits={"direct": COMMIT_HASH},
            enqueuer=lambda _job_id: None,
        )
    assert active_job.revision_scope == "active_revalidation"
    execute_preview_job(
        preview_session_factory,
        job_id=active_job.id,
        processor=_confirmable_processor,
    )
    assert (
        _published_configuration_snapshot(
            preview_session_factory,
            product_id=product_id,
        )
        == before_revalidation
    )

    with preview_session_factory() as session:
        succeeded = preview_jobs.get_active_revision_revalidation_job(
            session,
            job_id=active_job.id,
        )
        assert succeeded.result is not None
        current_layout = cast(list[dict[str, object]], succeeded.result["layout_candidates"])[0]
        assert (
            preview_jobs.get_active_revision_revalidation_eligibility(
                session,
                product_id=product_id,
                active_revision_id=candidate_id,
                expected_active_revision_version=4,
            ).eligible
            is False
        )
    with preview_session_factory() as session:
        confirmation = preview_jobs.confirm_active_revision_revalidation(
            session,
            job_id=active_job.id,
            preview_digest=str(succeeded.result["digest"]),
            layout_candidate_id=UUID(str(current_layout["id"])),
            layout_candidate_version=1,
            actor_id=actor_id,
        )
    assert confirmation.revision_id == candidate_id
    assert confirmation.revision_version == 4
    assert confirmation.mapping_id == mapping_id
    assert confirmation.connection_generation == 8
    assert confirmation.preview_digest == succeeded.result["digest"]
    assert confirmation.layout_candidate_id == UUID(str(current_layout["id"]))
    assert confirmation.confirmed_by == actor_id
    assert (
        _published_configuration_snapshot(
            preview_session_factory,
            product_id=product_id,
        )
        == before_revalidation
    )

    with preview_session_factory() as session:
        eligibility = preview_jobs.get_active_revision_revalidation_eligibility(
            session,
            product_id=product_id,
            active_revision_id=candidate_id,
            expected_active_revision_version=4,
        )
        assert eligibility.eligible is True
        assert len(eligibility.mappings) == 1
        assert eligibility.mappings[0].is_current is True
    with preview_session_factory() as session:
        reactivated = reactivate_product(
            session,
            product_id=product_id,
            active_revision_id=candidate_id,
            expected_active_version=4,
        )
    assert reactivated.changed is True
    assert reactivated.is_active is True
    assert reactivated.candidate_revision_id is None
    assert (
        _published_configuration_snapshot(
            preview_session_factory,
            product_id=product_id,
        )
        == before_revalidation
    )


def test_active_revalidation_namespace_and_creation_guards_fail_closed(
    preview_session_factory: sessionmaker[Session],
) -> None:
    """Reject wrong lifecycle ownership while preserving disjoint job namespaces."""
    preview_jobs = importlib.import_module("verboflex.services.preview_jobs")
    product_id, revision_id, mapping_id, actor_id, selected_layout_id = (
        _seed_active_revalidation_authority(preview_session_factory)
    )
    with preview_session_factory() as session:
        created = preview_jobs.create_or_reuse_active_revision_revalidation_job(
            session,
            product_id=product_id,
            active_revision_id=revision_id,
            mapping_id=mapping_id,
            expected_active_revision_version=4,
            commits={"direct": COMMIT_HASH},
            enqueuer=lambda _job_id: None,
        )
    with preview_session_factory() as session:
        reused = preview_jobs.create_or_reuse_active_revision_revalidation_job(
            session,
            product_id=product_id,
            active_revision_id=revision_id,
            mapping_id=mapping_id,
            expected_active_revision_version=4,
            commits={"direct": COMMIT_HASH},
            enqueuer=lambda _job_id: None,
        )
    assert reused.id == created.id

    with (
        preview_session_factory() as session,
        pytest.raises(PreviewJobConflict, match="preview identity conflict"),
    ):
        get_preview_job(session, job_id=created.id)
    with (
        preview_session_factory() as session,
        pytest.raises(PreviewJobConflict, match="preview identity conflict"),
    ):
        confirm_preview_job(
            session,
            job_id=created.id,
            preview_digest="f" * 64,
            layout_candidate_id=selected_layout_id,
            layout_candidate_version=1,
            actor_id=actor_id,
        )
    with (
        preview_session_factory() as session,
        pytest.raises(PreviewJobNotFound, match="active revalidation job unavailable"),
    ):
        preview_jobs.get_active_revision_revalidation_job(session, job_id=uuid4())

    with preview_session_factory() as session:
        row = session.get_one(PreviewJob, created.id)
        revision = session.get_one(ProductRevision, revision_id)
        mapping = session.get_one(ProductRepositoryMapping, mapping_id)
        connection = session.get_one(BitbucketConnection, 1)
        row.revision_scope = cast(Any, "invalid")
        with pytest.raises(PreviewJobConflict, match="persisted preview scope rejected"):
            _identity(row)
        with session.no_autoflush:
            assert (
                preview_jobs._current_identity_matches(
                    row,
                    revision,
                    mapping,
                    connection,
                )
                is False
            )
        session.rollback()

    with preview_session_factory.begin() as session:
        session.get_one(Product, product_id).is_active = True
    with (
        preview_session_factory() as session,
        pytest.raises(PreviewJobNotFound, match="active revision revalidation unavailable"),
    ):
        preview_jobs.create_or_reuse_active_revision_revalidation_job(
            session,
            product_id=product_id,
            active_revision_id=revision_id,
            mapping_id=mapping_id,
            expected_active_revision_version=4,
            commits={"direct": COMMIT_HASH},
            enqueuer=lambda _job_id: None,
        )
    with preview_session_factory.begin() as session:
        session.get_one(Product, product_id).is_active = False
    with (
        preview_session_factory() as session,
        pytest.raises(PreviewJobConflict, match="active revision revalidation conflict"),
    ):
        preview_jobs.create_or_reuse_active_revision_revalidation_job(
            session,
            product_id=product_id,
            active_revision_id=revision_id,
            mapping_id=mapping_id,
            expected_active_revision_version=5,
            commits={"direct": COMMIT_HASH},
            enqueuer=lambda _job_id: None,
        )
    with (
        preview_session_factory() as session,
        pytest.raises(PreviewJobNotFound, match="active revision mapping unavailable"),
    ):
        preview_jobs.create_or_reuse_active_revision_revalidation_job(
            session,
            product_id=product_id,
            active_revision_id=revision_id,
            mapping_id=uuid4(),
            expected_active_revision_version=4,
            commits={"direct": COMMIT_HASH},
            enqueuer=lambda _job_id: None,
        )


def test_active_revalidation_enqueue_failures_are_bounded_and_retryable(
    preview_session_factory: sessionmaker[Session],
) -> None:
    """Bound broker failures and preserve a racing durable state without overwrite."""
    preview_jobs = importlib.import_module("verboflex.services.preview_jobs")
    product_id, revision_id, mapping_id, _actor_id, _selected_layout_id = (
        _seed_active_revalidation_authority(preview_session_factory)
    )

    def unavailable_enqueuer(_job_id: UUID) -> None:
        raise RuntimeError("broker diagnostics must not escape")

    with preview_session_factory() as session:
        failed = preview_jobs.create_or_reuse_active_revision_revalidation_job(
            session,
            product_id=product_id,
            active_revision_id=revision_id,
            mapping_id=mapping_id,
            expected_active_revision_version=4,
            commits={"direct": COMMIT_HASH},
            enqueuer=unavailable_enqueuer,
        )
    assert failed.state == "failed"
    assert failed.error_code == "enqueue_failed"
    with preview_session_factory() as session:
        retried = preview_jobs.create_or_reuse_active_revision_revalidation_job(
            session,
            product_id=product_id,
            active_revision_id=revision_id,
            mapping_id=mapping_id,
            expected_active_revision_version=4,
            commits={"direct": COMMIT_HASH},
            enqueuer=lambda _job_id: None,
        )
    assert retried.attempt == 2

    product_id, _active_id, _candidate_id, candidate_mapping_id = _seed_preview_graph(
        preview_session_factory
    )

    with preview_session_factory() as session:

        def racing_enqueuer(job_id: UUID) -> None:
            with preview_session_factory.begin() as racing_session:
                row = racing_session.get_one(PreviewJob, job_id)
                row.state = "running"
                row.started_at = datetime.now(UTC)
            session.expire_all()
            raise RuntimeError("late broker acknowledgement")

        racing = create_or_reuse_preview_job(
            session,
            product_id=product_id,
            mapping_id=candidate_mapping_id,
            expected_candidate_version=4,
            commits={"direct": COMMIT_HASH},
            enqueuer=racing_enqueuer,
        )
    assert racing.state == "running"
    assert racing.error_code is None


def test_active_revalidation_confirmation_and_currentness_reject_every_mismatch(
    preview_session_factory: sessionmaker[Session],
) -> None:
    """Exercise exact confirmation identity, idempotency, and corrupted evidence denial."""
    preview_jobs = importlib.import_module("verboflex.services.preview_jobs")
    product_id, revision_id, mapping_id, actor_id, selected_layout_id = (
        _seed_active_revalidation_authority(preview_session_factory)
    )
    with (
        preview_session_factory() as session,
        pytest.raises(PreviewJobNotFound, match="active revalidation job unavailable"),
    ):
        preview_jobs.confirm_active_revision_revalidation(
            session,
            job_id=uuid4(),
            preview_digest="f" * 64,
            layout_candidate_id=selected_layout_id,
            layout_candidate_version=1,
            actor_id=actor_id,
        )

    with preview_session_factory() as session:
        candidate_job = PreviewJob(
            id=uuid4(),
            input_digest="1" * 64,
            attempt=1,
            state="queued",
            revision_scope="candidate",
            product_id=product_id,
            candidate_revision_id=revision_id,
            candidate_revision_version=4,
            mapping_id=mapping_id,
            topology="direct",
            connection_generation=7,
            detector_version="preview-v1",
            layout_identity="automatic",
            repository_sides=[
                {
                    "role": "direct",
                    "repository_id": str(
                        session.get_one(ProductRepositoryMapping, mapping_id).sides[0].repository_id
                    ),
                    "source_branch": "main",
                    "commit_hash": COMMIT_HASH,
                }
            ],
        )
        session.add(candidate_job)
        session.commit()
    with (
        preview_session_factory() as session,
        pytest.raises(PreviewJobConflict, match="active revalidation identity conflict"),
    ):
        preview_jobs.confirm_active_revision_revalidation(
            session,
            job_id=candidate_job.id,
            preview_digest="1" * 64,
            layout_candidate_id=selected_layout_id,
            layout_candidate_version=1,
            actor_id=actor_id,
        )
    with (
        preview_session_factory() as session,
        pytest.raises(PreviewJobNotFound, match="active revalidation job unavailable"),
    ):
        preview_jobs.get_active_revision_revalidation_job(session, job_id=candidate_job.id)
    with preview_session_factory() as session:
        row = session.get_one(PreviewJob, candidate_job.id)
        revision = session.get_one(ProductRevision, revision_id)
        mapping = session.get_one(ProductRepositoryMapping, mapping_id)
        mapping.confirmed_preview_job_id = row.id
        mapping.confirmed_preview_digest = "1" * 64
        mapping.preview_confirmed_by = actor_id
        mapping.preview_confirmed_at = datetime.now(UTC)
        with session.no_autoflush:
            mapping.confirmed_preview_digest = None
            assert (
                preview_jobs.is_current_preview_confirmation(
                    session,
                    revision,
                    mapping,
                )
                is False
            )
            mapping.confirmed_preview_digest = "1" * 64
            mapping.confirmed_preview_job_id = uuid4()
            assert (
                preview_jobs.is_current_preview_confirmation(
                    session,
                    revision,
                    mapping,
                )
                is False
            )
            mapping.confirmed_preview_job_id = row.id
            assert (
                preview_jobs.is_current_preview_confirmation(
                    session,
                    revision,
                    mapping,
                )
                is False
            )
            row.state = "succeeded"
            row.result = {"closed": "candidate fallback branch"}
            assert preview_jobs._mapping_has_complete_confirmation(mapping) is True
            assert preview_jobs._confirmation_job_matches(row, revision, mapping) is True
            assert (
                preview_jobs.is_current_preview_confirmation(
                    session,
                    revision,
                    mapping,
                )
                is False
            )
        session.rollback()

    with preview_session_factory() as session:
        queued = preview_jobs.create_or_reuse_active_revision_revalidation_job(
            session,
            product_id=product_id,
            active_revision_id=revision_id,
            mapping_id=mapping_id,
            expected_active_revision_version=4,
            commits={"direct": COMMIT_HASH},
            enqueuer=lambda _job_id: None,
        )
    with (
        preview_session_factory() as session,
        pytest.raises(PreviewJobConflict, match="confirmation unavailable"),
    ):
        preview_jobs.confirm_active_revision_revalidation(
            session,
            job_id=queued.id,
            preview_digest=queued.input_digest,
            layout_candidate_id=selected_layout_id,
            layout_candidate_version=1,
            actor_id=actor_id,
        )
    execute_preview_job(
        preview_session_factory,
        job_id=queued.id,
        processor=_confirmable_processor,
    )
    with preview_session_factory() as session:
        completed = preview_jobs.get_active_revision_revalidation_job(
            session,
            job_id=queued.id,
        )
    assert completed.result is not None
    result = completed.result
    candidates = cast(list[dict[str, object]], result["layout_candidates"])
    with (
        preview_session_factory() as session,
        pytest.raises(PreviewJobConflict, match="identity conflict"),
    ):
        preview_jobs.confirm_active_revision_revalidation(
            session,
            job_id=queued.id,
            preview_digest="f" * 64,
            layout_candidate_id=selected_layout_id,
            layout_candidate_version=1,
            actor_id=actor_id,
        )
    with (
        preview_session_factory() as session,
        pytest.raises(PreviewJobConflict, match="confirmation unavailable"),
    ):
        preview_jobs.confirm_active_revision_revalidation(
            session,
            job_id=queued.id,
            preview_digest=str(result["digest"]),
            layout_candidate_id=uuid4(),
            layout_candidate_version=1,
            actor_id=actor_id,
        )
    with (
        preview_session_factory() as session,
        pytest.raises(PreviewJobConflict, match="confirmation unavailable"),
    ):
        preview_jobs.confirm_active_revision_revalidation(
            session,
            job_id=queued.id,
            preview_digest=str(result["digest"]),
            layout_candidate_id=UUID(str(candidates[1]["id"])),
            layout_candidate_version=1,
            actor_id=actor_id,
        )
    with preview_session_factory() as session:
        confirmed = preview_jobs.confirm_active_revision_revalidation(
            session,
            job_id=queued.id,
            preview_digest=str(result["digest"]),
            layout_candidate_id=selected_layout_id,
            layout_candidate_version=1,
            actor_id=actor_id,
        )
    with preview_session_factory() as session:
        idempotent = preview_jobs.confirm_active_revision_revalidation(
            session,
            job_id=queued.id,
            preview_digest=str(result["digest"]),
            layout_candidate_id=selected_layout_id,
            layout_candidate_version=1,
            actor_id=actor_id,
        )
    assert idempotent == confirmed

    second, second_result = _complete_active_revalidation(
        preview_session_factory,
        product_id=product_id,
        revision_id=revision_id,
        mapping_id=mapping_id,
        commit_hash="b" * 40,
    )
    with preview_session_factory.begin() as session:
        session.add(
            ActiveRevisionRevalidationConfirmation(
                job_id=second.id,
                revision_scope="active_revalidation",
                product_id=product_id,
                revision_id=revision_id,
                revision_version=4,
                mapping_id=mapping_id,
                connection_generation=second.connection_generation,
                preview_digest="e" * 64,
                layout_candidate_id=selected_layout_id,
                layout_candidate_version=1,
                confirmed_by=actor_id,
                confirmed_at=datetime.now(UTC),
            )
        )
    with (
        preview_session_factory() as session,
        pytest.raises(PreviewJobConflict, match="confirmation conflict"),
    ):
        preview_jobs.confirm_active_revision_revalidation(
            session,
            job_id=second.id,
            preview_digest=str(second_result["digest"]),
            layout_candidate_id=selected_layout_id,
            layout_candidate_version=1,
            actor_id=actor_id,
        )
    with preview_session_factory() as session:
        revision = session.get_one(ProductRevision, revision_id)
        mapping = session.get_one(ProductRepositoryMapping, mapping_id)
        assert (
            preview_jobs.active_revision_revalidation_is_current(
                session,
                revision,
                mapping,
            )
            is False
        )
    with preview_session_factory() as session:
        row = session.get_one(PreviewJob, second.id)
        revision = session.get_one(ProductRevision, revision_id)
        mapping = session.get_one(ProductRepositoryMapping, mapping_id)
        row.state = "failed"
        with session.no_autoflush:
            assert (
                preview_jobs.active_revision_revalidation_is_current(
                    session,
                    revision,
                    mapping,
                )
                is False
            )
        session.rollback()
    with preview_session_factory.begin() as session:
        session.get_one(PreviewJob, second.id).result = {"invalid": "closed result"}
    with preview_session_factory() as session:
        revision = session.get_one(ProductRevision, revision_id)
        mapping = session.get_one(ProductRepositoryMapping, mapping_id)
        assert (
            preview_jobs.active_revision_revalidation_is_current(
                session,
                revision,
                mapping,
            )
            is False
        )
    with preview_session_factory.begin() as session:
        session.get_one(BitbucketConnection, 1).generation += 1
    with (
        preview_session_factory() as session,
        pytest.raises(PreviewJobConflict, match="identity conflict"),
    ):
        preview_jobs.confirm_active_revision_revalidation(
            session,
            job_id=second.id,
            preview_digest=str(second_result["digest"]),
            layout_candidate_id=selected_layout_id,
            layout_candidate_version=1,
            actor_id=actor_id,
        )


def test_active_revalidation_eligibility_and_revision_scope_guards_are_bounded(
    preview_session_factory: sessionmaker[Session],
) -> None:
    """Project deterministic blockers and reject impossible revision-scope states."""
    preview_jobs = importlib.import_module("verboflex.services.preview_jobs")
    product_id, revision_id, mapping_id, _actor_id, _selected_layout_id = (
        _seed_active_revalidation_authority(preview_session_factory)
    )
    with (
        preview_session_factory() as session,
        pytest.raises(PreviewJobNotFound, match="active revision revalidation unavailable"),
    ):
        preview_jobs.get_active_revision_revalidation_eligibility(
            session,
            product_id=uuid4(),
            active_revision_id=revision_id,
            expected_active_revision_version=4,
        )
    with (
        preview_session_factory() as session,
        pytest.raises(PreviewJobConflict, match="active revision revalidation conflict"),
    ):
        preview_jobs.get_active_revision_revalidation_eligibility(
            session,
            product_id=product_id,
            active_revision_id=revision_id,
            expected_active_revision_version=5,
        )
    empty_product_id = uuid4()
    empty_active_revision_id = uuid4()
    empty_candidate_revision_id = uuid4()
    with preview_session_factory.begin() as session:
        empty_product = Product(
            id=empty_product_id,
            display_name=f"Empty authority {empty_product_id}",
            name_key=f"empty authority {empty_product_id}",
            is_active=True,
        )
        session.add(empty_product)
        session.flush()
        session.add_all(
            [
                ProductRevision(
                    id=empty_active_revision_id,
                    product_id=empty_product_id,
                    version=1,
                    is_published=True,
                    published_at=datetime.now(UTC),
                ),
                ProductRevision(
                    id=empty_candidate_revision_id,
                    product_id=empty_product_id,
                    version=1,
                    is_published=False,
                ),
            ]
        )
        session.flush()
        empty_product.active_revision_id = empty_active_revision_id
        empty_product.candidate_revision_id = empty_candidate_revision_id
    with preview_session_factory() as session:
        blocked = preview_jobs.get_active_revision_revalidation_eligibility(
            session,
            product_id=empty_product_id,
            active_revision_id=empty_active_revision_id,
            expected_active_revision_version=1,
        )
    assert blocked.blocker_codes == (
        "product_active",
        "candidate_revision_present",
        "mappings_required",
    )

    product_id, revision_id, mapping_id, _actor_id, _selected_layout_id = (
        _seed_active_revalidation_authority(
            preview_session_factory,
            invalid_mapping=True,
        )
    )
    with preview_session_factory() as session:
        blocked = preview_jobs.get_active_revision_revalidation_eligibility(
            session,
            product_id=product_id,
            active_revision_id=revision_id,
            expected_active_revision_version=4,
        )
    assert blocked.mappings[0].blocker_codes == (
        "mapping_configuration_invalid",
        "layout_required",
    )

    with preview_session_factory() as session:
        row = PreviewJob(
            id=uuid4(),
            input_digest="2" * 64,
            attempt=1,
            state="queued",
            revision_scope="active_revalidation",
            product_id=product_id,
            candidate_revision_id=revision_id,
            candidate_revision_version=4,
            mapping_id=mapping_id,
            topology="separate",
            connection_generation=7,
            detector_version="preview-v1",
            layout_identity="automatic",
            repository_sides=[],
        )
        assert preview_jobs._current_revision(session, row, for_update=False) is not None
        row.revision_scope = cast(Any, "invalid")
        assert preview_jobs._current_revision(session, row, for_update=False) is None
        assert (
            preview_jobs._current_identity_matches(
                row,
                session.get_one(ProductRevision, revision_id),
                session.get_one(ProductRepositoryMapping, mapping_id),
                session.get_one(BitbucketConnection, 1),
            )
            is False
        )
        product = session.get_one(Product, product_id)
        revision = session.get_one(ProductRevision, revision_id)
        with session.no_autoflush:
            product.is_active = True
            assert preview_jobs._current_revision(session, row, for_update=False) is None
            product.is_active = False
            row.revision_scope = "candidate"
            product.candidate_revision_id = uuid4()
            assert preview_jobs._current_revision(session, row, for_update=False) is None
            product.candidate_revision_id = revision_id
            assert preview_jobs._current_revision(session, row, for_update=False) is None
            row.revision_scope = "active_revalidation"
            product.candidate_revision_id = None
            revision.is_published = False
            assert preview_jobs._current_revision(session, row, for_update=False) is None
        session.rollback()
    assert _start_preview_job(preview_session_factory, job_id=uuid4()) is None
