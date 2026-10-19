"""Administrator-only direct candidate-mapping HTTP contracts."""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Generator, Iterator, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from alembic.config import Config
from fastapi import HTTPException
from psycopg import connect, sql
from pydantic import SecretStr
from sqlalchemy import create_engine, delete, select, text
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from verboflex.api.v1.routes.admin_discovery import get_bitbucket_discovery_adapter
from verboflex.auth.access_tokens import issue_access_token
from verboflex.auth.passwords import hash_password
from verboflex.core.config import Settings, get_settings
from verboflex.db.session import get_db_session
from verboflex.integrations.bitbucket.client import BitbucketBranch
from verboflex.main import app
from verboflex.models.auth_session import AuthSession
from verboflex.models.import_job import ImportExecution, ImportJob
from verboflex.models.product import Product, ProductRevision
from verboflex.models.product_mapping import (
    ProductMappingAllowedTarget,
    ProductMappingRepositorySide,
    ProductRepositoryMapping,
)
from verboflex.models.repository import Repository
from verboflex.models.role import Role
from verboflex.models.translation import LocalizationScope, TranslationParseIssue
from verboflex.models.user import User

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ADMIN_DATABASE_URL = os.environ.get(
    "VERBOFLEX_TEST_POSTGRES_ADMIN_URL",
    "postgresql://postgres@127.0.0.1:55432/postgres",
)
SIGNING_SECRET = "0123456789abcdef" * 2


class BranchAdapter:
    """Exact live branch membership fixture."""

    def __init__(self, names: Sequence[str]) -> None:
        self.names = tuple(names)
        self.calls: list[tuple[str, str]] = []

    async def list_repository_branches(
        self,
        _session: Session,
        *,
        workspace: str,
        repository_slug: str,
    ) -> tuple[BitbucketBranch, ...]:
        self.calls.append((workspace, repository_slug))
        return tuple(
            BitbucketBranch(name=name, commit_hash=f"{index + 1:040x}")
            for index, name in enumerate(self.names)
        )


@pytest.fixture(scope="module")
def mapping_session_factory() -> Iterator[sessionmaker[Session]]:
    """Migrate one isolated PostgreSQL database for the mapping API."""
    database_name = f"verboflex_admin_mappings_{uuid4().hex}"
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
        engine.dispose()
        with connect(ADMIN_DATABASE_URL, autocommit=True) as admin_connection:
            admin_connection.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database_name))
            )


@pytest.fixture(autouse=True)
def clean_mapping_database(
    mapping_session_factory: sessionmaker[Session],
) -> Iterator[None]:
    """Keep mapping examples and authorities independent."""
    app.dependency_overrides.clear()
    with mapping_session_factory.begin() as session:
        session.execute(text("TRUNCATE products, repositories CASCADE"))
        session.execute(delete(AuthSession))
        session.execute(delete(User))
    yield
    app.dependency_overrides.clear()


def _settings() -> Settings:
    return Settings(jwt_secret_key=SecretStr(SIGNING_SECRET))


def _configure_dependencies(
    factory: sessionmaker[Session],
    adapter: BranchAdapter,
) -> None:
    def override_session() -> Generator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_settings] = _settings
    app.dependency_overrides[get_bitbucket_discovery_adapter] = lambda: adapter


def _create_authority(
    factory: sessionmaker[Session],
    *,
    email: str,
    roles: Sequence[str],
) -> str:
    user_id = uuid4()
    auth_session_id = uuid4()
    now = datetime.now(UTC)
    with factory.begin() as session:
        durable_roles = list(session.execute(select(Role).where(Role.name.in_(roles))).scalars())
        session.add(
            User(
                id=user_id,
                email=email,
                display_name=email.split("@", 1)[0].title(),
                hashed_password=hash_password("principal password phrase!"),
                is_active=True,
                must_change_password=False,
                roles=durable_roles,
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


def _seed_candidate(
    factory: sessionmaker[Session],
    *,
    product_id: UUID | None = None,
    candidate_version: int = 4,
) -> tuple[UUID, UUID, UUID]:
    durable_product_id = product_id or uuid4()
    active_id = uuid4()
    candidate_id = uuid4()
    with factory.begin() as session:
        product = Product(
            id=durable_product_id,
            display_name=f"Product {durable_product_id}",
            name_key=f"product {durable_product_id}",
            is_active=True,
        )
        session.add(product)
        session.flush()
        session.add_all(
            [
                ProductRevision(
                    id=active_id,
                    product_id=durable_product_id,
                    description="published",
                    version=3,
                    is_published=True,
                    published_at=datetime.now(UTC),
                ),
                ProductRevision(
                    id=candidate_id,
                    product_id=durable_product_id,
                    description="candidate",
                    version=candidate_version,
                    is_published=False,
                ),
            ]
        )
        session.flush()
        product.active_revision_id = active_id
        product.candidate_revision_id = candidate_id
    return durable_product_id, active_id, candidate_id


def _seed_repository(
    factory: sessionmaker[Session],
    *,
    repository_id: UUID | None = None,
) -> UUID:
    durable_id = repository_id or uuid4()
    with factory.begin() as session:
        session.add(
            Repository(
                id=durable_id,
                workspace="mobile-team",
                repository_slug=f"repo-{durable_id.hex}",
            )
        )
    return durable_id


def _active_snapshot(
    factory: sessionmaker[Session],
    *,
    product_id: UUID,
    active_id: UUID,
) -> tuple[Any, ...]:
    with factory() as session:
        product = session.get_one(Product, product_id)
        active = session.get_one(ProductRevision, active_id)
        return (
            product.active_revision_id,
            product.is_active,
            active.id,
            active.version,
            active.description,
            active.is_published,
            active.published_at,
            active.updated_at,
        )


def _mapping_path(product_id: UUID, mapping_id: UUID | None = None) -> str:
    collection = f"/api/v1/admin/products/{product_id}/candidate/mappings"
    return collection if mapping_id is None else f"{collection}/{mapping_id}"


def _revision_mapping_path(product_id: UUID, revision_id: UUID) -> str:
    return f"/api/v1/admin/products/{product_id}/revisions/{revision_id}/mappings"


async def _request(
    method: str,
    *,
    path: str,
    access_token: str | None,
    json_body: dict[str, object] | None = None,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    headers = {"Authorization": f"Bearer {access_token}"} if access_token is not None else None
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, headers=headers, json=json_body)


def _direct_payload(
    repository_id: UUID,
    *,
    expected_version: int = 4,
    source_branch: str = "main",
    allowed_targets: Sequence[str] = ("release/2", "release/1", "release/1"),
    default_target: str = "release/1",
) -> dict[str, object]:
    return {
        "topology": "direct",
        "repository_id": str(repository_id),
        "source_branch": source_branch,
        "allowed_target_branches": list(allowed_targets),
        "default_target_branch": default_target,
        "expected_candidate_version": expected_version,
    }


def _separate_payload(
    keys_repository_id: UUID,
    translations_repository_id: UUID,
    *,
    expected_version: int = 4,
    keys_branch: str = "keys/main",
    translations_branch: str = "translations/main",
    allowed_targets: Sequence[str] = ("release/1", "release/2"),
    default_target: str = "release/1",
) -> dict[str, object]:
    return {
        "topology": "separate",
        "sides": [
            {
                "role": "keys",
                "repository_id": str(keys_repository_id),
                "source_branch": keys_branch,
            },
            {
                "role": "translations",
                "repository_id": str(translations_repository_id),
                "source_branch": translations_branch,
            },
        ],
        "allowed_target_branches": list(allowed_targets),
        "default_target_branch": default_target,
        "expected_candidate_version": expected_version,
    }


def _persist_mapping(
    session: Session,
    *,
    mapping_id: UUID,
    revision_id: UUID,
    topology: str,
    primary_repository_id: UUID,
    primary_branch: str,
    translations_repository_id: UUID | None = None,
    translations_branch: str | None = None,
    targets: Sequence[str] = ("release/1",),
    default_target: str = "release/1",
) -> None:
    primary_role = "direct" if topology == "direct" else "keys"
    sides = [
        ProductMappingRepositorySide(
            role=primary_role,
            repository_id=primary_repository_id,
            source_branch=primary_branch,
        )
    ]
    if topology == "separate":
        assert translations_repository_id is not None
        assert translations_branch is not None
        sides.append(
            ProductMappingRepositorySide(
                role="translations",
                repository_id=translations_repository_id,
                source_branch=translations_branch,
            )
        )
    session.add(
        ProductRepositoryMapping(
            id=mapping_id,
            revision_id=revision_id,
            topology=topology,
            identity_key=f"fixture:{mapping_id}",
            sides=sides,
            allowed_targets=[
                ProductMappingAllowedTarget(
                    branch=target,
                    is_default=target == default_target,
                )
                for target in targets
            ],
        )
    )


def _seed_revision_read_graph(
    factory: sessionmaker[Session],
    *,
    include_candidate: bool,
) -> tuple[UUID, UUID, UUID | None, UUID, tuple[UUID, ...]]:
    """Persist active/candidate/stale mappings before publication guards engage."""
    product_id = uuid4()
    active_id = uuid4()
    candidate_id = uuid4() if include_candidate else None
    stale_id = uuid4()
    repository_ids = tuple(uuid4() for _ in range(4))
    mapping_ids = tuple(uuid4() for _ in range(3 if include_candidate else 1))
    now = datetime.now(UTC)
    with factory.begin() as session:
        product = Product(
            id=product_id,
            display_name=f"Revision read {product_id}",
            name_key=f"revision read {product_id}",
            is_active=False,
        )
        session.add(product)
        session.flush()
        active = ProductRevision(
            id=active_id,
            product_id=product_id,
            description="active revision",
            version=7,
            is_published=False,
        )
        stale = ProductRevision(
            id=stale_id,
            product_id=product_id,
            description="historical revision",
            version=3,
            is_published=False,
        )
        revisions = [active, stale]
        if candidate_id is not None:
            revisions.append(
                ProductRevision(
                    id=candidate_id,
                    product_id=product_id,
                    description="candidate revision",
                    version=11,
                    is_published=False,
                )
            )
        session.add_all(revisions)
        session.add_all(
            Repository(
                id=repository_id,
                workspace="revision-read-team",
                repository_slug=f"repo-{repository_id.hex}",
            )
            for repository_id in repository_ids
        )
        session.flush()
        _persist_mapping(
            session,
            mapping_id=mapping_ids[0],
            revision_id=active_id,
            topology="direct",
            primary_repository_id=repository_ids[0],
            primary_branch="active/main",
            targets=("active/release",),
            default_target="active/release",
        )
        if candidate_id is not None:
            _persist_mapping(
                session,
                mapping_id=mapping_ids[1],
                revision_id=candidate_id,
                topology="direct",
                primary_repository_id=repository_ids[1],
                primary_branch="candidate/a",
                targets=("candidate/release",),
                default_target="candidate/release",
            )
            _persist_mapping(
                session,
                mapping_id=mapping_ids[2],
                revision_id=candidate_id,
                topology="separate",
                primary_repository_id=repository_ids[2],
                primary_branch="candidate/keys",
                translations_repository_id=repository_ids[3],
                translations_branch="candidate/translations",
                targets=("candidate/release",),
                default_target="candidate/release",
            )
        session.flush()
        active.is_published = True
        active.published_at = now
        stale.is_published = True
        stale.published_at = now
        session.flush()
        product.active_revision_id = active_id
        product.candidate_revision_id = candidate_id
    return product_id, active_id, candidate_id, stale_id, mapping_ids


def _revision_graph_snapshot(
    factory: sessionmaker[Session],
    *,
    product_ids: Sequence[UUID],
) -> tuple[Any, ...]:
    """Capture every persisted pointer and revision-owned row touched by the read."""
    ordered_product_ids = tuple(sorted(product_ids))
    with factory() as session:
        revision_ids = tuple(
            session.scalars(
                select(ProductRevision.id)
                .where(ProductRevision.product_id.in_(ordered_product_ids))
                .order_by(ProductRevision.id)
            )
        )
        mapping_ids = tuple(
            session.scalars(
                select(ProductRepositoryMapping.id)
                .where(ProductRepositoryMapping.revision_id.in_(revision_ids))
                .order_by(ProductRepositoryMapping.id)
            )
        )
        return (
            tuple(
                session.execute(
                    select(
                        Product.id,
                        Product.active_revision_id,
                        Product.candidate_revision_id,
                        Product.is_active,
                        Product.updated_at,
                    )
                    .where(Product.id.in_(ordered_product_ids))
                    .order_by(Product.id)
                ).all()
            ),
            tuple(
                session.execute(
                    select(
                        ProductRevision.id,
                        ProductRevision.product_id,
                        ProductRevision.version,
                        ProductRevision.is_published,
                        ProductRevision.published_at,
                        ProductRevision.updated_at,
                    )
                    .where(ProductRevision.id.in_(revision_ids))
                    .order_by(ProductRevision.id)
                ).all()
            ),
            tuple(
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
                        ProductRepositoryMapping.created_at,
                        ProductRepositoryMapping.updated_at,
                    )
                    .where(ProductRepositoryMapping.id.in_(mapping_ids))
                    .order_by(ProductRepositoryMapping.id)
                ).all()
            ),
            tuple(
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
            ),
            tuple(
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
            ),
        )


def test_revision_mapping_read_is_owned_cursor_faithful_and_mutation_free(
    mapping_session_factory: sessionmaker[Session],
) -> None:
    """Active/candidate reads preserve graph state and reject every other revision."""
    active_only = _seed_revision_read_graph(
        mapping_session_factory,
        include_candidate=False,
    )
    candidate_graph = _seed_revision_read_graph(
        mapping_session_factory,
        include_candidate=True,
    )
    active_product_id, active_id, _no_candidate, stale_id, active_mapping_ids = active_only
    product_id, candidate_active_id, candidate_id, _candidate_stale, mapping_ids = candidate_graph
    assert candidate_id is not None
    adapter = BranchAdapter(())
    _configure_dependencies(mapping_session_factory, adapter)
    admin_token = _create_authority(
        mapping_session_factory,
        email="revision-reader@example.com",
        roles=("admin",),
    )
    ordinary_token = _create_authority(
        mapping_session_factory,
        email="revision-reader-denied@example.com",
        roles=("viewer",),
    )
    before = _revision_graph_snapshot(
        mapping_session_factory,
        product_ids=(active_product_id, product_id),
    )

    assert (
        asyncio.run(
            _request(
                "GET",
                path=_revision_mapping_path(active_product_id, active_id),
                access_token=None,
            )
        ).status_code
        == 401
    )
    assert (
        asyncio.run(
            _request(
                "GET",
                path=_revision_mapping_path(active_product_id, active_id),
                access_token=ordinary_token,
            )
        ).status_code
        == 403
    )

    active_response = asyncio.run(
        _request(
            "GET",
            path=_revision_mapping_path(active_product_id, active_id),
            access_token=admin_token,
        )
    )
    assert active_response.status_code == 200
    assert active_response.json() == {
        "items": [
            {
                "id": str(active_mapping_ids[0]),
                "topology": "direct",
                "primary_repository_id": active_response.json()["items"][0][
                    "primary_repository_id"
                ],
                "primary_source_branch": "active/main",
                "primary_localization_root": None,
                "code_source": None,
                "translations_localization_root": None,
                "translations_repository_id": None,
                "translations_source_branch": None,
                "allowed_target_branches": ["active/release"],
                "default_target_branch": "active/release",
                "selected_layout_candidate_id": None,
                "selected_layout_version": None,
                "candidate_version": 7,
            }
        ],
        "next_cursor": None,
    }

    first_page = asyncio.run(
        _request(
            "GET",
            path=_revision_mapping_path(product_id, candidate_id) + "?limit=1",
            access_token=admin_token,
        )
    )
    assert first_page.status_code == 200
    assert [item["id"] for item in first_page.json()["items"]] == [str(mapping_ids[1])]
    cursor = first_page.json()["next_cursor"]
    assert isinstance(cursor, str) and cursor
    second_page = asyncio.run(
        _request(
            "GET",
            path=_revision_mapping_path(product_id, candidate_id) + f"?limit=1&cursor={cursor}",
            access_token=admin_token,
        )
    )
    assert second_page.status_code == 200
    assert [item["id"] for item in second_page.json()["items"]] == [str(mapping_ids[2])]
    assert second_page.json()["next_cursor"] is None

    invalid_cursor = asyncio.run(
        _request(
            "GET",
            path=_revision_mapping_path(product_id, candidate_id) + "?cursor=not-a-cursor",
            access_token=admin_token,
        )
    )
    assert invalid_cursor.status_code == 422
    assert invalid_cursor.json() == {"detail": "Invalid cursor"}

    candidate_active = asyncio.run(
        _request(
            "GET",
            path=_revision_mapping_path(product_id, candidate_active_id),
            access_token=admin_token,
        )
    )
    assert candidate_active.status_code == 200
    assert [item["id"] for item in candidate_active.json()["items"]] == [str(mapping_ids[0])]

    for requested_product_id, requested_revision_id in (
        (product_id, active_id),
        (active_product_id, stale_id),
        (product_id, uuid4()),
    ):
        rejected = asyncio.run(
            _request(
                "GET",
                path=_revision_mapping_path(requested_product_id, requested_revision_id),
                access_token=admin_token,
            )
        )
        assert rejected.status_code == 404
        assert rejected.json() == {"detail": "Mapping revision unavailable"}

    assert adapter.calls == []
    assert (
        _revision_graph_snapshot(
            mapping_session_factory,
            product_ids=(active_product_id, product_id),
        )
        == before
    )


def test_localization_root_roundtrips_and_changes_candidate_authority(
    mapping_session_factory: sessionmaker[Session],
) -> None:
    product_id, active_id, _ = _seed_candidate(mapping_session_factory)
    repository_id = _seed_repository(mapping_session_factory)
    _configure_dependencies(
        mapping_session_factory, BranchAdapter(("main", "release/1", "release/2"))
    )
    token = _create_authority(mapping_session_factory, email="admin@example.com", roles=("admin",))
    before = _active_snapshot(mapping_session_factory, product_id=product_id, active_id=active_id)
    payload = {
        **_direct_payload(repository_id),
        "localization_root": "shared/src/commonMain/moko-resources",
    }
    created = asyncio.run(
        _request("POST", path=_mapping_path(product_id), access_token=token, json_body=payload)
    )
    assert created.status_code == 201
    assert created.json()["primary_localization_root"] == payload["localization_root"]
    mapping_id = UUID(created.json()["id"])
    payload.update(expected_candidate_version=5, localization_root="translations")
    updated = asyncio.run(
        _request(
            "PATCH",
            path=_mapping_path(product_id, mapping_id),
            access_token=token,
            json_body=payload,
        )
    )
    assert updated.status_code == 200
    assert updated.json()["candidate_version"] == 6
    assert updated.json()["primary_localization_root"] == "translations"
    assert updated.json()["selected_layout_candidate_id"] is None
    listed = asyncio.run(_request("GET", path=_mapping_path(product_id), access_token=token))
    assert listed.json()["items"][0]["primary_localization_root"] == "translations"
    assert (
        _active_snapshot(mapping_session_factory, product_id=product_id, active_id=active_id)
        == before
    )


@pytest.mark.parametrize("root", ["", "/absolute", "../escape", "a/../b", "a\\b", "a/%2e%2e/b"])
def test_invalid_localization_root_is_rejected_before_discovery(
    mapping_session_factory: sessionmaker[Session],
    root: str,
) -> None:
    product_id, _, _ = _seed_candidate(mapping_session_factory)
    repository_id = _seed_repository(mapping_session_factory)
    adapter = BranchAdapter(("main", "release/1", "release/2"))
    _configure_dependencies(mapping_session_factory, adapter)
    token = _create_authority(mapping_session_factory, email="admin@example.com", roles=("admin",))
    response = asyncio.run(
        _request(
            "POST",
            path=_mapping_path(product_id),
            access_token=token,
            json_body={**_direct_payload(repository_id), "localization_root": root},
        )
    )
    assert response.status_code == 422
    assert not adapter.calls


def test_direct_create_update_conflicts_and_noop_preserve_active_revision(
    mapping_session_factory: sessionmaker[Session],
) -> None:
    """Create/update are candidate-versioned, normalized, and active-safe."""
    product_id, active_id, _candidate_id = _seed_candidate(mapping_session_factory)
    repository_id = _seed_repository(mapping_session_factory)
    adapter = BranchAdapter(("main", "release/1", "release/2", "release/3"))
    _configure_dependencies(mapping_session_factory, adapter)
    admin_token = _create_authority(
        mapping_session_factory,
        email="admin@example.com",
        roles=("admin",),
    )
    before_active = _active_snapshot(
        mapping_session_factory,
        product_id=product_id,
        active_id=active_id,
    )

    created = asyncio.run(
        _request(
            "POST",
            path=_mapping_path(product_id),
            access_token=admin_token,
            json_body=_direct_payload(repository_id),
        )
    )
    assert created.status_code == 201
    body = created.json()
    assert body == {
        "id": body["id"],
        "topology": "direct",
        "primary_repository_id": str(repository_id),
        "primary_source_branch": "main",
        "primary_localization_root": None,
        "code_source": None,
        "translations_localization_root": None,
        "translations_repository_id": None,
        "translations_source_branch": None,
        "allowed_target_branches": ["release/1", "release/2"],
        "default_target_branch": "release/1",
        "selected_layout_candidate_id": None,
        "selected_layout_version": None,
        "candidate_version": 5,
    }
    mapping_id = UUID(body["id"])
    with mapping_session_factory() as session:
        persisted = session.get_one(ProductRepositoryMapping, mapping_id)
        timestamps = (persisted.created_at, persisted.updated_at)

    duplicate = asyncio.run(
        _request(
            "POST",
            path=_mapping_path(product_id),
            access_token=admin_token,
            json_body=_direct_payload(repository_id, expected_version=5),
        )
    )
    assert duplicate.status_code == 409
    assert duplicate.json() == {
        "detail": "Mapping unavailable",
        "field": "mapping_identity",
    }

    identical = asyncio.run(
        _request(
            "PATCH",
            path=_mapping_path(product_id, mapping_id),
            access_token=admin_token,
            json_body=_direct_payload(
                repository_id,
                expected_version=5,
                allowed_targets=("release/1", "release/2", "release/1"),
            ),
        )
    )
    assert identical.status_code == 200
    assert identical.json()["candidate_version"] == 5
    with mapping_session_factory() as session:
        persisted = session.get_one(ProductRepositoryMapping, mapping_id)
        assert (persisted.created_at, persisted.updated_at) == timestamps

    changed = asyncio.run(
        _request(
            "PATCH",
            path=_mapping_path(product_id, mapping_id),
            access_token=admin_token,
            json_body=_direct_payload(
                repository_id,
                expected_version=5,
                allowed_targets=("release/1", "release/3"),
                default_target="release/3",
            ),
        )
    )
    assert changed.status_code == 200
    assert changed.json()["candidate_version"] == 6
    assert changed.json()["allowed_target_branches"] == ["release/1", "release/3"]
    assert changed.json()["default_target_branch"] == "release/3"

    cases = [
        (
            _direct_payload(repository_id, expected_version=5),
            409,
            {"detail": "Mapping candidate conflict", "field": "candidate_version"},
        ),
        (
            _direct_payload(
                repository_id,
                expected_version=6,
                source_branch="missing",
            ),
            409,
            {"detail": "Source branch unavailable", "field": "source_branch"},
        ),
        (
            _direct_payload(
                repository_id,
                expected_version=6,
                allowed_targets=("release/missing",),
                default_target="release/missing",
            ),
            409,
            {
                "detail": "Target branch unavailable",
                "field": "allowed_target_branches",
            },
        ),
        (
            _direct_payload(
                repository_id,
                expected_version=6,
                allowed_targets=("release/1",),
                default_target="release/2",
            ),
            422,
            {"detail": "Invalid mapping input"},
        ),
    ]
    for payload, expected_status, expected_body in cases:
        response = asyncio.run(
            _request(
                "PATCH",
                path=_mapping_path(product_id, mapping_id),
                access_token=admin_token,
                json_body=payload,
            )
        )
        assert response.status_code == expected_status
        assert response.json() == expected_body

    assert (
        _active_snapshot(
            mapping_session_factory,
            product_id=product_id,
            active_id=active_id,
        )
        == before_active
    )


def test_mapping_collection_uses_exact_tuple_order_and_stable_opaque_pages(
    mapping_session_factory: sessionmaker[Session],
) -> None:
    """Every collision component and the final UUID tie remain page-stable."""
    product_id, _active_id, candidate_id = _seed_candidate(mapping_session_factory)
    adapter = BranchAdapter(("main", "release/1"))
    _configure_dependencies(mapping_session_factory, adapter)
    admin_token = _create_authority(
        mapping_session_factory,
        email="order-admin@example.com",
        roles=("admin",),
    )
    repositories = [
        _seed_repository(
            mapping_session_factory,
            repository_id=UUID(f"00000000-0000-0000-0000-{index:012x}"),
        )
        for index in range(1, 7)
    ]
    ids = [UUID(f"10000000-0000-0000-0000-{index:012x}") for index in range(1, 11)]
    with mapping_session_factory.begin() as session:
        # Direct sorts before Separate, then primary repository and C-collated branch.
        _persist_mapping(
            session,
            mapping_id=ids[1],
            revision_id=candidate_id,
            topology="direct",
            primary_repository_id=repositories[1],
            primary_branch="a",
            targets=("release/1", "release/2"),
        )
        _persist_mapping(
            session,
            mapping_id=ids[0],
            revision_id=candidate_id,
            topology="direct",
            primary_repository_id=repositories[1],
            primary_branch="Z",
        )
        # Same complete pre-UUID tuple, distinct target configuration: UUID breaks tie.
        _persist_mapping(
            session,
            mapping_id=ids[3],
            revision_id=candidate_id,
            topology="direct",
            primary_repository_id=repositories[2],
            primary_branch="same",
            targets=("release/1", "release/2"),
        )
        _persist_mapping(
            session,
            mapping_id=ids[2],
            revision_id=candidate_id,
            topology="direct",
            primary_repository_id=repositories[2],
            primary_branch="same",
            targets=("release/1",),
        )
        # Separate fixtures tie through topology, primary, and then translation fields.
        _persist_mapping(
            session,
            mapping_id=ids[7],
            revision_id=candidate_id,
            topology="separate",
            primary_repository_id=repositories[3],
            primary_branch="keys",
            translations_repository_id=repositories[5],
            translations_branch="b",
        )
        _persist_mapping(
            session,
            mapping_id=ids[6],
            revision_id=candidate_id,
            topology="separate",
            primary_repository_id=repositories[3],
            primary_branch="keys",
            translations_repository_id=repositories[5],
            translations_branch="A",
        )
        _persist_mapping(
            session,
            mapping_id=ids[5],
            revision_id=candidate_id,
            topology="separate",
            primary_repository_id=repositories[3],
            primary_branch="keys",
            translations_repository_id=repositories[4],
            translations_branch="translations",
        )
        _persist_mapping(
            session,
            mapping_id=ids[4],
            revision_id=candidate_id,
            topology="separate",
            primary_repository_id=repositories[3],
            primary_branch="Keys",
            translations_repository_id=repositories[4],
            translations_branch="translations",
        )

    expected_ids = [ids[index] for index in (0, 1, 2, 3, 4, 5, 6, 7)]
    seen: list[UUID] = []
    cursor: str | None = None
    while True:
        suffix = "?limit=2" + (f"&cursor={cursor}" if cursor is not None else "")
        response = asyncio.run(
            _request(
                "GET",
                path=_mapping_path(product_id) + suffix,
                access_token=admin_token,
            )
        )
        assert response.status_code == 200
        body = response.json()
        seen.extend(UUID(item["id"]) for item in body["items"])
        cursor = body["next_cursor"]
        if cursor is None:
            break

    assert seen == expected_ids
    assert len(seen) == len(set(seen))
    assert (
        asyncio.run(
            _request(
                "GET",
                path=_mapping_path(product_id) + "?cursor=not-a-cursor",
                access_token=admin_token,
            )
        ).status_code
        == 422
    )

    other_product, _other_active, _other_candidate = _seed_candidate(mapping_session_factory)
    first_page = asyncio.run(
        _request(
            "GET",
            path=_mapping_path(product_id) + "?limit=1",
            access_token=admin_token,
        )
    ).json()
    assert (
        asyncio.run(
            _request(
                "GET",
                path=_mapping_path(other_product) + f"?cursor={first_page['next_cursor']}",
                access_token=admin_token,
            )
        ).status_code
        == 422
    )


def test_separate_mapping_api_is_closed_versioned_and_topology_safe(
    mapping_session_factory: sessionmaker[Session],
) -> None:
    """Separate requires Keys/Translations and preserves mapping/active identity."""
    product_id, active_id, _candidate_id = _seed_candidate(mapping_session_factory)
    keys_repository_id = _seed_repository(mapping_session_factory)
    translations_repository_id = _seed_repository(mapping_session_factory)
    adapter = BranchAdapter(("main", "keys/main", "translations/main", "release/1", "release/2"))
    _configure_dependencies(mapping_session_factory, adapter)
    admin_token = _create_authority(
        mapping_session_factory,
        email="separate-admin@example.com",
        roles=("admin",),
    )
    before_active = _active_snapshot(
        mapping_session_factory,
        product_id=product_id,
        active_id=active_id,
    )

    direct = asyncio.run(
        _request(
            "POST",
            path=_mapping_path(product_id),
            access_token=admin_token,
            json_body=_direct_payload(keys_repository_id),
        )
    )
    assert direct.status_code == 201
    mapping_id = UUID(direct.json()["id"])
    with mapping_session_factory.begin() as session:
        persisted = session.get_one(ProductRepositoryMapping, mapping_id)
        persisted.selected_layout_candidate_id = uuid4()
        persisted.selected_layout_version = 3

    changed = asyncio.run(
        _request(
            "PATCH",
            path=_mapping_path(product_id, mapping_id),
            access_token=admin_token,
            json_body=_separate_payload(
                keys_repository_id,
                translations_repository_id,
                expected_version=5,
            ),
        )
    )
    assert changed.status_code == 200
    assert changed.json() == {
        "id": str(mapping_id),
        "topology": "separate",
        "primary_repository_id": str(keys_repository_id),
        "primary_source_branch": "keys/main",
        "primary_localization_root": None,
        "code_source": None,
        "translations_localization_root": None,
        "translations_repository_id": str(translations_repository_id),
        "translations_source_branch": "translations/main",
        "allowed_target_branches": ["release/1", "release/2"],
        "default_target_branch": "release/1",
        "selected_layout_candidate_id": None,
        "selected_layout_version": None,
        "candidate_version": 6,
    }
    assert (
        _active_snapshot(
            mapping_session_factory,
            product_id=product_id,
            active_id=active_id,
        )
        == before_active
    )

    for field, expected_field in (
        ("keys_branch", "keys_source_branch"),
        ("translations_branch", "translations_source_branch"),
    ):
        payload = _separate_payload(
            keys_repository_id,
            translations_repository_id,
            expected_version=6,
            **{field: "Missing"},
        )
        conflict = asyncio.run(
            _request(
                "PATCH",
                path=_mapping_path(product_id, mapping_id),
                access_token=admin_token,
                json_body=payload,
            )
        )
        assert conflict.status_code == 409
        assert conflict.json() == {
            "detail": "Source branch unavailable",
            "field": expected_field,
        }


@pytest.mark.parametrize("side_shape", ["missing", "duplicate", "extra"])
def test_separate_mapping_api_rejects_missing_duplicate_or_extra_roles(
    mapping_session_factory: sessionmaker[Session],
    side_shape: str,
) -> None:
    """The closed payload accepts exactly one Keys and one Translations side."""
    product_id, active_id, _candidate_id = _seed_candidate(mapping_session_factory)
    keys_repository_id = _seed_repository(mapping_session_factory)
    translations_repository_id = _seed_repository(mapping_session_factory)
    adapter = BranchAdapter(("keys/main", "translations/main", "release/1", "release/2"))
    _configure_dependencies(mapping_session_factory, adapter)
    admin_token = _create_authority(
        mapping_session_factory,
        email=f"side-{side_shape}@example.com",
        roles=("admin",),
    )
    before_active = _active_snapshot(
        mapping_session_factory,
        product_id=product_id,
        active_id=active_id,
    )
    payload = _separate_payload(keys_repository_id, translations_repository_id)
    sides = list(payload["sides"])
    if side_shape == "missing":
        sides.pop()
    elif side_shape == "duplicate":
        sides[1] = {**sides[1], "role": "keys"}
    else:
        sides.append(
            {
                "role": "keys",
                "repository_id": str(uuid4()),
                "source_branch": "other",
            }
        )
    payload["sides"] = sides

    response = asyncio.run(
        _request(
            "POST",
            path=_mapping_path(product_id),
            access_token=admin_token,
            json_body=payload,
        )
    )

    assert response.status_code == 422
    assert adapter.calls == []
    with mapping_session_factory() as session:
        assert session.scalar(select(ProductRepositoryMapping.id)) is None
    assert (
        _active_snapshot(
            mapping_session_factory,
            product_id=product_id,
            active_id=active_id,
        )
        == before_active
    )


def test_mapping_collection_is_empty_default_50_and_maximum_100(
    mapping_session_factory: sessionmaker[Session],
) -> None:
    """Potentially large mapping collections are always bounded."""
    empty_product, _active, _candidate = _seed_candidate(mapping_session_factory)
    adapter = BranchAdapter(("main", "release/1"))
    _configure_dependencies(mapping_session_factory, adapter)
    admin_token = _create_authority(
        mapping_session_factory,
        email="page-admin@example.com",
        roles=("admin",),
    )
    empty = asyncio.run(
        _request(
            "GET",
            path=_mapping_path(empty_product),
            access_token=admin_token,
        )
    )
    assert empty.status_code == 200
    assert empty.json() == {"items": [], "next_cursor": None}

    product_id, _active_id, candidate_id = _seed_candidate(mapping_session_factory)
    repository_id = _seed_repository(mapping_session_factory)
    with mapping_session_factory.begin() as session:
        for index in range(101):
            _persist_mapping(
                session,
                mapping_id=UUID(f"20000000-0000-0000-0000-{index:012x}"),
                revision_id=candidate_id,
                topology="direct",
                primary_repository_id=repository_id,
                primary_branch=f"branch-{index:03d}",
            )

    default_page = asyncio.run(
        _request(
            "GET",
            path=_mapping_path(product_id),
            access_token=admin_token,
        )
    )
    assert default_page.status_code == 200
    assert len(default_page.json()["items"]) == 50
    assert default_page.json()["next_cursor"] is not None

    maximum_page = asyncio.run(
        _request(
            "GET",
            path=_mapping_path(product_id) + "?limit=100",
            access_token=admin_token,
        )
    )
    assert maximum_page.status_code == 200
    assert len(maximum_page.json()["items"]) == 100
    assert maximum_page.json()["next_cursor"] is not None
    assert (
        asyncio.run(
            _request(
                "GET",
                path=_mapping_path(product_id) + "?limit=101",
                access_token=admin_token,
            )
        ).status_code
        == 422
    )


@pytest.mark.parametrize(
    "forbidden_field",
    [
        "format",
        "layout",
        "glob",
        "path",
        "file_list",
        "locale_template",
        "discovery",
        "is_active",
        "enabled",
    ],
)
def test_mapping_requests_are_admin_guarded_and_reject_manual_controls(
    mapping_session_factory: sessionmaker[Session],
    forbidden_field: str,
) -> None:
    """Closed transport input cannot mint lifecycle or manual layout authority."""
    product_id, active_id, _candidate_id = _seed_candidate(mapping_session_factory)
    repository_id = _seed_repository(mapping_session_factory)
    adapter = BranchAdapter(("main", "release/1"))
    _configure_dependencies(mapping_session_factory, adapter)
    user_token = _create_authority(
        mapping_session_factory,
        email=f"user-{forbidden_field}@example.com",
        roles=("product_manager_reviewer",),
    )
    admin_token = _create_authority(
        mapping_session_factory,
        email=f"admin-{forbidden_field}@example.com",
        roles=("admin",),
    )
    before_active = _active_snapshot(
        mapping_session_factory,
        product_id=product_id,
        active_id=active_id,
    )

    assert (
        asyncio.run(
            _request(
                "POST",
                path=_mapping_path(product_id),
                access_token=None,
                json_body=_direct_payload(repository_id),
            )
        ).status_code
        == 401
    )
    assert (
        asyncio.run(
            _request(
                "POST",
                path=_mapping_path(product_id),
                access_token=user_token,
                json_body=_direct_payload(repository_id),
            )
        ).status_code
        == 403
    )
    payload = _direct_payload(repository_id)
    payload[forbidden_field] = "manual"
    closed = asyncio.run(
        _request(
            "POST",
            path=_mapping_path(product_id),
            access_token=admin_token,
            json_body=payload,
        )
    )
    assert closed.status_code == 422
    with mapping_session_factory() as session:
        assert session.scalar(select(ProductRepositoryMapping.id)) is None
    assert (
        _active_snapshot(
            mapping_session_factory,
            product_id=product_id,
            active_id=active_id,
        )
        == before_active
    )


def test_route_table_and_openapi_expose_no_mapping_delete_operation(
    mapping_session_factory: sessionmaker[Session],
) -> None:
    """Phase 2 mapping lifecycle is candidate-owned and has no delete route."""
    product_id, _active_id, _candidate_id = _seed_candidate(mapping_session_factory)
    adapter = BranchAdapter(("main", "release/1"))
    _configure_dependencies(mapping_session_factory, adapter)
    admin_token = _create_authority(
        mapping_session_factory,
        email="contract-admin@example.com",
        roles=("admin",),
    )
    mapping_id = uuid4()
    assert (
        asyncio.run(
            _request(
                "DELETE",
                path=_mapping_path(product_id, mapping_id),
                access_token=admin_token,
            )
        ).status_code
        == 405
    )

    openapi = app.openapi()
    collection_path = "/api/v1/admin/products/{product_id}/candidate/mappings"
    detail_path = collection_path + "/{mapping_id}"
    assert set(openapi["paths"][collection_path]) == {"get", "post"}
    assert set(openapi["paths"][detail_path]) == {"patch"}
    operations = {
        operation["operationId"]
        for path in (collection_path, detail_path)
        for operation in openapi["paths"][path].values()
    }
    assert operations == {
        "list_admin_candidate_mappings",
        "create_admin_candidate_mapping",
        "update_admin_candidate_mapping",
    }
    assert all("delete" not in operation.casefold() for operation in operations)


def test_mapping_transport_projects_unavailable_resources_and_dependencies(
    mapping_session_factory: sessionmaker[Session],
) -> None:
    """Missing candidate resources are 404 and unavailable discovery is 503."""
    repository_id = _seed_repository(mapping_session_factory)
    adapter = BranchAdapter(("main", "release/1"))
    _configure_dependencies(mapping_session_factory, adapter)
    admin_token = _create_authority(
        mapping_session_factory,
        email="unavailable-admin@example.com",
        roles=("admin",),
    )
    missing_product = uuid4()
    for method, path in (
        ("GET", _mapping_path(missing_product)),
        ("POST", _mapping_path(missing_product)),
        ("PATCH", _mapping_path(missing_product, uuid4())),
    ):
        response = asyncio.run(
            _request(
                method,
                path=path,
                access_token=admin_token,
                json_body=(
                    None
                    if method == "GET"
                    else _direct_payload(
                        repository_id,
                        allowed_targets=("release/1",),
                    )
                ),
            )
        )
        assert response.status_code == 404
        assert response.json() == {"detail": "Mapping candidate unavailable"}

    product_id, _active_id, _candidate_id = _seed_candidate(mapping_session_factory)
    app.dependency_overrides[get_bitbucket_discovery_adapter] = lambda: None
    for method, path in (
        ("POST", _mapping_path(product_id)),
        ("PATCH", _mapping_path(product_id, uuid4())),
    ):
        response = asyncio.run(
            _request(
                method,
                path=path,
                access_token=admin_token,
                json_body=_direct_payload(repository_id),
            )
        )
        assert response.status_code == 503
        assert response.json() == {"detail": "Mapping branch discovery unavailable"}


def test_mapping_error_projection_is_closed_and_reraises_unknown_failures() -> None:
    """Only named domain errors cross the mapping transport boundary."""
    from verboflex.api.v1.routes import admin_mappings
    from verboflex.services.mappings import InvalidMappingInput, MappingNotFound

    for error, expected_status, expected_detail in (
        (MappingNotFound("missing"), 404, "Mapping candidate unavailable"),
        (InvalidMappingInput("invalid"), 422, "Invalid mapping input"),
    ):
        with pytest.raises(HTTPException) as raised:
            admin_mappings._raise_mapping_error(error)
        assert raised.value.status_code == expected_status
        assert raised.value.detail == expected_detail

    unexpected = RuntimeError("unexpected")
    with pytest.raises(RuntimeError) as raised:
        admin_mappings._raise_mapping_error(unexpected)
    assert raised.value is unexpected


def _seed_parser_failure_outcomes(
    factory: sessionmaker[Session],
) -> tuple[UUID, UUID, UUID]:
    """Persist one retained-dataset failure and one first-import failure."""
    now = datetime.now(UTC)
    product_id = uuid4()
    revision_id = uuid4()
    keys_repository_id = uuid4()
    translations_repository_id = uuid4()
    direct_repository_id = uuid4()
    retained_mapping_id = uuid4()
    first_mapping_id = uuid4()
    retained_import_id = uuid4()
    first_import_id = uuid4()
    baseline_execution_id = uuid4()
    retained_failure_execution_id = uuid4()
    first_failure_execution_id = uuid4()

    with factory.begin() as session:
        product = Product(
            id=product_id,
            display_name=f"Parser outcomes {product_id}",
            name_key=f"parser outcomes {product_id}",
            is_active=True,
        )
        revision = ProductRevision(
            id=revision_id,
            product_id=product_id,
            description="published parser outcomes",
            version=1,
            is_published=False,
        )
        session.add(product)
        session.flush()
        session.add(revision)
        session.add_all(
            [
                Repository(
                    id=keys_repository_id,
                    workspace="parser-team",
                    repository_slug=f"keys-{keys_repository_id.hex}",
                ),
                Repository(
                    id=translations_repository_id,
                    workspace="parser-team",
                    repository_slug=f"translations-{translations_repository_id.hex}",
                ),
                Repository(
                    id=direct_repository_id,
                    workspace="parser-team",
                    repository_slug=f"direct-{direct_repository_id.hex}",
                ),
            ]
        )
        session.flush()
        session.add_all(
            [
                ProductRepositoryMapping(
                    id=retained_mapping_id,
                    revision_id=revision_id,
                    topology="separate",
                    identity_key="a-retained-parser-dataset",
                    base_language="en",
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
                ),
                ProductRepositoryMapping(
                    id=first_mapping_id,
                    revision_id=revision_id,
                    topology="direct",
                    identity_key="b-first-parser-failure",
                    base_language="en",
                    sides=[
                        ProductMappingRepositorySide(
                            role="direct",
                            repository_id=direct_repository_id,
                            source_branch="main",
                        )
                    ],
                    allowed_targets=[ProductMappingAllowedTarget(branch="main", is_default=True)],
                ),
            ]
        )
        session.flush()
        revision.is_published = True
        revision.published_at = now
        session.flush()
        product.active_revision_id = revision_id

    with factory.begin() as session:
        session.add_all(
            [
                ImportJob(
                    id=retained_import_id,
                    product_id=product_id,
                    revision_id=revision_id,
                    mapping_id=retained_mapping_id,
                    topology="separate",
                    state="current",
                    current_execution_id=baseline_execution_id,
                    active_baseline_execution_id=baseline_execution_id,
                    retry_count=0,
                    error_category=None,
                    error_message=None,
                    latest_execution_at=now,
                ),
                ImportJob(
                    id=first_import_id,
                    product_id=product_id,
                    revision_id=revision_id,
                    mapping_id=first_mapping_id,
                    topology="direct",
                    state="running",
                    current_execution_id=first_failure_execution_id,
                    active_baseline_execution_id=None,
                    retry_count=0,
                    error_category=None,
                    error_message=None,
                    latest_execution_at=now,
                ),
            ]
        )
        session.flush()
        session.add_all(
            [
                ImportExecution(
                    id=baseline_execution_id,
                    import_job_id=retained_import_id,
                    sequence=1,
                    state="succeeded",
                    connection_generation=0,
                    started_at=now - timedelta(minutes=2),
                    finished_at=now - timedelta(minutes=1),
                ),
                ImportExecution(
                    id=first_failure_execution_id,
                    import_job_id=first_import_id,
                    sequence=1,
                    state="running",
                    connection_generation=0,
                    started_at=now,
                    finished_at=None,
                ),
            ]
        )
        session.flush()
        session.add(
            LocalizationScope(
                id=uuid4(),
                product_id=product_id,
                mapping_identity_key="a-retained-parser-dataset",
                current_revision_id=revision_id,
                current_mapping_id=retained_mapping_id,
                active_import_job_id=retained_import_id,
                active_execution_id=baseline_execution_id,
                dataset_version=1,
            )
        )
        session.flush()
        retained_job = session.get_one(ImportJob, retained_import_id)
        retained_job.state = "running"
        retained_job.current_execution_id = retained_failure_execution_id
        retained_job.retry_count = 1
        retained_job.error_category = None
        retained_job.error_message = None
        session.add(
            ImportExecution(
                id=retained_failure_execution_id,
                import_job_id=retained_import_id,
                sequence=2,
                state="running",
                connection_generation=0,
                started_at=now,
                finished_at=None,
            )
        )
        session.flush()
        issue_rows = (
            (0, "translations", "translations/z.json", "malformed_file", 7, 3),
            (1, "keys", "keys/provider-second.json", "duplicate_key", 2, None),
            (2, "translations", "translations/a.json", "unsupported_structure", None, None),
            (3, "keys", "keys/provider-fourth.json", "ambiguous_structure", 4, 8),
            (4, "translations", "translations/b.json", "base_language_required", 1, 1),
        )
        for position, repository_side, path, issue_code, line, column in issue_rows:
            session.add(
                TranslationParseIssue(
                    import_execution_id=retained_failure_execution_id,
                    position=position,
                    import_job_id=retained_import_id,
                    repository_side=repository_side,
                    path=path,
                    issue_code=issue_code,
                    message=(
                        "<script>provider body and parser exception must remain private</script>"
                    ),
                    line=line,
                    column=column,
                )
            )
        session.add(
            TranslationParseIssue(
                import_execution_id=first_failure_execution_id,
                position=0,
                import_job_id=first_import_id,
                repository_side="direct",
                path="locales/messages.json",
                issue_code="malformed_file",
                message="raw source excerpt: secret-canary",
                line=None,
                column=None,
            )
        )
        session.flush()
        for import_id, execution_id, message in (
            (
                retained_import_id,
                retained_failure_execution_id,
                "The last successful baseline is unchanged.",
            ),
            (
                first_import_id,
                first_failure_execution_id,
                "No import baseline was created.",
            ),
        ):
            job = session.get_one(ImportJob, import_id)
            execution = session.get_one(ImportExecution, execution_id)
            job.state = "import_failed"
            job.error_category = "bounded_failure"
            job.error_message = message
            execution.state = "failed"
            execution.finished_at = now

    return product_id, retained_import_id, first_import_id


def test_parser_failure_api_projects_retained_dataset_and_safe_ordered_issues(
    mapping_session_factory: sessionmaker[Session],
) -> None:
    """Current scope authority distinguishes retained data from a first failure."""
    product_id, retained_import_id, first_import_id = _seed_parser_failure_outcomes(
        mapping_session_factory
    )
    _configure_dependencies(mapping_session_factory, BranchAdapter(()))
    admin_token = _create_authority(
        mapping_session_factory,
        email="parser-outcome-admin@example.com",
        roles=("admin",),
    )
    ordinary_token = _create_authority(
        mapping_session_factory,
        email="parser-outcome-viewer@example.com",
        roles=("viewer",),
    )

    retained_path = f"/api/v1/admin/products/{product_id}/imports/{retained_import_id}"
    assert asyncio.run(_request("GET", path=retained_path, access_token=None)).status_code == 401
    assert (
        asyncio.run(_request("GET", path=retained_path, access_token=ordinary_token)).status_code
        == 403
    )

    retained = asyncio.run(_request("GET", path=retained_path, access_token=admin_token))
    assert retained.status_code == 200
    retained_body = retained.json()
    assert retained_body["state"] == "may_be_stale"
    assert retained_body["dataset_status"] == "retained"
    assert retained_body["parser_issue_remaining_count"] == 0
    assert retained_body["parser_issues"] == [
        {
            "issue_code": "duplicate_key",
            "repository_side": "keys",
            "path": "keys/provider-second.json",
            "line": 2,
            "column": None,
            "message_key": "import.parser.duplicate_key",
        },
        {
            "issue_code": "ambiguous_structure",
            "repository_side": "keys",
            "path": "keys/provider-fourth.json",
            "line": 4,
            "column": 8,
            "message_key": "import.parser.ambiguous_structure",
        },
        {
            "issue_code": "malformed_file",
            "repository_side": "translations",
            "path": "translations/z.json",
            "line": 7,
            "column": 3,
            "message_key": "import.parser.malformed_file",
        },
        {
            "issue_code": "unsupported_structure",
            "repository_side": "translations",
            "path": "translations/a.json",
            "line": None,
            "column": None,
            "message_key": "import.parser.unsupported_structure",
        },
        {
            "issue_code": "base_language_required",
            "repository_side": "translations",
            "path": "translations/b.json",
            "line": 1,
            "column": 1,
            "message_key": "import.parser.base_language_required",
        },
    ]
    serialized = json.dumps(retained_body).casefold()
    for forbidden in (
        "secret-canary",
        "<script>",
        "provider body",
        "parser exception",
        "raw source",
        "source_excerpt",
        "exception",
    ):
        assert forbidden not in serialized

    first = asyncio.run(
        _request(
            "GET",
            path=f"/api/v1/admin/products/{product_id}/imports/{first_import_id}",
            access_token=admin_token,
        )
    )
    assert first.status_code == 200
    first_body = first.json()
    assert first_body["state"] == "import_failed"
    assert first_body["dataset_status"] == "not_created"
    assert first_body["parser_issue_remaining_count"] == 0
    assert [issue["repository_side"] for issue in first_body["parser_issues"]] == ["direct"]


def test_code_source_configuration_is_versioned_and_invalidates_preview(mapping_session_factory):
    product_id, _active_id, _candidate_id = _seed_candidate(mapping_session_factory)
    keys_repo = _seed_repository(mapping_session_factory)
    translations_repo = _seed_repository(mapping_session_factory)
    _configure_dependencies(
        mapping_session_factory,
        BranchAdapter(("keys/main", "translations/main", "release/1", "release/2")),
    )
    token = _create_authority(
        mapping_session_factory, email="code-admin@example.com", roles=("admin",)
    )
    payload = _separate_payload(keys_repo, translations_repo)
    payload["code_source"] = {
        "resource_roots": ["Res.strings"],
        "declaration_symbols": ["demo.Keys.*"],
    }
    created = asyncio.run(
        _request("POST", path=_mapping_path(product_id), access_token=token, json_body=payload)
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["code_source"]["declaration_symbols"] == ["demo.Keys.*"]
    mapping_id = UUID(body["id"])
    with mapping_session_factory.begin() as session:
        mapping = session.get_one(ProductRepositoryMapping, mapping_id)
        assert mapping.code_source["resource_roots"] == ["Res.strings"]
        mapping.selected_layout_candidate_id = uuid4()
        mapping.selected_layout_version = 1
    payload["expected_candidate_version"] = body["candidate_version"]
    payload["code_source"] = {"resource_roots": ["Words.strings"]}
    changed = asyncio.run(
        _request(
            "PATCH",
            path=_mapping_path(product_id, mapping_id),
            access_token=token,
            json_body=payload,
        )
    )
    assert changed.status_code == 200
    assert changed.json()["candidate_version"] == body["candidate_version"] + 1
    assert changed.json()["selected_layout_candidate_id"] is None
    payload["expected_candidate_version"] = changed.json()["candidate_version"]
    unchanged = asyncio.run(
        _request(
            "PATCH",
            path=_mapping_path(product_id, mapping_id),
            access_token=token,
            json_body=payload,
        )
    )
    assert unchanged.json()["candidate_version"] == changed.json()["candidate_version"]
    payload["code_source"] = {"resource_roots": ["Res.strings"], "execute": "malicious"}
    invalid = asyncio.run(
        _request(
            "PATCH",
            path=_mapping_path(product_id, mapping_id),
            access_token=token,
            json_body=payload,
        )
    )
    assert invalid.status_code == 422
