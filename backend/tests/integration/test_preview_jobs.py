"""Durable administrator preview-job integration contracts."""

from __future__ import annotations

import asyncio
import importlib
import os
import time
from collections.abc import Generator, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from alembic.config import Config
from psycopg import connect, sql
from pydantic import SecretStr
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from verboflex.auth.access_tokens import issue_access_token
from verboflex.auth.passwords import hash_password
from verboflex.core.config import Settings, get_settings
from verboflex.db.session import get_db_session
from verboflex.main import app
from verboflex.models.auth_session import AuthSession
from verboflex.models.bitbucket_connection import BitbucketConnection
from verboflex.models.product import Product, ProductRevision
from verboflex.models.product_mapping import (
    ProductMappingAllowedTarget,
    ProductMappingRepositorySide,
    ProductRepositoryMapping,
)
from verboflex.models.repository import Repository
from verboflex.models.role import Role
from verboflex.models.user import User

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
    assert enqueuer.payloads == [(created_body["id"],)]

    preview_tasks = importlib.import_module("verboflex.worker.preview_tasks")
    celery_app = importlib.import_module("verboflex.worker.celery_app").app
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
    celery_app.conf.update(
        broker_url="memory://",
        result_backend="cache+memory://",
        task_always_eager=False,
        task_ignore_result=True,
    )
    from celery.contrib.testing.worker import start_worker

    with start_worker(
        celery_app,
        pool="solo",
        perform_ping_check=False,
        loglevel="ERROR",
    ):
        celery_app.send_task("verboflex.preview.run", args=list(enqueuer.payloads[0]))
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
