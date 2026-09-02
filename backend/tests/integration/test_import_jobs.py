"""Production tracer for direct published-mapping imports."""

from __future__ import annotations

import asyncio
import importlib
import os
import time
from collections.abc import Generator, Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier, Lock
from typing import Any
from urllib.parse import quote
from uuid import UUID, uuid4

import httpx
import pytest
from alembic import command
from alembic.config import Config
from celery import Celery
from psycopg import connect, sql
from pydantic import SecretStr
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

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
COMMIT_HASH = "b" * 40


@pytest.fixture(scope="module")
def import_session_factory() -> Iterator[sessionmaker[Session]]:
    database_name = f"verboflex_import_jobs_{uuid4().hex}"
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
        if hasattr(app.state, "import_job_enqueuer"):
            del app.state.import_job_enqueuer
        engine.dispose()
        with connect(ADMIN_DATABASE_URL, autocommit=True) as admin_connection:
            admin_connection.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database_name))
            )


@pytest.fixture(autouse=True)
def clean_import_database(
    import_session_factory: sessionmaker[Session],
) -> Iterator[None]:
    app.dependency_overrides.clear()
    if hasattr(app.state, "import_job_enqueuer"):
        del app.state.import_job_enqueuer
    with import_session_factory.begin() as session:
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
    if hasattr(app.state, "import_job_enqueuer"):
        del app.state.import_job_enqueuer


def _settings() -> Settings:
    return Settings(jwt_secret_key=SecretStr(SIGNING_SECRET))


def _configure_dependencies(factory: sessionmaker[Session]) -> None:
    def override_session() -> Generator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_settings] = _settings


def _create_admin(factory: sessionmaker[Session]) -> str:
    user_id = uuid4()
    auth_session_id = uuid4()
    now = datetime.now(UTC)
    with factory.begin() as session:
        role = session.execute(select(Role).where(Role.name == "admin")).scalar_one()
        session.add(
            User(
                id=user_id,
                email=f"admin-{user_id}@example.com",
                display_name="Admin",
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


def _seed_published_direct_mapping(
    factory: sessionmaker[Session],
) -> tuple[UUID, UUID, UUID, UUID]:
    product_id = uuid4()
    revision_id = uuid4()
    repository_id = uuid4()
    mapping_id = uuid4()
    now = datetime.now(UTC)
    with factory.begin() as session:
        product = Product(
            id=product_id,
            display_name=f"Import Product {product_id}",
            name_key=f"import product {product_id}",
            is_active=True,
        )
        session.add(product)
        session.flush()
        session.add_all(
            [
                ProductRevision(
                    id=revision_id,
                    product_id=product_id,
                    description="published",
                    version=7,
                    is_published=False,
                ),
                Repository(
                    id=repository_id,
                    workspace="import-team",
                    repository_slug=f"repo-{repository_id.hex[:12]}",
                    descriptive_name="Direct source",
                    descriptive_name_key="direct source",
                ),
            ]
        )
        session.flush()
        session.add(
            ProductRepositoryMapping(
                id=mapping_id,
                revision_id=revision_id,
                topology="direct",
                identity_key=f'["direct","{repository_id}","main"]',
                sides=[
                    ProductMappingRepositorySide(
                        role="direct",
                        repository_id=repository_id,
                        source_branch="main",
                    )
                ],
                allowed_targets=[ProductMappingAllowedTarget(branch="main", is_default=True)],
            )
        )
        session.flush()
        revision = session.get(ProductRevision, revision_id)
        assert revision is not None
        revision.is_published = True
        revision.published_at = now
        session.flush()
        product.active_revision_id = revision_id
        connection = session.get(BitbucketConnection, 1)
        assert connection is not None
        connection.generation = 9
        connection.access_token_ciphertext = "encrypted-access"
        connection.refresh_token_ciphertext = None
        connection.scope_profile = "repository"
        connection.provider_expires_at = now + timedelta(hours=1)
        connection.connected_at = now
        connection.revoked_at = None
    return product_id, revision_id, repository_id, mapping_id


@dataclass
class PersistedImportEnqueuer:
    factory: sessionmaker[Session]
    payloads: list[tuple[str]] = field(default_factory=list)
    lock: Lock = field(default_factory=Lock)

    def __call__(self, import_id: UUID) -> None:
        with self.factory() as session:
            row = session.execute(
                text("SELECT id, state FROM import_jobs WHERE id = :import_id"),
                {"import_id": import_id},
            ).one()
        assert row.id == import_id
        assert row.state == "queued"
        with self.lock:
            self.payloads.append((str(import_id),))


@dataclass
class ProviderResourceSpy:
    files: dict[str, bytes]
    requests: list[tuple[str, str]] = field(default_factory=list)

    async def resolve_repository_branch(
        self,
        _session: Session,
        *,
        workspace: str,
        repository_slug: str,
        branch: str,
    ) -> BitbucketBranch:
        self.requests.append(
            (
                "GET",
                "https://api.bitbucket.org/2.0/repositories/"
                f"{workspace}/{repository_slug}/refs/branches/{quote(branch, safe='')}",
            )
        )
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
        self.requests.append(
            (
                "GET",
                "https://api.bitbucket.org/2.0/repositories/"
                f"{workspace}/{repository_slug}/src/{commit_hash}/",
            )
        )
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
        self.requests.append(
            (
                "GET",
                "https://api.bitbucket.org/2.0/repositories/"
                f"{workspace}/{repository_slug}/src/{commit_hash}/{quote(path)}",
            )
        )
        return content


async def _request(
    method: str,
    path: str,
    *,
    access_token: str | None,
) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        headers = {"Authorization": f"Bearer {access_token}"} if access_token is not None else None
        return await client.request(method, path, headers=headers)


def _assert_secret_free(value: object) -> None:
    forbidden = {
        "access_token",
        "authorization",
        "celery",
        "ciphertext",
        "oauth",
        "provider_body",
        "raw_source",
        "refresh_token",
        "stack",
        "task_id",
        "url",
    }
    if isinstance(value, dict):
        assert forbidden.isdisjoint(key.casefold() for key in value)
        for child in value.values():
            _assert_secret_free(child)
    elif isinstance(value, list):
        for child in value:
            _assert_secret_free(child)


def test_direct_import_tracer_runs_api_worker_provider_and_persists_baseline(
    import_session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_dependencies(import_session_factory)
    admin_token = _create_admin(import_session_factory)
    product_id, revision_id, repository_id, mapping_id = _seed_published_direct_mapping(
        import_session_factory
    )
    enqueuer = PersistedImportEnqueuer(import_session_factory)
    app.state.import_job_enqueuer = enqueuer
    collection_path = f"/api/v1/admin/products/{product_id}/published/mapping-imports"
    start_path = f"/api/v1/admin/products/{product_id}/published/mappings/{mapping_id}/imports"

    before = asyncio.run(_request("GET", collection_path, access_token=admin_token))
    assert before.status_code == 200
    assert before.json()["items"][0]["state"] == "not_imported"

    created = asyncio.run(_request("POST", start_path, access_token=admin_token))
    assert created.status_code == 202
    created_body = created.json()
    assert created_body["state"] == "queued"
    assert created_body["mapping_id"] == str(mapping_id)
    assert created_body["active_revision_id"] == str(revision_id)
    assert enqueuer.payloads == [(created_body["id"],)]

    spy = ProviderResourceSpy(
        files={
            "mobile/src/main/res/values-it/strings.xml": b"<resources />",
            "mobile/src/main/res/values/strings.xml": b"<resources />",
        }
    )
    import_tasks = importlib.import_module("verboflex.worker.import_tasks")
    monkeypatch.setattr(import_tasks, "SessionFactory", import_session_factory)
    monkeypatch.setattr(
        import_tasks,
        "import_processor",
        lambda identity: import_tasks.process_import(
            identity,
            factory=import_session_factory,
            adapter=spy,
        ),
    )
    test_celery = Celery(
        "verboflex-direct-import-integration",
        broker="memory://",
        backend="cache+memory://",
    )
    test_celery.task(
        name="verboflex.import.run",
        serializer="json",
        ignore_result=True,
    )(import_tasks.run_import_job.run)
    from celery.contrib.testing.worker import start_worker

    with start_worker(
        test_celery,
        pool="solo",
        perform_ping_check=False,
        loglevel="ERROR",
    ):
        test_celery.send_task("verboflex.import.run", args=list(enqueuer.payloads[0]))
        deadline = time.monotonic() + 5
        status_body: dict[str, Any] | None = None
        while time.monotonic() < deadline:
            response = asyncio.run(
                _request(
                    "GET",
                    f"/api/v1/admin/products/{product_id}/imports/{created_body['id']}",
                    access_token=admin_token,
                )
            )
            assert response.status_code == 200
            status_body = response.json()
            if status_body["state"] in {"current", "import_failed"}:
                break
            time.sleep(0.02)
    test_celery.close()

    assert status_body is not None
    assert status_body["state"] == "current"
    assert status_body["active_baseline"] is not None
    references = status_body["active_baseline"]["source_references"]
    assert [reference["path"] for reference in references] == [
        "mobile/src/main/res/values-it/strings.xml",
        "mobile/src/main/res/values/strings.xml",
    ]
    assert [reference["position"] for reference in references] == [0, 1]
    assert {reference["commit_hash"] for reference in references} == {COMMIT_HASH}
    assert {reference["repository_id"] for reference in references} == {str(repository_id)}
    assert all(len(reference["sha256"]) == 64 for reference in references)
    assert all(method == "GET" for method, _url in spy.requests)
    assert all(httpx.URL(url).host == "api.bitbucket.org" for _method, url in spy.requests)
    _assert_secret_free(status_body)
    assert "<resources" not in str(status_body)

    with import_session_factory() as session:
        assert session.scalar(text("SELECT count(*) FROM import_jobs")) == 1
        assert session.scalar(text("SELECT count(*) FROM import_executions")) == 1
        assert session.scalar(text("SELECT count(*) FROM import_source_references")) == 2


def test_concurrent_start_serializes_to_one_logical_import_and_execution(
    import_session_factory: sessionmaker[Session],
) -> None:
    _configure_dependencies(import_session_factory)
    admin_token = _create_admin(import_session_factory)
    product_id, _revision_id, _repository_id, mapping_id = _seed_published_direct_mapping(
        import_session_factory
    )
    enqueuer = PersistedImportEnqueuer(import_session_factory)
    app.state.import_job_enqueuer = enqueuer
    barrier = Barrier(2)
    path = f"/api/v1/admin/products/{product_id}/published/mappings/{mapping_id}/imports"

    def start() -> httpx.Response:
        barrier.wait(timeout=5)
        return asyncio.run(_request("POST", path, access_token=admin_token))

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda _index: start(), range(2)))

    assert [response.status_code for response in responses] == [202, 202]
    records = [response.json() for response in responses]
    assert records[0]["id"] == records[1]["id"]
    assert enqueuer.payloads == [(records[0]["id"],)]
    with import_session_factory() as session:
        assert session.scalar(text("SELECT count(*) FROM import_jobs")) == 1
        assert session.scalar(text("SELECT count(*) FROM import_executions")) == 1
