"""Production tracer for direct published-mapping imports."""

from __future__ import annotations

import asyncio
import importlib
import logging
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
    BitbucketProviderReadError,
    BitbucketSourceEntry,
    BitbucketSourcePage,
)
from verboflex.integrations.bitbucket.urls import BitbucketOperation
from verboflex.main import app
from verboflex.models.auth_session import AuthSession
from verboflex.models.bitbucket_connection import BitbucketConnection
from verboflex.models.import_job import ImportExecution, ImportJob
from verboflex.models.product import Product, ProductRevision
from verboflex.models.product_mapping import (
    ProductMappingAllowedTarget,
    ProductMappingRepositorySide,
    ProductRepositoryMapping,
)
from verboflex.models.repository import Repository
from verboflex.models.role import Role
from verboflex.models.user import User
from verboflex.services import import_jobs as import_job_service
from verboflex.services.bitbucket_oauth import PULLREQUEST_WRITE_SCOPE
from verboflex.services.import_jobs import (
    ImportSourceReferenceRecord,
    execute_import_job,
)

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


def _create_principal(factory: sessionmaker[Session], *, role_name: str) -> str:
    user_id = uuid4()
    auth_session_id = uuid4()
    now = datetime.now(UTC)
    with factory.begin() as session:
        role = session.execute(select(Role).where(Role.name == role_name)).scalar_one()
        session.add(
            User(
                id=user_id,
                email=f"{role_name}-{user_id}@example.com",
                display_name=role_name,
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


def _create_admin(factory: sessionmaker[Session]) -> str:
    return _create_principal(factory, role_name="admin")


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
        connection.scope_profile = PULLREQUEST_WRITE_SCOPE
        connection.provider_expires_at = now + timedelta(hours=1)
        connection.connected_at = now
        connection.revoked_at = None
    return product_id, revision_id, repository_id, mapping_id


def _seed_candidate_mapping(
    factory: sessionmaker[Session],
    *,
    product_id: UUID,
) -> UUID:
    revision_id = uuid4()
    repository_id = uuid4()
    mapping_id = uuid4()
    with factory.begin() as session:
        product = session.get(Product, product_id)
        assert product is not None
        session.add_all(
            [
                ProductRevision(
                    id=revision_id,
                    product_id=product_id,
                    description="candidate",
                    version=8,
                    is_published=False,
                ),
                Repository(
                    id=repository_id,
                    workspace="import-team",
                    repository_slug=f"candidate-{repository_id.hex[:12]}",
                    descriptive_name="Candidate source",
                    descriptive_name_key="candidate source",
                ),
            ]
        )
        session.flush()
        session.add(
            ProductRepositoryMapping(
                id=mapping_id,
                revision_id=revision_id,
                topology="direct",
                identity_key=f'["direct","{repository_id}","candidate"]',
                sides=[
                    ProductMappingRepositorySide(
                        role="direct",
                        repository_id=repository_id,
                        source_branch="candidate",
                    )
                ],
                allowed_targets=[ProductMappingAllowedTarget(branch="candidate", is_default=True)],
            )
        )
        session.flush()
        product.candidate_revision_id = revision_id
    return mapping_id


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
        "attempt",
        "attempt_history",
        "attempts",
        "authorization",
        "celery",
        "ciphertext",
        "client_secret",
        "credential",
        "credentials",
        "execution_history",
        "oauth",
        "provider_body",
        "provider_response",
        "provider_url",
        "raw_authority",
        "raw_source",
        "refresh_token",
        "source_bytes",
        "stack",
        "stack_trace",
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


@pytest.mark.parametrize(
    ("role_name", "expected_status"),
    [
        (None, 401),
        ("product_manager_reviewer", 403),
        ("translator", 403),
        ("viewer", 403),
    ],
)
def test_import_authorization_fails_before_mapping_or_dispatch_work(
    import_session_factory: sessionmaker[Session],
    role_name: str | None,
    expected_status: int,
) -> None:
    _configure_dependencies(import_session_factory)
    product_id, _revision_id, _repository_id, mapping_id = _seed_published_direct_mapping(
        import_session_factory
    )
    token = (
        _create_principal(import_session_factory, role_name=role_name)
        if role_name is not None
        else None
    )
    enqueuer = PersistedImportEnqueuer(import_session_factory)
    app.state.import_job_enqueuer = enqueuer
    unknown_import_id = uuid4()

    responses = [
        asyncio.run(
            _request(
                "GET",
                f"/api/v1/admin/products/{product_id}/published/mapping-imports",
                access_token=token,
            )
        ),
        asyncio.run(
            _request(
                "POST",
                f"/api/v1/admin/products/{product_id}/published/mappings/{mapping_id}/imports",
                access_token=token,
            )
        ),
        asyncio.run(
            _request(
                "GET",
                f"/api/v1/admin/products/{product_id}/imports/{unknown_import_id}",
                access_token=token,
            )
        ),
    ]

    assert [response.status_code for response in responses] == [expected_status] * 3
    assert enqueuer.payloads == []
    with import_session_factory() as session:
        assert session.scalar(text("SELECT count(*) FROM import_jobs")) == 0
        assert session.scalar(text("SELECT count(*) FROM import_executions")) == 0


def test_import_ownership_rejects_candidate_inactive_wrong_and_forged_identities(
    import_session_factory: sessionmaker[Session],
) -> None:
    _configure_dependencies(import_session_factory)
    admin_token = _create_admin(import_session_factory)
    product_id, _revision_id, _repository_id, mapping_id = _seed_published_direct_mapping(
        import_session_factory
    )
    candidate_mapping_id = _seed_candidate_mapping(
        import_session_factory,
        product_id=product_id,
    )
    other_product_id, _other_revision, _other_repository, other_mapping_id = (
        _seed_published_direct_mapping(import_session_factory)
    )
    enqueuer = PersistedImportEnqueuer(import_session_factory)
    app.state.import_job_enqueuer = enqueuer

    rejected_paths = [
        f"/api/v1/admin/products/{product_id}/published/mappings/{candidate_mapping_id}/imports",
        f"/api/v1/admin/products/{product_id}/published/mappings/{other_mapping_id}/imports",
        f"/api/v1/admin/products/{product_id}/published/mappings/{uuid4()}/imports",
    ]
    rejected = [
        asyncio.run(_request("POST", path, access_token=admin_token)) for path in rejected_paths
    ]
    assert [response.status_code for response in rejected] == [404, 404, 404]
    assert enqueuer.payloads == []

    created = asyncio.run(
        _request(
            "POST",
            f"/api/v1/admin/products/{product_id}/published/mappings/{mapping_id}/imports",
            access_token=admin_token,
        )
    )
    assert created.status_code == 202
    import_id = created.json()["id"]
    wrong_product = asyncio.run(
        _request(
            "GET",
            f"/api/v1/admin/products/{other_product_id}/imports/{import_id}",
            access_token=admin_token,
        )
    )
    assert wrong_product.status_code == 404

    with import_session_factory.begin() as session:
        product = session.get(Product, product_id)
        assert product is not None
        product.is_active = False

    inactive_list = asyncio.run(
        _request(
            "GET",
            f"/api/v1/admin/products/{product_id}/published/mapping-imports",
            access_token=admin_token,
        )
    )
    inactive_start = asyncio.run(
        _request(
            "POST",
            f"/api/v1/admin/products/{product_id}/published/mappings/{mapping_id}/imports",
            access_token=admin_token,
        )
    )
    inactive_status = asyncio.run(
        _request(
            "GET",
            f"/api/v1/admin/products/{product_id}/imports/{import_id}",
            access_token=admin_token,
        )
    )
    assert [
        inactive_list.status_code,
        inactive_start.status_code,
        inactive_status.status_code,
    ] == [404, 404, 404]
    assert enqueuer.payloads == [(import_id,)]


def _successful_reference(repository_id: UUID) -> ImportSourceReferenceRecord:
    return ImportSourceReferenceRecord(
        position=0,
        repository_side="direct",
        repository_id=repository_id,
        source_branch="main",
        commit_hash=COMMIT_HASH,
        path="mobile/src/main/res/values/strings.xml",
        size_bytes=13,
        sha256="a" * 64,
    )


def _successful_reference_at(
    repository_id: UUID,
    *,
    commit_hash: str,
) -> ImportSourceReferenceRecord:
    return ImportSourceReferenceRecord(
        position=0,
        repository_side="direct",
        repository_id=repository_id,
        source_branch="main",
        commit_hash=commit_hash,
        path="mobile/src/main/res/values/strings.xml",
        size_bytes=13,
        sha256="a" * 64,
    )


def test_transition_current_refresh_increments_execution_without_retry(
    import_session_factory: sessionmaker[Session],
) -> None:
    _configure_dependencies(import_session_factory)
    admin_token = _create_admin(import_session_factory)
    product_id, _revision_id, repository_id, mapping_id = _seed_published_direct_mapping(
        import_session_factory
    )
    enqueuer = PersistedImportEnqueuer(import_session_factory)
    app.state.import_job_enqueuer = enqueuer
    start_path = f"/api/v1/admin/products/{product_id}/published/mappings/{mapping_id}/imports"

    initial = asyncio.run(_request("POST", start_path, access_token=admin_token))
    assert initial.status_code == 202
    import_id = UUID(initial.json()["id"])
    execute_import_job(
        import_session_factory,
        import_id=import_id,
        processor=lambda _identity: (_successful_reference(repository_id),),
    )

    refreshed = asyncio.run(_request("POST", start_path, access_token=admin_token))
    assert refreshed.status_code == 202
    assert refreshed.json()["id"] == str(import_id)
    assert refreshed.json()["state"] == "queued"
    assert refreshed.json()["retry_count"] == 0
    assert enqueuer.payloads == [(str(import_id),), (str(import_id),)]
    with import_session_factory() as session:
        job = session.get(ImportJob, import_id)
        assert job is not None
        executions = tuple(
            session.execute(
                select(ImportExecution)
                .where(ImportExecution.import_job_id == import_id)
                .order_by(ImportExecution.sequence)
            ).scalars()
        )
        assert [execution.sequence for execution in executions] == [1, 2]
        assert job.current_execution_id == executions[1].id
        assert job.active_baseline_execution_id == executions[0].id


def test_same_commit_refresh_retains_the_active_baseline_pointer(
    import_session_factory: sessionmaker[Session],
) -> None:
    _configure_dependencies(import_session_factory)
    admin_token = _create_admin(import_session_factory)
    product_id, _revision_id, repository_id, mapping_id = _seed_published_direct_mapping(
        import_session_factory
    )
    app.state.import_job_enqueuer = PersistedImportEnqueuer(import_session_factory)
    start_path = f"/api/v1/admin/products/{product_id}/published/mappings/{mapping_id}/imports"

    initial = asyncio.run(_request("POST", start_path, access_token=admin_token))
    import_id = UUID(initial.json()["id"])
    reference = _successful_reference(repository_id)
    execute_import_job(
        import_session_factory,
        import_id=import_id,
        processor=lambda _identity: (reference,),
    )
    with import_session_factory() as session:
        before = session.get(ImportJob, import_id)
        assert before is not None
        original_baseline_id = before.active_baseline_execution_id
        assert original_baseline_id is not None

    refreshed = asyncio.run(_request("POST", start_path, access_token=admin_token))
    assert refreshed.status_code == 202
    execute_import_job(
        import_session_factory,
        import_id=import_id,
        processor=lambda _identity: (reference,),
    )

    with import_session_factory() as session:
        after = session.get(ImportJob, import_id)
        assert after is not None
        assert after.state == "current"
        assert after.retry_count == 0
        assert after.active_baseline_execution_id == original_baseline_id
        assert after.current_execution_id != original_baseline_id


def test_retry_replaces_current_projection_and_retains_the_previous_baseline(
    import_session_factory: sessionmaker[Session],
) -> None:
    _configure_dependencies(import_session_factory)
    admin_token = _create_admin(import_session_factory)
    product_id, _revision_id, repository_id, mapping_id = _seed_published_direct_mapping(
        import_session_factory
    )
    app.state.import_job_enqueuer = PersistedImportEnqueuer(import_session_factory)
    start_path = f"/api/v1/admin/products/{product_id}/published/mappings/{mapping_id}/imports"
    status_path: str

    initial = asyncio.run(_request("POST", start_path, access_token=admin_token))
    import_id = UUID(initial.json()["id"])
    status_path = f"/api/v1/admin/products/{product_id}/imports/{import_id}"
    execute_import_job(
        import_session_factory,
        import_id=import_id,
        processor=lambda _identity: (_successful_reference(repository_id),),
    )
    original = asyncio.run(_request("GET", status_path, access_token=admin_token)).json()

    refresh = asyncio.run(_request("POST", start_path, access_token=admin_token))
    assert refresh.status_code == 202
    execute_import_job(
        import_session_factory,
        import_id=import_id,
        processor=lambda _identity: (),
    )
    failed = asyncio.run(_request("GET", status_path, access_token=admin_token)).json()
    assert failed["state"] == "import_failed"
    assert failed["retry_count"] == 0
    assert failed["active_baseline"] == original["active_baseline"]

    retried = asyncio.run(_request("POST", start_path, access_token=admin_token))
    retried_body = retried.json()
    assert retried.status_code == 202
    assert retried_body["id"] == str(import_id)
    assert retried_body["state"] == "queued"
    assert retried_body["retry_count"] == 1
    assert retried_body["error_category"] is None
    assert retried_body["error_message"] is None

    next_commit = "c" * 40
    execute_import_job(
        import_session_factory,
        import_id=import_id,
        processor=lambda _identity: (
            _successful_reference_at(repository_id, commit_hash=next_commit),
        ),
    )
    current = asyncio.run(_request("GET", status_path, access_token=admin_token)).json()
    assert current["state"] == "current"
    assert current["retry_count"] == 1
    assert current["active_baseline"]["source_references"][0]["commit_hash"] == next_commit
    _assert_secret_free(current)
    assert {
        "current_execution_id",
        "connection_generation",
        "execution_history",
        "attempt_history",
    }.isdisjoint(current)
    with import_session_factory() as session:
        executions = tuple(
            session.execute(
                select(ImportExecution)
                .where(ImportExecution.import_job_id == import_id)
                .order_by(ImportExecution.sequence)
            ).scalars()
        )
        assert [execution.sequence for execution in executions] == [1, 2, 3]


def test_current_capability_generation_is_revalidated_before_completion(
    import_session_factory: sessionmaker[Session],
) -> None:
    _configure_dependencies(import_session_factory)
    admin_token = _create_admin(import_session_factory)
    product_id, _revision_id, repository_id, mapping_id = _seed_published_direct_mapping(
        import_session_factory
    )
    app.state.import_job_enqueuer = PersistedImportEnqueuer(import_session_factory)
    start_path = f"/api/v1/admin/products/{product_id}/published/mappings/{mapping_id}/imports"

    created = asyncio.run(_request("POST", start_path, access_token=admin_token))
    assert created.status_code == 202
    import_id = UUID(created.json()["id"])
    identity = import_job_service.start_import_execution(
        import_session_factory,
        import_id=import_id,
    )
    assert identity is not None

    with import_session_factory.begin() as session:
        connection = session.get(BitbucketConnection, 1)
        assert connection is not None
        connection.generation += 1

    terminalized = import_job_service.finish_import_execution(
        import_session_factory,
        identity=identity,
        references=(_successful_reference(repository_id),),
    )
    assert terminalized is True
    response = asyncio.run(
        _request(
            "GET",
            f"/api/v1/admin/products/{product_id}/imports/{import_id}",
            access_token=admin_token,
        )
    )
    assert response.status_code == 200
    assert response.json()["state"] == "import_failed"
    assert response.json()["active_baseline"] is None


def test_late_worker_completion_cannot_overwrite_a_newer_retry(
    import_session_factory: sessionmaker[Session],
) -> None:
    _configure_dependencies(import_session_factory)
    admin_token = _create_admin(import_session_factory)
    product_id, _revision_id, repository_id, mapping_id = _seed_published_direct_mapping(
        import_session_factory
    )
    app.state.import_job_enqueuer = PersistedImportEnqueuer(import_session_factory)
    start_path = f"/api/v1/admin/products/{product_id}/published/mappings/{mapping_id}/imports"

    created = asyncio.run(_request("POST", start_path, access_token=admin_token))
    import_id = UUID(created.json()["id"])
    first_identity = import_job_service.start_import_execution(
        import_session_factory,
        import_id=import_id,
    )
    assert first_identity is not None
    assert import_job_service.finish_import_execution(
        import_session_factory,
        identity=first_identity,
        references=None,
    )

    retried = asyncio.run(_request("POST", start_path, access_token=admin_token))
    assert retried.status_code == 202
    assert retried.json()["retry_count"] == 1
    assert (
        import_job_service.finish_import_execution(
            import_session_factory,
            identity=first_identity,
            references=(_successful_reference(repository_id),),
        )
        is False
    )
    with import_session_factory() as session:
        job = session.get(ImportJob, import_id)
        assert job is not None
        current_execution = session.get(ImportExecution, job.current_execution_id)
        assert current_execution is not None
        assert job.state == "queued"
        assert job.active_baseline_execution_id is None
        assert current_execution.sequence == 2
        assert current_execution.state == "queued"


def test_import_empty_source_terminalizes_and_preserves_the_last_baseline(
    import_session_factory: sessionmaker[Session],
) -> None:
    _configure_dependencies(import_session_factory)
    admin_token = _create_admin(import_session_factory)
    product_id, _revision_id, repository_id, mapping_id = _seed_published_direct_mapping(
        import_session_factory
    )
    enqueuer = PersistedImportEnqueuer(import_session_factory)
    app.state.import_job_enqueuer = enqueuer
    start_path = f"/api/v1/admin/products/{product_id}/published/mappings/{mapping_id}/imports"

    initial = asyncio.run(_request("POST", start_path, access_token=admin_token))
    assert initial.status_code == 202
    import_id = UUID(initial.json()["id"])
    execute_import_job(
        import_session_factory,
        import_id=import_id,
        processor=lambda _identity: (_successful_reference(repository_id),),
    )
    baseline = asyncio.run(
        _request(
            "GET",
            f"/api/v1/admin/products/{product_id}/imports/{import_id}",
            access_token=admin_token,
        )
    ).json()["active_baseline"]
    assert baseline is not None

    retry = asyncio.run(_request("POST", start_path, access_token=admin_token))
    assert retry.status_code == 202
    assert retry.json()["state"] == "queued"
    execute_import_job(
        import_session_factory,
        import_id=import_id,
        processor=lambda _identity: (),
    )
    failed = asyncio.run(
        _request(
            "GET",
            f"/api/v1/admin/products/{product_id}/imports/{import_id}",
            access_token=admin_token,
        )
    )
    assert failed.status_code == 200
    body = failed.json()
    assert body["state"] == "import_failed"
    assert body["active_baseline"] == baseline
    assert body["error_category"] == "provider_unavailable"
    _assert_secret_free(body)


def test_import_enqueue_failure_is_terminal_bounded_and_baseline_preserving(
    import_session_factory: sessionmaker[Session],
) -> None:
    _configure_dependencies(import_session_factory)
    admin_token = _create_admin(import_session_factory)
    product_id, _revision_id, repository_id, mapping_id = _seed_published_direct_mapping(
        import_session_factory
    )
    enqueuer = PersistedImportEnqueuer(import_session_factory)
    app.state.import_job_enqueuer = enqueuer
    start_path = f"/api/v1/admin/products/{product_id}/published/mappings/{mapping_id}/imports"

    initial = asyncio.run(_request("POST", start_path, access_token=admin_token))
    import_id = UUID(initial.json()["id"])
    execute_import_job(
        import_session_factory,
        import_id=import_id,
        processor=lambda _identity: (_successful_reference(repository_id),),
    )
    before = asyncio.run(
        _request(
            "GET",
            f"/api/v1/admin/products/{product_id}/imports/{import_id}",
            access_token=admin_token,
        )
    ).json()["active_baseline"]

    def fail_dispatch(_import_id: UUID) -> None:
        raise RuntimeError(
            "provider body with access_token=secret, task_id=unsafe, url=https://unsafe.invalid"
        )

    app.state.import_job_enqueuer = fail_dispatch
    failed = asyncio.run(_request("POST", start_path, access_token=admin_token))
    assert failed.status_code == 202
    body = failed.json()
    assert body["state"] == "import_failed"
    assert body["active_baseline"] == before
    assert body["retry_count"] == 1
    assert body["error_category"] == "provider_unavailable"
    assert "secret" not in str(body).casefold()
    assert "unsafe" not in str(body).casefold()
    _assert_secret_free(body)
    with import_session_factory() as session:
        job = session.get(ImportJob, import_id)
        assert job is not None
        execution = session.get(ImportExecution, job.current_execution_id)
        assert execution is not None
        assert execution.state == "failed"
        assert execution.started_at is not None
        assert execution.finished_at is not None


@pytest.mark.parametrize(
    ("failure_kind", "provider_status", "operation"),
    [
        ("reauthorization_required", 401, BitbucketOperation.BRANCH_RESOLVE),
        ("permission_denied", 403, BitbucketOperation.SOURCE_TREE),
        ("rate_limited", 429, BitbucketOperation.SOURCE_FILE),
        ("not_found", 404, BitbucketOperation.BRANCH_RESOLVE),
        ("timeout", 504, BitbucketOperation.SOURCE_TREE),
        ("unavailable", 503, BitbucketOperation.SOURCE_FILE),
        ("invalid_source", 200, BitbucketOperation.SOURCE_TREE),
        ("limit_exceeded", 200, BitbucketOperation.SOURCE_FILE),
    ],
)
def test_terminal_provider_failure_emits_one_sanitized_diagnostic_and_public_error(
    import_session_factory: sessionmaker[Session],
    caplog: pytest.LogCaptureFixture,
    failure_kind: str,
    provider_status: int,
    operation: BitbucketOperation,
) -> None:
    _configure_dependencies(import_session_factory)
    admin_token = _create_admin(import_session_factory)
    product_id, _revision_id, _repository_id, mapping_id = _seed_published_direct_mapping(
        import_session_factory
    )
    app.state.import_job_enqueuer = PersistedImportEnqueuer(import_session_factory)
    start_path = f"/api/v1/admin/products/{product_id}/published/mappings/{mapping_id}/imports"
    created = asyncio.run(_request("POST", start_path, access_token=admin_token))
    assert created.status_code == 202
    import_id = UUID(created.json()["id"])
    attempts = 0

    def fail_provider(_identity: object) -> tuple[ImportSourceReferenceRecord, ...]:
        nonlocal attempts
        attempts += 1
        raise BitbucketProviderReadError(
            kind=failure_kind,  # type: ignore[arg-type]
            provider_status=provider_status,
            operation=operation,
        )

    caplog.set_level(logging.INFO, logger="verboflex.bitbucket.operations")
    execute_import_job(
        import_session_factory,
        import_id=import_id,
        processor=fail_provider,
    )

    diagnostic_records = [
        record
        for record in caplog.records
        if record.name == "verboflex.bitbucket.operations"
        and getattr(record, "event_name", None) == "bitbucket.provider_operation_failed"
    ]
    assert attempts == 1
    assert len(diagnostic_records) == 1
    diagnostic = diagnostic_records[0]
    assert {
        "operation": diagnostic.operation,
        "error_category": diagnostic.error_category,
        "provider_status": diagnostic.provider_status,
        "correlation_id": diagnostic.correlation_id,
        "import_id": diagnostic.import_id,
        "execution_number": diagnostic.execution_number,
    } == {
        "operation": operation.value,
        "error_category": failure_kind,
        "provider_status": provider_status,
        "correlation_id": str(import_id),
        "import_id": str(import_id),
        "execution_number": 1,
    }
    assert isinstance(diagnostic.elapsed_ms, int)
    assert 0 <= diagnostic.elapsed_ms <= 2_147_483_647

    response = asyncio.run(
        _request(
            "GET",
            f"/api/v1/admin/products/{product_id}/imports/{import_id}",
            access_token=admin_token,
        )
    )
    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "import_failed"
    assert body["error_category"] == "provider_unavailable"
    assert body["error_message"] == (
        "This import did not complete. Review the reason, then retry from the mapping. "
        "No import baseline was created."
    )
    _assert_secret_free(body)


def test_diagnostic_handler_failure_cannot_change_import_terminalization(
    import_session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from verboflex.integrations.bitbucket import diagnostics

    _configure_dependencies(import_session_factory)
    admin_token = _create_admin(import_session_factory)
    product_id, _revision_id, _repository_id, mapping_id = _seed_published_direct_mapping(
        import_session_factory
    )
    app.state.import_job_enqueuer = PersistedImportEnqueuer(import_session_factory)
    start_path = f"/api/v1/admin/products/{product_id}/published/mappings/{mapping_id}/imports"
    created = asyncio.run(_request("POST", start_path, access_token=admin_token))
    assert created.status_code == 202
    import_id = UUID(created.json()["id"])

    class FailingLogger:
        def info(self, *_args: object, **_kwargs: object) -> None:
            raise RuntimeError("provider-body-logging-handler-canary")

    monkeypatch.setattr(diagnostics, "_LOGGER", FailingLogger())

    def fail_provider(_identity: object) -> tuple[ImportSourceReferenceRecord, ...]:
        raise BitbucketProviderReadError(
            kind="unavailable",
            provider_status=503,
            operation=BitbucketOperation.SOURCE_FILE,
        )

    execute_import_job(
        import_session_factory,
        import_id=import_id,
        processor=fail_provider,
    )

    response = asyncio.run(
        _request(
            "GET",
            f"/api/v1/admin/products/{product_id}/imports/{import_id}",
            access_token=admin_token,
        )
    )
    assert response.status_code == 200
    assert response.json()["state"] == "import_failed"
    assert response.json()["error_category"] == "provider_unavailable"
    assert "canary" not in str(response.json()).casefold()
