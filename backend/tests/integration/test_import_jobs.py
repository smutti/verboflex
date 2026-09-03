"""Production tracer for direct published-mapping imports."""

from __future__ import annotations

import asyncio
import importlib
import logging
import os
import time
from collections.abc import Generator, Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
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
from pydantic import SecretStr, ValidationError
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from verboflex.auth.access_tokens import issue_access_token
from verboflex.auth.passwords import hash_password
from verboflex.core.config import Settings, get_settings
from verboflex.db.session import get_db_session
from verboflex.integrations.bitbucket.client import (
    BitbucketAncestry,
    BitbucketBranch,
    BitbucketCommitDelta,
    BitbucketFileDelta,
    BitbucketProviderReadError,
    BitbucketSourceEntry,
    BitbucketSourcePage,
)
from verboflex.integrations.bitbucket.urls import BitbucketOperation
from verboflex.main import app
from verboflex.models.auth_session import AuthSession
from verboflex.models.bitbucket_connection import BitbucketConnection
from verboflex.models.import_job import (
    ImportExecution,
    ImportJob,
    ImportRewriteDelta,
    ImportRewriteProposal,
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
from verboflex.services import import_jobs as import_job_service
from verboflex.services.bitbucket_oauth import PULLREQUEST_WRITE_SCOPE
from verboflex.services.import_jobs import (
    ImportSourceReferenceRecord,
    execute_import_job,
    finish_import_execution,
    start_import_execution,
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


def _seed_published_separate_mapping(
    factory: sessionmaker[Session],
) -> tuple[UUID, UUID, UUID, UUID, UUID]:
    product_id = uuid4()
    revision_id = uuid4()
    keys_repository_id = uuid4()
    translations_repository_id = uuid4()
    mapping_id = uuid4()
    now = datetime.now(UTC)
    with factory.begin() as session:
        product = Product(
            id=product_id,
            display_name=f"Separate Import Product {product_id}",
            name_key=f"separate import product {product_id}",
            is_active=True,
        )
        session.add(product)
        session.flush()
        session.add_all(
            [
                ProductRevision(
                    id=revision_id,
                    product_id=product_id,
                    description="published separate",
                    version=7,
                    is_published=False,
                ),
                Repository(
                    id=keys_repository_id,
                    workspace="import-team",
                    repository_slug=f"keys-{keys_repository_id.hex[:12]}",
                    descriptive_name="Keys source",
                    descriptive_name_key="keys source",
                ),
                Repository(
                    id=translations_repository_id,
                    workspace="import-team",
                    repository_slug=f"translations-{translations_repository_id.hex[:12]}",
                    descriptive_name="Translations source",
                    descriptive_name_key="translations source",
                ),
            ]
        )
        session.flush()
        session.add(
            ProductRepositoryMapping(
                id=mapping_id,
                revision_id=revision_id,
                topology="separate",
                identity_key=(
                    f'[["keys","{keys_repository_id}","main"],'
                    f'["translations","{translations_repository_id}","main"]]'
                ),
                sides=[
                    ProductMappingRepositorySide(
                        role="keys",
                        repository_id=keys_repository_id,
                        source_branch="main",
                    ),
                    ProductMappingRepositorySide(
                        role="translations",
                        repository_id=translations_repository_id,
                        source_branch="main",
                    ),
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
    return (
        product_id,
        revision_id,
        keys_repository_id,
        translations_repository_id,
        mapping_id,
    )


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
    commit_hashes: list[str] = field(default_factory=lambda: [COMMIT_HASH])
    branch_resolution_count: int = 0

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
        commit_hash = self.commit_hashes[
            min(self.branch_resolution_count, len(self.commit_hashes) - 1)
        ]
        self.branch_resolution_count += 1
        return BitbucketBranch(name=branch, commit_hash=commit_hash)

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


@dataclass
class SourceMovementAdapterSpy:
    ancestries: dict[tuple[str, str, str], BitbucketAncestry]
    deltas: dict[tuple[str, str, str, str], BitbucketCommitDelta] = field(default_factory=dict)
    requests: list[tuple[str, str, str, str]] = field(default_factory=list)

    async def compare_repository_ancestry(
        self,
        _session: Session,
        *,
        workspace: str,
        repository_slug: str,
        old_commit_hash: str,
        new_commit_hash: str,
    ) -> BitbucketAncestry:
        self.requests.append(("ancestry", repository_slug, old_commit_hash, new_commit_hash))
        return self.ancestries[(repository_slug, old_commit_hash, new_commit_hash)]

    async def list_repository_diffstat(
        self,
        _session: Session,
        *,
        workspace: str,
        repository_slug: str,
        old_commit_hash: str,
        new_commit_hash: str,
        repository_side: str,
    ) -> BitbucketCommitDelta:
        self.requests.append(("diffstat", repository_slug, old_commit_hash, new_commit_hash))
        return self.deltas[(repository_slug, old_commit_hash, new_commit_hash, repository_side)]


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

    duplicate_queued = asyncio.run(_request("POST", start_path, access_token=admin_token))
    assert duplicate_queued.status_code == 202
    assert duplicate_queued.json()["state"] == "queued"
    assert enqueuer.payloads == [(str(import_id),), (str(import_id),)]
    running_identity = import_job_service.start_import_execution(
        import_session_factory,
        import_id=import_id,
    )
    assert running_identity is not None
    duplicate_running = asyncio.run(_request("POST", start_path, access_token=admin_token))
    assert duplicate_running.status_code == 202
    assert duplicate_running.json()["state"] == "running"
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


def test_current_capability_and_branch_resolution_are_fresh_for_every_execution(
    import_session_factory: sessionmaker[Session],
) -> None:
    _configure_dependencies(import_session_factory)
    admin_token = _create_admin(import_session_factory)
    product_id, _revision_id, _repository_id, mapping_id = _seed_published_direct_mapping(
        import_session_factory
    )
    app.state.import_job_enqueuer = PersistedImportEnqueuer(import_session_factory)
    start_path = f"/api/v1/admin/products/{product_id}/published/mappings/{mapping_id}/imports"
    first_commit = "b" * 40
    second_commit = "c" * 40
    spy = ProviderResourceSpy(
        files={"mobile/src/main/res/values/strings.xml": b"<resources />"},
        commit_hashes=[first_commit, second_commit],
    )

    initial = asyncio.run(_request("POST", start_path, access_token=admin_token))
    assert initial.status_code == 202
    import_id = UUID(initial.json()["id"])
    execute_import_job(
        import_session_factory,
        import_id=import_id,
        processor=lambda identity: import_job_service.process_import(
            identity,
            factory=import_session_factory,
            adapter=spy,
        ),
    )
    refreshed = asyncio.run(_request("POST", start_path, access_token=admin_token))
    assert refreshed.status_code == 202
    execute_import_job(
        import_session_factory,
        import_id=import_id,
        processor=lambda identity: import_job_service.process_import(
            identity,
            factory=import_session_factory,
            adapter=spy,
        ),
    )

    assert spy.branch_resolution_count == 2
    status = asyncio.run(
        _request(
            "GET",
            f"/api/v1/admin/products/{product_id}/imports/{import_id}",
            access_token=admin_token,
        )
    )
    assert status.status_code == 200
    assert status.json()["retry_count"] == 0
    assert {
        reference["commit_hash"]
        for reference in status.json()["active_baseline"]["source_references"]
    } == {second_commit}


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
    assert body["retry_count"] == 0
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


def test_separate_import_activates_keys_then_translations_as_one_ordered_baseline(
    import_session_factory: sessionmaker[Session],
) -> None:
    _configure_dependencies(import_session_factory)
    admin_token = _create_admin(import_session_factory)
    (
        product_id,
        revision_id,
        keys_repository_id,
        translations_repository_id,
        mapping_id,
    ) = _seed_published_separate_mapping(import_session_factory)
    enqueuer = PersistedImportEnqueuer(import_session_factory)
    app.state.import_job_enqueuer = enqueuer
    start_path = f"/api/v1/admin/products/{product_id}/published/mappings/{mapping_id}/imports"

    before = asyncio.run(
        _request(
            "GET",
            f"/api/v1/admin/products/{product_id}/published/mapping-imports",
            access_token=admin_token,
        )
    )
    assert before.status_code == 200
    assert before.json()["items"] == [
        {
            "id": None,
            "mapping_id": str(mapping_id),
            "active_revision_id": str(revision_id),
            "topology": "separate",
            "repository_sides": [
                {
                    "role": "keys",
                    "repository_id": str(keys_repository_id),
                    "source_branch": "main",
                },
                {
                    "role": "translations",
                    "repository_id": str(translations_repository_id),
                    "source_branch": "main",
                },
            ],
            "state": "not_imported",
            "active_baseline": None,
            "latest_execution_at": None,
            "retry_count": 0,
            "error_category": None,
            "error_message": None,
        }
    ]

    created = asyncio.run(_request("POST", start_path, access_token=admin_token))
    assert created.status_code == 202
    import_id = UUID(created.json()["id"])
    spy = ProviderResourceSpy(
        files={"locales/messages.json": b'{"hello":"ciao"}'},
        commit_hashes=["c" * 40, "d" * 40],
    )
    identity = start_import_execution(import_session_factory, import_id=import_id)
    assert identity is not None
    references = import_job_service.process_import(
        identity,
        factory=import_session_factory,
        adapter=spy,
    )
    assert finish_import_execution(
        import_session_factory,
        identity=identity,
        references=references,
    )

    completed = asyncio.run(
        _request(
            "GET",
            f"/api/v1/admin/products/{product_id}/imports/{import_id}",
            access_token=admin_token,
        )
    )
    assert completed.status_code == 200
    source_references = completed.json()["active_baseline"]["source_references"]
    assert [reference["position"] for reference in source_references] == [0, 1]
    assert [reference["repository_side"] for reference in source_references] == [
        "keys",
        "translations",
    ]
    assert [reference["repository_id"] for reference in source_references] == [
        str(keys_repository_id),
        str(translations_repository_id),
    ]
    assert [reference["commit_hash"] for reference in source_references] == [
        "c" * 40,
        "d" * 40,
    ]
    assert [reference["path"] for reference in source_references] == [
        "locales/messages.json",
        "locales/messages.json",
    ]


def test_separate_one_side_failure_preserves_prior_complete_pair(
    import_session_factory: sessionmaker[Session],
) -> None:
    _configure_dependencies(import_session_factory)
    admin_token = _create_admin(import_session_factory)
    (
        product_id,
        _revision_id,
        keys_repository_id,
        translations_repository_id,
        mapping_id,
    ) = _seed_published_separate_mapping(import_session_factory)
    app.state.import_job_enqueuer = PersistedImportEnqueuer(import_session_factory)
    start_path = f"/api/v1/admin/products/{product_id}/published/mappings/{mapping_id}/imports"
    created = asyncio.run(_request("POST", start_path, access_token=admin_token))
    import_id = UUID(created.json()["id"])

    def complete_pair(_identity: object) -> tuple[ImportSourceReferenceRecord, ...]:
        return (
            ImportSourceReferenceRecord(
                position=0,
                repository_side="keys",
                repository_id=keys_repository_id,
                source_branch="main",
                commit_hash="1" * 40,
                path="same/messages.json",
                size_bytes=10,
                sha256="a" * 64,
            ),
            ImportSourceReferenceRecord(
                position=1,
                repository_side="translations",
                repository_id=translations_repository_id,
                source_branch="main",
                commit_hash="2" * 40,
                path="same/messages.json",
                size_bytes=11,
                sha256="b" * 64,
            ),
        )

    execute_import_job(import_session_factory, import_id=import_id, processor=complete_pair)
    with import_session_factory() as session:
        original_job = session.get_one(ImportJob, import_id)
        original_baseline_id = original_job.active_baseline_execution_id
    assert original_baseline_id is not None

    refresh = asyncio.run(_request("POST", start_path, access_token=admin_token))
    assert refresh.status_code == 202

    def incomplete_pair(_identity: object) -> tuple[ImportSourceReferenceRecord, ...]:
        return complete_pair(_identity)[:1]

    execute_import_job(import_session_factory, import_id=import_id, processor=incomplete_pair)

    with import_session_factory() as session:
        failed_job = session.get_one(ImportJob, import_id)
        failed_execution_id = failed_job.current_execution_id
        failed_execution = session.get_one(ImportExecution, failed_execution_id)
        assert failed_job.state == "import_failed"
        assert failed_execution.state == "failed"
        assert failed_job.active_baseline_execution_id == original_baseline_id
        assert (
            session.scalar(
                text(
                    "SELECT count(*) FROM import_source_references "
                    "WHERE execution_id = :execution_id"
                ),
                {"execution_id": failed_execution_id},
            )
            == 0
        )
    failed = asyncio.run(
        _request(
            "GET",
            f"/api/v1/admin/products/{product_id}/imports/{import_id}",
            access_token=admin_token,
        )
    ).json()
    assert [
        reference["repository_side"] for reference in failed["active_baseline"]["source_references"]
    ] == [
        "keys",
        "translations",
    ]


def test_worker_loss_watchdog_terminalizes_once_at_inclusive_bound_and_ignores_late_finish(
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
    execute_import_job(
        import_session_factory,
        import_id=import_id,
        processor=lambda _identity: (_successful_reference(repository_id),),
    )
    with import_session_factory() as session:
        original_baseline_id = session.get_one(ImportJob, import_id).active_baseline_execution_id
    assert original_baseline_id is not None

    refreshed = asyncio.run(_request("POST", start_path, access_token=admin_token))
    assert refreshed.status_code == 202
    identity = start_import_execution(import_session_factory, import_id=import_id)
    assert identity is not None
    now = datetime(2030, 1, 2, 3, 4, 5, tzinfo=UTC)
    cutoff = now - timedelta(seconds=90)
    with import_session_factory.begin() as session:
        execution = session.get_one(ImportExecution, identity.execution_id)
        execution.started_at = cutoff + timedelta(seconds=1)

    assert (
        import_job_service.reconcile_stale_imports(
            import_session_factory,
            hard_time_limit_seconds=75,
            watchdog_grace_seconds=15,
            clock=lambda: now,
        )
        == 0
    )
    with import_session_factory.begin() as session:
        execution = session.get_one(ImportExecution, identity.execution_id)
        execution.started_at = cutoff

    assert (
        import_job_service.reconcile_stale_imports(
            import_session_factory,
            hard_time_limit_seconds=75,
            watchdog_grace_seconds=15,
            clock=lambda: now,
        )
        == 1
    )
    assert (
        import_job_service.reconcile_stale_imports(
            import_session_factory,
            hard_time_limit_seconds=75,
            watchdog_grace_seconds=15,
            clock=lambda: now,
        )
        == 0
    )
    assert not finish_import_execution(
        import_session_factory,
        identity=identity,
        references=(_successful_reference(repository_id),),
    )

    with import_session_factory() as session:
        terminal_job = session.get_one(ImportJob, import_id)
        terminal_execution = session.get_one(ImportExecution, identity.execution_id)
        assert terminal_job.state == "import_failed"
        assert terminal_job.error_category == "provider_unavailable"
        assert terminal_job.active_baseline_execution_id == original_baseline_id
        assert terminal_execution.state == "failed"
        assert terminal_execution.finished_at == now
        assert (
            session.scalar(
                text(
                    "SELECT count(*) FROM import_source_references "
                    "WHERE execution_id = :execution_id"
                ),
                {"execution_id": identity.execution_id},
            )
            == 0
        )


def test_import_watchdog_settings_and_named_tasks_are_bounded_and_do_not_redispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    celery_app = importlib.import_module("verboflex.worker.celery_app")
    import_tasks = importlib.import_module("verboflex.worker.import_tasks")
    settings = Settings(
        import_soft_time_limit_seconds=10,
        import_hard_time_limit_seconds=20,
        import_watchdog_grace_seconds=8,
        import_watchdog_interval_seconds=2,
    )
    application = celery_app.create_celery_app(settings)

    assert settings.import_max_terminalization_seconds == 30
    assert application.conf.task_annotations["verboflex.import.run"] == {
        "acks_late": True,
        "reject_on_worker_lost": True,
        "soft_time_limit": 10,
        "time_limit": 20,
    }
    assert application.conf.beat_schedule["import-stale-execution-watchdog"] == {
        "task": "verboflex.import.reconcile_stale_jobs",
        "schedule": 2.0,
    }
    assert application.conf.beat_max_loop_interval == 2
    application.close()

    calls: list[tuple[object, int, int]] = []

    def reconcile(
        factory: object,
        *,
        hard_time_limit_seconds: int,
        watchdog_grace_seconds: int,
    ) -> int:
        calls.append((factory, hard_time_limit_seconds, watchdog_grace_seconds))
        return 3

    factory = object()
    monkeypatch.setattr(import_tasks, "get_settings", lambda: settings)
    monkeypatch.setattr(import_tasks, "SessionFactory", factory)
    monkeypatch.setattr(import_tasks, "reconcile_stale_imports", reconcile)
    assert import_tasks.reconcile_stale_import_jobs.run() == 3
    assert calls == [(factory, 20, 8)]
    assert import_tasks.reconcile_stale_import_jobs.name == (
        "verboflex.import.reconcile_stale_jobs"
    )

    for overrides in (
        {"import_soft_time_limit_seconds": 0},
        {"import_hard_time_limit_seconds": 0},
        {"import_watchdog_grace_seconds": 0},
        {"import_watchdog_interval_seconds": 0},
        {"import_soft_time_limit_seconds": 20, "import_hard_time_limit_seconds": 20},
        {"import_watchdog_grace_seconds": 5, "import_watchdog_interval_seconds": 5},
        {
            "import_hard_time_limit_seconds": 280,
            "import_watchdog_grace_seconds": 15,
            "import_watchdog_interval_seconds": 10,
        },
    ):
        with pytest.raises(ValidationError):
            Settings(**overrides)


def _movement_input(
    repository_side: str,
    *,
    repository_id: UUID | None = None,
    active_commit_hash: str,
    proposed_commit_hash: str,
) -> object:
    return import_job_service.SourceMovementInput(
        repository_side=repository_side,
        repository_id=repository_id or uuid4(),
        workspace="import-team",
        repository_slug=f"{repository_side}-repository",
        active_commit_hash=active_commit_hash,
        proposed_commit_hash=proposed_commit_hash,
    )


def test_classify_direct_equal_short_circuits_without_provider_reads() -> None:
    commit_hash = "1" * 40
    source = _movement_input(
        "direct",
        active_commit_hash=commit_hash,
        proposed_commit_hash=commit_hash,
    )
    adapter = SourceMovementAdapterSpy(ancestries={})

    with Session() as session:
        classification = asyncio.run(
            import_job_service.classify_source_movement(
                session,
                sources=(source,),
                adapter=adapter,
            )
        )

    assert classification.movement == "equal"
    assert classification.rewrite_candidate is None
    assert [side.relation for side in classification.sides] == ["equal"]
    assert adapter.requests == []


def test_classify_direct_fast_forward_requires_exact_complete_ancestry() -> None:
    previous = "2" * 40
    proposed = "3" * 40
    source = _movement_input(
        "direct",
        active_commit_hash=previous,
        proposed_commit_hash=proposed,
    )
    adapter = SourceMovementAdapterSpy(
        ancestries={
            ("direct-repository", previous, proposed): BitbucketAncestry(
                old_commit_hash=previous,
                new_commit_hash=proposed,
                relation="descendant",
                complete=True,
            )
        }
    )

    with Session() as session:
        classification = asyncio.run(
            import_job_service.classify_source_movement(
                session,
                sources=(source,),
                adapter=adapter,
            )
        )

    assert classification.movement == "fast-forward"
    assert classification.rewrite_candidate is None
    assert [side.relation for side in classification.sides] == ["descendant"]
    assert adapter.requests == [("ancestry", "direct-repository", previous, proposed)]


def test_classify_separate_rewrite_is_one_ordered_mapping_candidate() -> None:
    keys_previous = "4" * 40
    keys_proposed = "5" * 40
    translations_previous = "6" * 40
    translations_proposed = "7" * 40
    keys_id = uuid4()
    translations_id = uuid4()
    sources = (
        _movement_input(
            "keys",
            repository_id=keys_id,
            active_commit_hash=keys_previous,
            proposed_commit_hash=keys_proposed,
        ),
        _movement_input(
            "translations",
            repository_id=translations_id,
            active_commit_hash=translations_previous,
            proposed_commit_hash=translations_proposed,
        ),
    )
    adapter = SourceMovementAdapterSpy(
        ancestries={
            ("keys-repository", keys_previous, keys_proposed): BitbucketAncestry(
                old_commit_hash=keys_previous,
                new_commit_hash=keys_proposed,
                relation="diverged",
                complete=True,
            ),
            (
                "translations-repository",
                translations_previous,
                translations_proposed,
            ): BitbucketAncestry(
                old_commit_hash=translations_previous,
                new_commit_hash=translations_proposed,
                relation="diverged",
                complete=True,
            ),
        },
        deltas={
            (
                "keys-repository",
                keys_previous,
                keys_proposed,
                "keys",
            ): BitbucketCommitDelta(
                old_commit_hash=keys_previous,
                new_commit_hash=keys_proposed,
                files=(
                    BitbucketFileDelta(
                        repository_side="keys",
                        ordinal=0,
                        change="added",
                        path="locales/messages.json",
                    ),
                ),
                complete=True,
            ),
            (
                "translations-repository",
                translations_previous,
                translations_proposed,
                "translations",
            ): BitbucketCommitDelta(
                old_commit_hash=translations_previous,
                new_commit_hash=translations_proposed,
                files=(
                    BitbucketFileDelta(
                        repository_side="translations",
                        ordinal=0,
                        change="removed",
                        path="locales/messages.json",
                    ),
                ),
                complete=True,
            ),
        },
    )

    with Session() as session:
        classification = asyncio.run(
            import_job_service.classify_source_movement(
                session,
                sources=sources,
                adapter=adapter,
            )
        )

    assert classification.movement == "review-required"
    candidate = classification.rewrite_candidate
    assert candidate is not None
    assert candidate.complete is True
    assert [side.repository_side for side in candidate.sides] == [
        "keys",
        "translations",
    ]
    assert [side.repository_id for side in candidate.sides] == [
        keys_id,
        translations_id,
    ]
    assert [side.relation for side in candidate.sides] == ["diverged", "diverged"]
    assert [
        (file.repository_side, file.ordinal, file.change, file.path) for file in candidate.files
    ] == [
        ("keys", 0, "added", "locales/messages.json"),
        ("translations", 0, "removed", "locales/messages.json"),
    ]
    assert adapter.requests == [
        ("ancestry", "keys-repository", keys_previous, keys_proposed),
        (
            "ancestry",
            "translations-repository",
            translations_previous,
            translations_proposed,
        ),
        ("diffstat", "keys-repository", keys_previous, keys_proposed),
        (
            "diffstat",
            "translations-repository",
            translations_previous,
            translations_proposed,
        ),
    ]


def test_classify_one_rewritten_separate_side_holds_the_whole_mapping() -> None:
    keys_commit = "8" * 40
    translations_previous = "9" * 40
    translations_proposed = "a" * 40
    sources = (
        _movement_input(
            "keys",
            active_commit_hash=keys_commit,
            proposed_commit_hash=keys_commit,
        ),
        _movement_input(
            "translations",
            active_commit_hash=translations_previous,
            proposed_commit_hash=translations_proposed,
        ),
    )
    adapter = SourceMovementAdapterSpy(
        ancestries={
            (
                "translations-repository",
                translations_previous,
                translations_proposed,
            ): BitbucketAncestry(
                old_commit_hash=translations_previous,
                new_commit_hash=translations_proposed,
                relation="diverged",
                complete=True,
            )
        },
        deltas={
            (
                "translations-repository",
                translations_previous,
                translations_proposed,
                "translations",
            ): BitbucketCommitDelta(
                old_commit_hash=translations_previous,
                new_commit_hash=translations_proposed,
                files=(),
                complete=True,
            )
        },
    )

    with Session() as session:
        classification = asyncio.run(
            import_job_service.classify_source_movement(
                session,
                sources=sources,
                adapter=adapter,
            )
        )

    assert classification.movement == "review-required"
    assert [side.relation for side in classification.sides] == ["equal", "diverged"]
    assert classification.rewrite_candidate is not None
    assert classification.rewrite_candidate.files == ()
    assert classification.rewrite_candidate.complete is True


def test_classify_separate_equal_and_descendant_is_fast_forward_without_delta() -> None:
    keys_commit = "b" * 40
    translations_previous = "c" * 40
    translations_proposed = "d" * 40
    sources = (
        _movement_input(
            "keys",
            active_commit_hash=keys_commit,
            proposed_commit_hash=keys_commit,
        ),
        _movement_input(
            "translations",
            active_commit_hash=translations_previous,
            proposed_commit_hash=translations_proposed,
        ),
    )
    adapter = SourceMovementAdapterSpy(
        ancestries={
            (
                "translations-repository",
                translations_previous,
                translations_proposed,
            ): BitbucketAncestry(
                old_commit_hash=translations_previous,
                new_commit_hash=translations_proposed,
                relation="descendant",
                complete=True,
            )
        }
    )

    with Session() as session:
        classification = asyncio.run(
            import_job_service.classify_source_movement(
                session,
                sources=sources,
                adapter=adapter,
            )
        )

    assert classification.movement == "fast-forward"
    assert classification.rewrite_candidate is None
    assert [side.relation for side in classification.sides] == [
        "equal",
        "descendant",
    ]
    assert all(request[0] != "diffstat" for request in adapter.requests)


@pytest.mark.parametrize(
    "boundary",
    [
        "ancestry_incomplete",
        "ancestry_mismatch",
        "delta_incomplete",
        "delta_mismatch",
        "delta_forged_side",
        "delta_bad_order",
    ],
)
def test_classify_incomplete_or_forged_comparison_has_no_confirmation_authority(
    boundary: str,
) -> None:
    previous = "e" * 40
    proposed = "f" * 40
    source = _movement_input(
        "direct",
        active_commit_hash=previous,
        proposed_commit_hash=proposed,
    )
    ancestry = BitbucketAncestry(
        old_commit_hash="0" * 40 if boundary == "ancestry_mismatch" else previous,
        new_commit_hash=proposed,
        relation="diverged",
        complete=boundary != "ancestry_incomplete",
    )
    delta = BitbucketCommitDelta(
        old_commit_hash="0" * 40 if boundary == "delta_mismatch" else previous,
        new_commit_hash=proposed,
        files=(
            BitbucketFileDelta(
                repository_side=("keys" if boundary == "delta_forged_side" else "direct"),
                ordinal=1 if boundary == "delta_bad_order" else 0,
                change="modified",
                path="locales/messages.json",
            ),
        ),
        complete=boundary != "delta_incomplete",
    )
    adapter = SourceMovementAdapterSpy(
        ancestries={("direct-repository", previous, proposed): ancestry},
        deltas={("direct-repository", previous, proposed, "direct"): delta},
    )

    with Session() as session, pytest.raises(BitbucketProviderReadError):
        asyncio.run(
            import_job_service.classify_source_movement(
                session,
                sources=(source,),
                adapter=adapter,
            )
        )


def test_classify_reuses_no_proposed_commit_between_manual_retry_calls() -> None:
    previous = "1" * 40
    first_proposed = "2" * 40
    retry_proposed = "3" * 40
    adapter = SourceMovementAdapterSpy(
        ancestries={
            ("direct-repository", previous, first_proposed): BitbucketAncestry(
                old_commit_hash=previous,
                new_commit_hash=first_proposed,
                relation="descendant",
                complete=True,
            ),
            ("direct-repository", previous, retry_proposed): BitbucketAncestry(
                old_commit_hash=previous,
                new_commit_hash=retry_proposed,
                relation="descendant",
                complete=True,
            ),
        }
    )

    with Session() as session:
        first = asyncio.run(
            import_job_service.classify_source_movement(
                session,
                sources=(
                    _movement_input(
                        "direct",
                        active_commit_hash=previous,
                        proposed_commit_hash=first_proposed,
                    ),
                ),
                adapter=adapter,
            )
        )
        retry = asyncio.run(
            import_job_service.classify_source_movement(
                session,
                sources=(
                    _movement_input(
                        "direct",
                        active_commit_hash=previous,
                        proposed_commit_hash=retry_proposed,
                    ),
                ),
                adapter=adapter,
            )
        )

    assert first.movement == retry.movement == "fast-forward"
    assert [request[3] for request in adapter.requests] == [
        first_proposed,
        retry_proposed,
    ]


@pytest.mark.parametrize(
    "roles",
    [(), ("translations", "keys"), ("keys",), ("direct", "direct")],
)
def test_classify_rejects_noncanonical_mapping_side_shape_before_provider_reads(
    roles: tuple[str, ...],
) -> None:
    adapter = SourceMovementAdapterSpy(ancestries={})
    sources = tuple(
        _movement_input(
            role,
            active_commit_hash="4" * 40,
            proposed_commit_hash="5" * 40,
        )
        for role in roles
    )

    with Session() as session, pytest.raises(BitbucketProviderReadError):
        asyncio.run(
            import_job_service.classify_source_movement(
                session,
                sources=sources,
                adapter=adapter,
            )
        )

    assert adapter.requests == []


def _complete_initial_direct_baseline(
    factory: sessionmaker[Session],
    *,
    product_id: UUID,
    mapping_id: UUID,
    repository_id: UUID,
    commit_hash: str,
) -> tuple[UUID, UUID]:
    record = import_job_service.start_or_refresh_import(
        factory(),
        product_id=product_id,
        mapping_id=mapping_id,
        enqueuer=lambda _import_id: None,
    )
    assert record.id is not None
    identity = import_job_service.start_import_execution(factory, import_id=record.id)
    assert identity is not None
    assert import_job_service.finish_import_execution(
        factory,
        identity=identity,
        references=(_successful_reference_at(repository_id, commit_hash=commit_hash),),
    )
    return record.id, identity.execution_id


def _rewrite_classification(
    *,
    sides: tuple[import_job_service.SourceMovementSideComparison, ...],
    files: tuple[BitbucketFileDelta, ...] = (),
    complete: bool = True,
) -> import_job_service.SourceMovementClassification:
    return import_job_service.SourceMovementClassification(
        movement="review-required",
        sides=sides,
        rewrite_candidate=import_job_service.SourceRewriteCandidate(
            sides=sides,
            files=files,
            complete=complete,
        ),
    )


def test_rewrite_proposal_persists_complete_zero_delta_without_moving_baseline(
    import_session_factory: sessionmaker[Session],
) -> None:
    product_id, revision_id, repository_id, mapping_id = _seed_published_direct_mapping(
        import_session_factory
    )
    old_commit = "1" * 40
    new_commit = "2" * 40
    import_id, baseline_execution_id = _complete_initial_direct_baseline(
        import_session_factory,
        product_id=product_id,
        mapping_id=mapping_id,
        repository_id=repository_id,
        commit_hash=old_commit,
    )
    refresh = import_job_service.start_or_refresh_import(
        import_session_factory(),
        product_id=product_id,
        mapping_id=mapping_id,
        enqueuer=lambda _import_id: None,
    )
    assert refresh.id == import_id
    identity = import_job_service.start_import_execution(
        import_session_factory,
        import_id=import_id,
    )
    assert identity is not None
    sides = (
        import_job_service.SourceMovementSideComparison(
            repository_side="direct",
            repository_id=repository_id,
            active_commit_hash=old_commit,
            proposed_commit_hash=new_commit,
            relation="diverged",
        ),
    )

    assert import_job_service.finish_import_execution(
        import_session_factory,
        identity=identity,
        references=(_successful_reference_at(repository_id, commit_hash=new_commit),),
        movement=_rewrite_classification(sides=sides),
    )

    with import_session_factory() as session:
        job = session.get_one(ImportJob, import_id)
        proposals = tuple(
            session.scalars(
                select(ImportRewriteProposal).where(
                    ImportRewriteProposal.import_job_id == import_id
                )
            )
        )
        assert job.active_baseline_execution_id == baseline_execution_id
        assert job.current_execution_id == identity.execution_id
        assert len(proposals) == 1
        proposal = proposals[0]
        assert proposal.product_id == product_id
        assert proposal.revision_id == revision_id
        assert proposal.revision_version == 7
        assert proposal.mapping_id == mapping_id
        assert proposal.topology == "direct"
        assert proposal.connection_generation == identity.connection_generation
        assert proposal.proposed_execution_id == identity.execution_id
        assert proposal.old_baseline_execution_id == baseline_execution_id
        assert proposal.direct_repository_id == repository_id
        assert proposal.direct_old_commit_hash == old_commit
        assert proposal.direct_new_commit_hash == new_commit
        assert proposal.keys_repository_id is None
        assert proposal.translations_repository_id is None
        assert proposal.complete is True
        assert proposal.status == "pending"
        assert len(proposal.digest) == 64
        assert (
            session.scalar(
                select(func.count())
                .select_from(ImportRewriteDelta)
                .where(ImportRewriteDelta.proposal_id == proposal.id)
            )
            == 0
        )


def test_rewrite_proposal_rejects_incomplete_evidence_and_retains_old_baseline(
    import_session_factory: sessionmaker[Session],
) -> None:
    product_id, _revision_id, repository_id, mapping_id = _seed_published_direct_mapping(
        import_session_factory
    )
    old_commit = "3" * 40
    new_commit = "4" * 40
    import_id, baseline_execution_id = _complete_initial_direct_baseline(
        import_session_factory,
        product_id=product_id,
        mapping_id=mapping_id,
        repository_id=repository_id,
        commit_hash=old_commit,
    )
    import_job_service.start_or_refresh_import(
        import_session_factory(),
        product_id=product_id,
        mapping_id=mapping_id,
        enqueuer=lambda _import_id: None,
    )
    identity = import_job_service.start_import_execution(
        import_session_factory,
        import_id=import_id,
    )
    assert identity is not None
    sides = (
        import_job_service.SourceMovementSideComparison(
            repository_side="direct",
            repository_id=repository_id,
            active_commit_hash=old_commit,
            proposed_commit_hash=new_commit,
            relation="diverged",
        ),
    )

    assert import_job_service.finish_import_execution(
        import_session_factory,
        identity=identity,
        references=(_successful_reference_at(repository_id, commit_hash=new_commit),),
        movement=_rewrite_classification(sides=sides, complete=False),
    )

    with import_session_factory() as session:
        job = session.get_one(ImportJob, import_id)
        assert job.state == "import_failed"
        assert job.active_baseline_execution_id == baseline_execution_id
        assert (
            session.scalar(
                select(func.count())
                .select_from(ImportRewriteProposal)
                .where(
                    ImportRewriteProposal.import_job_id == import_id,
                    ImportRewriteProposal.status == "pending",
                )
            )
            == 0
        )


def test_rewrite_proposal_persists_complete_ordered_separate_delta_atomically(
    import_session_factory: sessionmaker[Session],
) -> None:
    (
        product_id,
        revision_id,
        keys_repository_id,
        translations_repository_id,
        mapping_id,
    ) = _seed_published_separate_mapping(import_session_factory)
    initial = import_job_service.start_or_refresh_import(
        import_session_factory(),
        product_id=product_id,
        mapping_id=mapping_id,
        enqueuer=lambda _import_id: None,
    )
    assert initial.id is not None
    first = import_job_service.start_import_execution(
        import_session_factory,
        import_id=initial.id,
    )
    assert first is not None
    keys_old, keys_new = "5" * 40, "6" * 40
    translations_old, translations_new = "7" * 40, "8" * 40
    baseline_references = (
        ImportSourceReferenceRecord(
            position=0,
            repository_side="keys",
            repository_id=keys_repository_id,
            source_branch="main",
            commit_hash=keys_old,
            path="locales/keys.json",
            size_bytes=1,
            sha256="a" * 64,
        ),
        ImportSourceReferenceRecord(
            position=1,
            repository_side="translations",
            repository_id=translations_repository_id,
            source_branch="main",
            commit_hash=translations_old,
            path="locales/translations.json",
            size_bytes=1,
            sha256="b" * 64,
        ),
    )
    assert import_job_service.finish_import_execution(
        import_session_factory,
        identity=first,
        references=baseline_references,
    )
    import_job_service.start_or_refresh_import(
        import_session_factory(),
        product_id=product_id,
        mapping_id=mapping_id,
        enqueuer=lambda _import_id: None,
    )
    second = import_job_service.start_import_execution(
        import_session_factory,
        import_id=initial.id,
    )
    assert second is not None
    proposed_references = (
        replace(baseline_references[0], commit_hash=keys_new),
        replace(baseline_references[1], commit_hash=translations_new),
    )
    sides = (
        import_job_service.SourceMovementSideComparison(
            repository_side="keys",
            repository_id=keys_repository_id,
            active_commit_hash=keys_old,
            proposed_commit_hash=keys_new,
            relation="diverged",
        ),
        import_job_service.SourceMovementSideComparison(
            repository_side="translations",
            repository_id=translations_repository_id,
            active_commit_hash=translations_old,
            proposed_commit_hash=translations_new,
            relation="diverged",
        ),
    )
    files = (
        BitbucketFileDelta(
            repository_side="keys",
            ordinal=0,
            change="modified",
            path="locales/keys.json",
        ),
        BitbucketFileDelta(
            repository_side="translations",
            ordinal=0,
            change="removed",
            path="locales/translations.json",
        ),
    )

    assert import_job_service.finish_import_execution(
        import_session_factory,
        identity=second,
        references=proposed_references,
        movement=_rewrite_classification(sides=sides, files=files),
    )

    with import_session_factory() as session:
        proposal = session.scalar(
            select(ImportRewriteProposal).where(
                ImportRewriteProposal.import_job_id == initial.id,
                ImportRewriteProposal.status == "pending",
            )
        )
        assert proposal is not None
        assert proposal.product_id == product_id
        assert proposal.revision_id == revision_id
        assert proposal.keys_repository_id == keys_repository_id
        assert proposal.translations_repository_id == translations_repository_id
        deltas = tuple(
            session.scalars(
                select(ImportRewriteDelta)
                .where(ImportRewriteDelta.proposal_id == proposal.id)
                .order_by(ImportRewriteDelta.position)
            )
        )
        assert [
            (delta.position, delta.repository_side, delta.change, delta.path) for delta in deltas
        ] == [
            (0, "keys", "modified", "locales/keys.json"),
            (1, "translations", "removed", "locales/translations.json"),
        ]
