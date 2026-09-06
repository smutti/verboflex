"""Administrator-only product candidate and collection HTTP contracts."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import unicodedata
from collections.abc import Generator, Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from alembic.config import Config
from psycopg import connect, sql
from pydantic import SecretStr
from sqlalchemy import create_engine, delete, event, func, select, text
from sqlalchemy.orm import Session, selectinload, sessionmaker
from sqlalchemy.sql import Executable

from alembic import command
from verboflex.api.v1.routes import admin_products as admin_product_routes
from verboflex.auth.access_tokens import issue_access_token
from verboflex.auth.passwords import hash_password
from verboflex.core.config import Settings, get_settings
from verboflex.db.session import get_db_session
from verboflex.main import app
from verboflex.models.auth_session import AuthSession
from verboflex.models.import_job import ImportExecution, ImportJob
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
from verboflex.services import publication as publication_service
from verboflex.services.products import list_products, normalize_product_name

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ADMIN_DATABASE_URL = os.environ.get(
    "VERBOFLEX_TEST_POSTGRES_ADMIN_URL",
    "postgresql://postgres@127.0.0.1:55432/postgres",
)
SIGNING_SECRET = "0123456789abcdef" * 2
ADMIN_PRODUCTS_PATH = "/api/v1/admin/products"


@pytest.fixture(scope="module")
def product_session_factory() -> Iterator[sessionmaker[Session]]:
    """Migrate one isolated PostgreSQL database for the focused product API."""
    database_name = f"verboflex_admin_products_{uuid4().hex}"
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
def clean_product_database(product_session_factory: sessionmaker[Session]) -> Iterator[None]:
    """Keep products and bearer principals independent across examples."""
    app.dependency_overrides.clear()
    with product_session_factory.begin() as session:
        session.execute(text("TRUNCATE products CASCADE"))
        session.execute(delete(AuthSession))
        session.execute(delete(User))
    yield
    app.dependency_overrides.clear()
    with product_session_factory.begin() as session:
        session.execute(text("TRUNCATE products CASCADE"))
        session.execute(delete(AuthSession))
        session.execute(delete(User))


def admin_settings() -> Settings:
    """Return deterministic signing settings independent from ambient secrets."""
    return Settings(jwt_secret_key=SecretStr(SIGNING_SECRET))


def configure_dependencies(factory: sessionmaker[Session]) -> None:
    """Wire principal and route sessions to the isolated database."""

    def override_session() -> Generator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_settings] = admin_settings


def create_authority(
    factory: sessionmaker[Session],
    *,
    email: str,
    roles: Sequence[str],
) -> tuple[UUID, str]:
    """Persist one current principal and return its ordinary bearer token."""
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
    return user_id, issue_access_token(
        user_id=user_id,
        session_id=auth_session_id,
        token_version=0,
        purpose="access",
        settings=admin_settings(),
        now=now,
    )


async def product_request(
    method: str,
    *,
    access_token: str | None,
    path: str = ADMIN_PRODUCTS_PATH,
    json_body: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    """Call the registered ASGI surface without bypassing dependencies."""
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    request_headers = dict(headers or {})
    if access_token is not None:
        request_headers["Authorization"] = f"Bearer {access_token}"
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(
            method,
            path,
            headers=request_headers or None,
            json=json_body,
        )


def create_payload(
    name: str = "Mobile Suite",
    description: str | None = "Mobile translations",
) -> dict[str, object]:
    return {"name": name, "description": description}


def _product_graph(factory: sessionmaker[Session]) -> tuple[object, ...]:
    """Capture every product and revision field affected by Task 3 mutations."""
    with factory() as session:
        products = tuple(
            session.execute(
                select(
                    Product.id,
                    Product.display_name,
                    Product.name_key,
                    Product.is_active,
                    Product.active_revision_id,
                    Product.candidate_revision_id,
                ).order_by(Product.id)
            ).all()
        )
        revisions = tuple(
            session.execute(
                select(
                    ProductRevision.id,
                    ProductRevision.product_id,
                    ProductRevision.display_name,
                    ProductRevision.name_key,
                    ProductRevision.description,
                    ProductRevision.version,
                    ProductRevision.is_published,
                    ProductRevision.published_at,
                ).order_by(ProductRevision.id)
            ).all()
        )
    return products, revisions


def _a01_key(name: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", name).split()).casefold()


def _cursor_from_json(payload: object, *, compact: bool) -> str:
    separators = (",", ":") if compact else None
    encoded = json.dumps(payload, separators=separators).encode()
    return base64.urlsafe_b64encode(encoded).rstrip(b"=").decode("ascii")


def test_admin_create_and_detail_return_closed_active_and_candidate_summaries(
    product_session_factory: sessionmaker[Session],
) -> None:
    """Create one stable product without inventing a publication shortcut."""
    _admin_id, admin_token = create_authority(
        product_session_factory,
        email="admin@example.com",
        roles=("admin",),
    )
    configure_dependencies(product_session_factory)

    created = asyncio.run(
        product_request(
            "POST",
            access_token=admin_token,
            json_body=create_payload(),
        )
    )

    assert created.status_code == 201
    body = created.json()
    assert body == {
        "id": body["id"],
        "name": "Mobile Suite",
        "is_active": False,
        "affected_mapping_count": 0,
        "active_revision": None,
        "candidate_revision": {
            "id": body["candidate_revision"]["id"],
            "version": 1,
            "name": "Mobile Suite",
            "description": "Mobile translations",
            "is_published": False,
        },
    }
    product_id = UUID(body["id"])
    candidate_id = UUID(body["candidate_revision"]["id"])

    detail = asyncio.run(
        product_request(
            "GET",
            access_token=admin_token,
            path=f"{ADMIN_PRODUCTS_PATH}/{product_id}",
        )
    )
    assert detail.status_code == 200
    assert detail.json() == body

    with product_session_factory() as session:
        product = session.get_one(Product, product_id)
        candidate = session.get_one(ProductRevision, candidate_id)
        assert product.active_revision_id is None
        assert product.candidate_revision_id == candidate.id
        assert candidate.is_published is False

    product_paths = {
        path for path in app.openapi()["paths"] if path.startswith(ADMIN_PRODUCTS_PATH)
    }
    revision_mappings_path = (
        f"{ADMIN_PRODUCTS_PATH}/{{product_id}}/revisions/{{revision_id}}/mappings"
    )
    assert product_paths == {
        ADMIN_PRODUCTS_PATH,
        f"{ADMIN_PRODUCTS_PATH}/{{product_id}}",
        f"{ADMIN_PRODUCTS_PATH}/{{product_id}}/deactivate",
        f"{ADMIN_PRODUCTS_PATH}/{{product_id}}/publish",
        f"{ADMIN_PRODUCTS_PATH}/{{product_id}}/reactivate",
        f"{ADMIN_PRODUCTS_PATH}/{{product_id}}/candidate/mappings",
        f"{ADMIN_PRODUCTS_PATH}/{{product_id}}/candidate/mappings/{{mapping_id}}",
        f"{ADMIN_PRODUCTS_PATH}/{{product_id}}/candidate/mappings/{{mapping_id}}/preview-jobs",
        f"{ADMIN_PRODUCTS_PATH}/{{product_id}}/published/mapping-imports",
        f"{ADMIN_PRODUCTS_PATH}/{{product_id}}/published/mappings/{{mapping_id}}/imports",
        f"{ADMIN_PRODUCTS_PATH}/{{product_id}}/imports/{{import_id}}",
        f"{ADMIN_PRODUCTS_PATH}/{{product_id}}/imports/{{import_id}}/duplicates",
        (
            f"{ADMIN_PRODUCTS_PATH}/{{product_id}}/published/mappings/{{mapping_id}}"
            "/imports/{import_id}/rewrite-comparison"
        ),
        (
            f"{ADMIN_PRODUCTS_PATH}/{{product_id}}/published/mappings/{{mapping_id}}"
            "/imports/{import_id}/rewrite-confirmation"
        ),
        f"{revision_mappings_path}/{{mapping_id}}/revalidation-preview-jobs",
        revision_mappings_path,
        f"{ADMIN_PRODUCTS_PATH}/{{product_id}}/revisions/{{revision_id}}/reactivation-eligibility",
    }
    assert set(app.openapi()["paths"][revision_mappings_path]) == {"get"}
    delete_operation = app.openapi()["paths"][f"{ADMIN_PRODUCTS_PATH}/{{product_id}}"]["delete"]
    assert delete_operation["operationId"] == "delete_admin_product"
    assert delete_operation["security"] == [{"OAuth2PasswordBearer": []}]
    assert set(delete_operation["responses"]) == {"204", "401", "403", "404", "409", "422"}
    assert "post" not in app.openapi()["paths"][f"{ADMIN_PRODUCTS_PATH}/{{product_id}}"]


def test_every_product_route_reuses_bearer_admin_authority_and_denials_do_not_mutate(
    product_session_factory: sessionmaker[Session],
) -> None:
    """Unauthenticated and non-admin calls fail before any product mutation."""
    _admin_id, admin_token = create_authority(
        product_session_factory,
        email="admin@example.com",
        roles=("admin",),
    )
    _viewer_id, viewer_token = create_authority(
        product_session_factory,
        email="viewer@example.com",
        roles=("viewer",),
    )
    configure_dependencies(product_session_factory)

    created = asyncio.run(
        product_request(
            "POST",
            access_token=admin_token,
            json_body=create_payload(name="Guarded Product"),
        )
    )
    assert created.status_code == 201
    product_id = created.json()["id"]
    before = _product_graph(product_session_factory)
    calls: tuple[tuple[str, str, dict[str, object] | None], ...] = (
        ("GET", ADMIN_PRODUCTS_PATH, None),
        ("POST", ADMIN_PRODUCTS_PATH, create_payload(name="Forbidden Product")),
        ("GET", f"{ADMIN_PRODUCTS_PATH}/{product_id}", None),
        (
            "PATCH",
            f"{ADMIN_PRODUCTS_PATH}/{product_id}",
            {
                "name": "Forbidden Rename",
                "description": None,
                "expected_candidate_version": 1,
            },
        ),
    )
    for token, expected_status in ((None, 401), (viewer_token, 403)):
        for method, path, payload in calls:
            response = asyncio.run(
                product_request(
                    method,
                    access_token=token,
                    path=path,
                    json_body=payload,
                )
            )
            assert response.status_code == expected_status
            assert _product_graph(product_session_factory) == before


def test_expected_version_conflicts_duplicate_name_and_identical_save_are_atomic(
    product_session_factory: sessionmaker[Session],
) -> None:
    """No-op, stale, and duplicate submissions preserve both revision graphs."""
    _admin_id, admin_token = create_authority(
        product_session_factory,
        email="admin@example.com",
        roles=("admin",),
    )
    configure_dependencies(product_session_factory)
    first = asyncio.run(
        product_request(
            "POST",
            access_token=admin_token,
            json_body=create_payload(name="Alpha Product", description="first"),
        )
    )
    second = asyncio.run(
        product_request(
            "POST",
            access_token=admin_token,
            json_body=create_payload(name="Beta Product", description="second"),
        )
    )
    assert first.status_code == second.status_code == 201
    first_id = first.json()["id"]
    candidate_before = first.json()["candidate_revision"]

    duplicate_create = asyncio.run(
        product_request(
            "POST",
            access_token=admin_token,
            json_body=create_payload(name="  beta\tproduct ", description="duplicate"),
        )
    )
    assert duplicate_create.status_code == 409
    assert duplicate_create.json() == {
        "detail": "Product name is unavailable",
        "field": "name",
    }

    invalid_name = asyncio.run(
        product_request(
            "POST",
            access_token=admin_token,
            json_body=create_payload(name=" \t ", description=None),
        )
    )
    assert invalid_name.status_code == 422
    assert invalid_name.json() == {"detail": "Invalid product input"}

    missing_version = asyncio.run(
        product_request(
            "PATCH",
            access_token=admin_token,
            path=f"{ADMIN_PRODUCTS_PATH}/{first_id}",
            json_body={"name": "Alpha Product", "description": "first"},
        )
    )
    assert missing_version.status_code == 422

    no_op = asyncio.run(
        product_request(
            "PATCH",
            access_token=admin_token,
            path=f"{ADMIN_PRODUCTS_PATH}/{first_id}",
            json_body={
                "name": "  Alpha\tProduct  ",
                "description": "first",
                "expected_candidate_version": 1,
            },
        )
    )
    assert no_op.status_code == 200
    assert no_op.json()["candidate_revision"] == candidate_before

    updated = asyncio.run(
        product_request(
            "PATCH",
            access_token=admin_token,
            path=f"{ADMIN_PRODUCTS_PATH}/{first_id}",
            json_body={
                "name": "Alpha Product Renamed",
                "description": "candidate edit",
                "expected_candidate_version": 1,
            },
        )
    )
    assert updated.status_code == 200
    assert updated.json()["candidate_revision"] == {
        "id": candidate_before["id"],
        "version": 2,
        "name": "Alpha Product Renamed",
        "description": "candidate edit",
        "is_published": False,
    }

    before_conflicts = _product_graph(product_session_factory)
    stale = asyncio.run(
        product_request(
            "PATCH",
            access_token=admin_token,
            path=f"{ADMIN_PRODUCTS_PATH}/{first_id}",
            json_body={
                "name": "Stale Writer",
                "description": "must not persist",
                "expected_candidate_version": 1,
            },
        )
    )
    assert stale.status_code == 409
    assert stale.json() == {"detail": "Product candidate conflict"}
    assert _product_graph(product_session_factory) == before_conflicts

    duplicate = asyncio.run(
        product_request(
            "PATCH",
            access_token=admin_token,
            path=f"{ADMIN_PRODUCTS_PATH}/{first_id}",
            json_body={
                "name": "  beta\tproduct ",
                "description": "must not persist",
                "expected_candidate_version": 2,
            },
        )
    )
    assert duplicate.status_code == 409
    assert duplicate.json() == {
        "detail": "Product name is unavailable",
        "field": "name",
    }
    assert _product_graph(product_session_factory) == before_conflicts

    unknown_id = uuid4()
    unknown_detail = asyncio.run(
        product_request(
            "GET",
            access_token=admin_token,
            path=f"{ADMIN_PRODUCTS_PATH}/{unknown_id}",
        )
    )
    unknown_update = asyncio.run(
        product_request(
            "PATCH",
            access_token=admin_token,
            path=f"{ADMIN_PRODUCTS_PATH}/{unknown_id}",
            json_body={
                "name": "Unknown",
                "description": None,
                "expected_candidate_version": 1,
            },
        )
    )
    assert unknown_detail.status_code == unknown_update.status_code == 404
    assert unknown_detail.json() == unknown_update.json() == {"detail": "Product unavailable"}
    assert _product_graph(product_session_factory) == before_conflicts


def test_racing_duplicate_create_has_one_winner_and_one_field_scoped_conflict(
    product_session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Database uniqueness closes the race after both requests pass their precheck."""
    _admin_id, admin_token = create_authority(
        product_session_factory,
        email="admin@example.com",
        roles=("admin",),
    )
    configure_dependencies(product_session_factory)
    barrier = Barrier(2)
    original_scalar = Session.scalar

    def synchronized_scalar(
        self: Session,
        statement: Executable,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        result = original_scalar(self, statement, *args, **kwargs)
        if "products.name_key" in str(statement):
            barrier.wait(timeout=5)
        return result

    monkeypatch.setattr(Session, "scalar", synchronized_scalar)

    def create_duplicate() -> httpx.Response:
        return asyncio.run(
            product_request(
                "POST",
                access_token=admin_token,
                json_body=create_payload(name="Concurrent Product"),
            )
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda _index: create_duplicate(), range(2)))

    assert sorted(response.status_code for response in responses) == [201, 409]
    conflict = next(response for response in responses if response.status_code == 409)
    assert conflict.json() == {"detail": "Product name is unavailable", "field": "name"}
    with product_session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Product)) == 1


def _seed_active_product(
    factory: sessionmaker[Session],
    *,
    name: str,
    description: str | None,
) -> tuple[UUID, UUID]:
    product_id = uuid4()
    revision_id = uuid4()
    with factory.begin() as session:
        product = Product(
            id=product_id,
            display_name=name,
            name_key=_a01_key(name),
            is_active=True,
        )
        session.add(product)
        session.flush()
        session.add(
            ProductRevision(
                id=revision_id,
                product_id=product_id,
                description=description,
                version=1,
                is_published=True,
                published_at=datetime.now(UTC),
            )
        )
        session.flush()
        product.active_revision_id = revision_id
        session.flush()
    return product_id, revision_id


def _seed_published_mapping_graph(
    factory: sessionmaker[Session],
    *,
    confirmed_by: UUID,
    name: str = "Published Graph",
) -> tuple[UUID, UUID]:
    """Seed one immutable active graph containing both mapping topologies."""
    now = datetime.now(UTC)
    product_id = uuid4()
    revision_id = uuid4()
    direct_repository_id = uuid4()
    keys_repository_id = uuid4()
    translations_repository_id = uuid4()
    with factory.begin() as session:
        product = Product(
            id=product_id,
            display_name=name,
            name_key=_a01_key(name),
            is_active=True,
        )
        revision = ProductRevision(
            id=revision_id,
            product_id=product_id,
            display_name=name,
            name_key=_a01_key(name),
            description="published graph description",
            version=4,
            is_published=False,
        )
        session.add(product)
        session.flush()
        session.add(revision)
        session.add_all(
            [
                Repository(
                    id=direct_repository_id,
                    workspace="clone-team",
                    repository_slug=f"direct-{direct_repository_id.hex[:12]}",
                ),
                Repository(
                    id=keys_repository_id,
                    workspace="clone-team",
                    repository_slug=f"keys-{keys_repository_id.hex[:12]}",
                ),
                Repository(
                    id=translations_repository_id,
                    workspace="clone-team",
                    repository_slug=f"translations-{translations_repository_id.hex[:12]}",
                ),
            ]
        )
        session.flush()
        product.candidate_revision_id = revision_id
        session.flush()

        direct_mapping = ProductRepositoryMapping(
            revision_id=revision_id,
            topology="direct",
            identity_key=f'["direct","{direct_repository_id}","main"]',
            selected_layout_candidate_id=uuid4(),
            selected_layout_version=3,
            sides=[
                ProductMappingRepositorySide(
                    role="direct",
                    repository_id=direct_repository_id,
                    source_branch="main",
                )
            ],
            allowed_targets=[
                ProductMappingAllowedTarget(branch="release/1", is_default=True),
                ProductMappingAllowedTarget(branch="release/2", is_default=False),
            ],
        )
        separate_mapping = ProductRepositoryMapping(
            revision_id=revision_id,
            topology="separate",
            identity_key=(
                f'["separate","{keys_repository_id}","main",'
                f'"{translations_repository_id}","translations"]'
            ),
            selected_layout_candidate_id=uuid4(),
            selected_layout_version=8,
            sides=[
                ProductMappingRepositorySide(
                    role="keys",
                    repository_id=keys_repository_id,
                    source_branch="main",
                ),
                ProductMappingRepositorySide(
                    role="translations",
                    repository_id=translations_repository_id,
                    source_branch="translations",
                ),
            ],
            allowed_targets=[ProductMappingAllowedTarget(branch="release/l10n", is_default=True)],
        )
        session.add_all([direct_mapping, separate_mapping])
        session.flush()

        for index, mapping in enumerate((direct_mapping, separate_mapping), start=1):
            digest = hashlib.sha256(f"{product_id}:{index}".encode()).hexdigest()
            preview_job = PreviewJob(
                id=uuid4(),
                input_digest=digest,
                attempt=1,
                state="succeeded",
                product_id=product_id,
                candidate_revision_id=revision_id,
                candidate_revision_version=revision.version,
                mapping_id=mapping.id,
                topology=mapping.topology,
                connection_generation=12,
                detector_version="clone-fixture-v1",
                layout_identity="one-format-layout",
                repository_sides=[
                    {
                        "role": side.role,
                        "repository_id": str(side.repository_id),
                        "source_branch": side.source_branch,
                        "commit": f"{index}" * 40,
                    }
                    for side in mapping.sides
                ],
                result={"digest": digest, "layout_candidates": []},
                started_at=now,
                finished_at=now,
            )
            session.add(preview_job)
            mapping.confirmed_preview_job_id = preview_job.id
            mapping.confirmed_preview_digest = digest
            mapping.preview_confirmed_by = confirmed_by
            mapping.preview_confirmed_at = now
        session.flush()

        revision.is_published = True
        revision.published_at = now
        session.flush()
        product.active_revision_id = revision_id
        product.candidate_revision_id = None
        session.flush()
    return product_id, revision_id


def _revision_mapping_graph(
    session: Session,
    *,
    revision_id: UUID,
) -> tuple[ProductRepositoryMapping, ...]:
    return tuple(
        session.execute(
            select(ProductRepositoryMapping)
            .options(
                selectinload(ProductRepositoryMapping.sides),
                selectinload(ProductRepositoryMapping.allowed_targets),
            )
            .where(ProductRepositoryMapping.revision_id == revision_id)
            .order_by(ProductRepositoryMapping.identity_key)
        ).scalars()
    )


def _seed_import_state(
    session: Session,
    *,
    product_id: UUID,
    revision_id: UUID,
    mapping_id: UUID,
    failed: bool,
    has_baseline: bool,
) -> None:
    """Persist one logical import state without involving provider behavior."""
    job_id = uuid4()
    current_execution_id = uuid4()
    baseline_execution_id = uuid4() if has_baseline and failed else current_execution_id
    now = datetime.now(UTC)
    session.add(
        ImportJob(
            id=job_id,
            product_id=product_id,
            revision_id=revision_id,
            mapping_id=mapping_id,
            topology="direct",
            state="import_failed" if failed else "current",
            current_execution_id=current_execution_id,
            active_baseline_execution_id=(baseline_execution_id if has_baseline else None),
            retry_count=1 if failed else 0,
            error_category="provider_unavailable" if failed else None,
            error_message="Import provider unavailable" if failed else None,
            latest_execution_at=now,
        )
    )
    session.flush()
    if has_baseline and failed:
        session.add(
            ImportExecution(
                id=baseline_execution_id,
                import_job_id=job_id,
                sequence=1,
                state="succeeded",
                connection_generation=1,
                started_at=now,
                finished_at=now,
            )
        )
    session.add(
        ImportExecution(
            id=current_execution_id,
            import_job_id=job_id,
            sequence=2 if has_baseline and failed else 1,
            state="failed" if failed else "succeeded",
            connection_generation=1,
            started_at=now,
            finished_at=now,
        )
    )


def _seed_historical_mapping(
    session: Session,
    *,
    product_id: UUID,
) -> tuple[UUID, UUID]:
    """Create one published revision that is not the product's active pointer."""
    revision_id = uuid4()
    repository_id = uuid4()
    mapping_id = uuid4()
    revision = ProductRevision(
        id=revision_id,
        product_id=product_id,
        description="historical",
        version=2,
        is_published=False,
    )
    session.add_all(
        [
            revision,
            Repository(
                id=repository_id,
                workspace="history-team",
                repository_slug=f"history-{repository_id.hex[:12]}",
            ),
        ]
    )
    session.flush()
    session.add(
        ProductRepositoryMapping(
            id=mapping_id,
            revision_id=revision_id,
            topology="direct",
            identity_key=f'["direct","{repository_id}","history"]',
            sides=[
                ProductMappingRepositorySide(
                    role="direct",
                    repository_id=repository_id,
                    source_branch="history",
                )
            ],
            allowed_targets=[ProductMappingAllowedTarget(branch="history", is_default=True)],
        )
    )
    session.flush()
    revision.is_published = True
    revision.published_at = datetime.now(UTC)
    session.flush()
    return revision_id, mapping_id


def _seed_candidate_mapping(
    factory: sessionmaker[Session],
    *,
    product_id: UUID,
) -> UUID:
    """Attach one non-published candidate mapping to an existing product."""
    revision_id = uuid4()
    repository_id = uuid4()
    mapping_id = uuid4()
    with factory.begin() as session:
        product = session.get_one(Product, product_id)
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
                    workspace="candidate-team",
                    repository_slug=f"candidate-{repository_id.hex[:12]}",
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
                allowed_targets=[
                    ProductMappingAllowedTarget(
                        branch="candidate",
                        is_default=True,
                    )
                ],
            )
        )
        session.flush()
        product.candidate_revision_id = revision_id
        session.flush()
    return mapping_id


def test_existing_product_edit_clones_complete_graph_once_and_isolates_candidate_identity(
    product_session_factory: sessionmaker[Session],
) -> None:
    """Concurrent published edits converge on one deep-cloned candidate graph."""
    admin_id, admin_token = create_authority(
        product_session_factory,
        email="admin@example.com",
        roles=("admin",),
    )
    product_id, active_id = _seed_published_mapping_graph(
        product_session_factory,
        confirmed_by=admin_id,
    )
    configure_dependencies(product_session_factory)
    barrier = Barrier(2)

    def edit_once(_index: int) -> httpx.Response:
        barrier.wait(timeout=5)
        return asyncio.run(
            product_request(
                "PATCH",
                access_token=admin_token,
                path=f"{ADMIN_PRODUCTS_PATH}/{product_id}",
                json_body={
                    "name": "Candidate Graph",
                    "description": "",
                    "expected_candidate_version": 4,
                },
            )
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(edit_once, range(2)))

    assert [response.status_code for response in responses] == [200, 200]
    response_candidates = {response.json()["candidate_revision"]["id"] for response in responses}
    assert len(response_candidates) == 1
    assert {response.json()["name"] for response in responses} == {"Published Graph"}
    assert {response.json()["candidate_revision"]["name"] for response in responses} == {
        "Candidate Graph"
    }
    candidate_id = UUID(response_candidates.pop())

    with product_session_factory() as session:
        product = session.get_one(Product, product_id)
        active = session.get_one(ProductRevision, active_id)
        candidate = session.get_one(ProductRevision, candidate_id)
        active_graph = _revision_mapping_graph(session, revision_id=active_id)
        candidate_graph = _revision_mapping_graph(session, revision_id=candidate_id)

        assert product.display_name == "Published Graph"
        assert product.name_key == "published graph"
        assert product.active_revision_id == active_id
        assert product.candidate_revision_id == candidate_id
        assert active.display_name == "Published Graph"
        assert active.name_key == "published graph"
        assert active.description == "published graph description"
        assert candidate.display_name == "Candidate Graph"
        assert candidate.name_key == "candidate graph"
        assert candidate.description == ""
        assert candidate.version == 5
        assert len(tuple(session.scalars(select(ProductRevision)))) == 2

        assert len(active_graph) == len(candidate_graph) == 2
        assert {mapping.id for mapping in active_graph}.isdisjoint(
            mapping.id for mapping in candidate_graph
        )
        for active_mapping, candidate_mapping in zip(active_graph, candidate_graph, strict=True):
            assert (
                candidate_mapping.topology,
                candidate_mapping.identity_key,
                candidate_mapping.selected_layout_candidate_id,
                candidate_mapping.selected_layout_version,
            ) == (
                active_mapping.topology,
                active_mapping.identity_key,
                active_mapping.selected_layout_candidate_id,
                active_mapping.selected_layout_version,
            )
            assert candidate_mapping.id != active_mapping.id
            assert [
                (side.role, side.repository_id, side.source_branch)
                for side in candidate_mapping.sides
            ] == [
                (side.role, side.repository_id, side.source_branch) for side in active_mapping.sides
            ]
            assert [
                (target.branch, target.is_default) for target in candidate_mapping.allowed_targets
            ] == [(target.branch, target.is_default) for target in active_mapping.allowed_targets]
            assert {(side.mapping_id, side.role) for side in active_mapping.sides}.isdisjoint(
                (side.mapping_id, side.role) for side in candidate_mapping.sides
            )
            assert {
                (target.mapping_id, target.branch) for target in active_mapping.allowed_targets
            }.isdisjoint(
                (target.mapping_id, target.branch) for target in candidate_mapping.allowed_targets
            )
            assert active_mapping.confirmed_preview_job_id is not None
            assert active_mapping.confirmed_preview_digest is not None
            assert active_mapping.preview_confirmed_by == admin_id
            assert active_mapping.preview_confirmed_at is not None
            assert candidate_mapping.confirmed_preview_job_id is None
            assert candidate_mapping.confirmed_preview_digest is None
            assert candidate_mapping.preview_confirmed_by is None
            assert candidate_mapping.preview_confirmed_at is None

        assert (
            session.scalar(
                select(func.count())
                .select_from(PreviewJob)
                .where(PreviewJob.candidate_revision_id == candidate_id)
            )
            == 0
        )


def test_zero_mapping_edit_is_repeatable_but_remains_ineligible_for_publication(
    product_session_factory: sessionmaker[Session],
) -> None:
    """An empty active graph clones as empty without becoming publishable."""
    _admin_id, admin_token = create_authority(
        product_session_factory,
        email="admin@example.com",
        roles=("admin",),
    )
    product_id, active_id = _seed_active_product(
        product_session_factory,
        name="Empty Published",
        description="active",
    )
    configure_dependencies(product_session_factory)
    payload = {
        "name": "Empty Candidate",
        "description": "",
        "expected_candidate_version": 1,
    }

    first = asyncio.run(
        product_request(
            "PATCH",
            access_token=admin_token,
            path=f"{ADMIN_PRODUCTS_PATH}/{product_id}",
            json_body=payload,
        )
    )
    repeated = asyncio.run(
        product_request(
            "PATCH",
            access_token=admin_token,
            path=f"{ADMIN_PRODUCTS_PATH}/{product_id}",
            json_body=payload,
        )
    )

    assert first.status_code == repeated.status_code == 200
    assert repeated.json() == first.json()
    assert first.json()["name"] == "Empty Published"
    assert first.json()["active_revision"]["id"] == str(active_id)
    assert first.json()["candidate_revision"]["name"] == "Empty Candidate"
    candidate_id = UUID(first.json()["candidate_revision"]["id"])
    with product_session_factory() as session:
        assert _revision_mapping_graph(session, revision_id=candidate_id) == ()

    blocked = asyncio.run(
        product_request(
            "POST",
            access_token=admin_token,
            path=f"{ADMIN_PRODUCTS_PATH}/{product_id}/publish",
            json_body={
                "candidate_revision_id": str(candidate_id),
                "expected_candidate_version": 2,
            },
        )
    )
    assert blocked.status_code == 409
    assert blocked.json() == {
        "detail": "Product publication blocked",
        "blockers": ["mappings_required"],
    }


def _add_publishable_mapping(
    session: Session,
    *,
    revision_id: UUID,
    repository_id: UUID,
) -> None:
    """Attach a structurally complete mapping whose preview is deliberately absent."""
    mapping = ProductRepositoryMapping(
        revision_id=revision_id,
        topology="direct",
        identity_key=f'["direct","{repository_id}","main"]',
        selected_layout_candidate_id=uuid4(),
        selected_layout_version=1,
        sides=[
            ProductMappingRepositorySide(
                role="direct",
                repository_id=repository_id,
                source_branch="main",
            )
        ],
        allowed_targets=[ProductMappingAllowedTarget(branch="release/1", is_default=True)],
    )
    session.add(mapping)


def _seed_product_lifecycle_graph(
    factory: sessionmaker[Session],
) -> tuple[UUID, UUID, UUID]:
    """Seed active and candidate revisions that can only fail on preview confirmation."""
    product_id = uuid4()
    active_id = uuid4()
    candidate_id = uuid4()
    repository_id = uuid4()
    with factory.begin() as session:
        product = Product(
            id=product_id,
            display_name=f"Lifecycle {product_id}",
            name_key=f"lifecycle {product_id}",
            is_active=True,
        )
        session.add(product)
        session.flush()
        active_revision = ProductRevision(
            id=active_id,
            product_id=product_id,
            description="active",
            version=6,
            is_published=False,
        )
        session.add_all(
            [
                active_revision,
                ProductRevision(
                    id=candidate_id,
                    product_id=product_id,
                    description="candidate",
                    version=7,
                    is_published=False,
                ),
                Repository(
                    id=repository_id,
                    workspace="lifecycle-team",
                    repository_slug=f"repo-{repository_id.hex[:12]}",
                ),
            ]
        )
        session.flush()
        _add_publishable_mapping(
            session,
            revision_id=active_id,
            repository_id=repository_id,
        )
        _add_publishable_mapping(
            session,
            revision_id=candidate_id,
            repository_id=repository_id,
        )
        session.flush()
        active_revision.is_published = True
        active_revision.published_at = datetime.now(UTC)
        session.flush()
        product.active_revision_id = active_id
        product.candidate_revision_id = candidate_id
    return product_id, active_id, candidate_id


def test_published_product_noop_and_candidate_creation_keep_active_summary_immutable(
    product_session_factory: sessionmaker[Session],
) -> None:
    """Editing an active product either does nothing or creates a separate candidate."""
    _admin_id, admin_token = create_authority(
        product_session_factory,
        email="admin@example.com",
        roles=("admin",),
    )
    product_id, active_id = _seed_active_product(
        product_session_factory,
        name="Published Product",
        description="published",
    )
    configure_dependencies(product_session_factory)

    stale = asyncio.run(
        product_request(
            "PATCH",
            access_token=admin_token,
            path=f"{ADMIN_PRODUCTS_PATH}/{product_id}",
            json_body={
                "name": "Published Product",
                "description": "published",
                "expected_candidate_version": 2,
            },
        )
    )
    assert stale.status_code == 409

    no_op = asyncio.run(
        product_request(
            "PATCH",
            access_token=admin_token,
            path=f"{ADMIN_PRODUCTS_PATH}/{product_id}",
            json_body={
                "name": "  Published\tProduct ",
                "description": "published",
                "expected_candidate_version": 1,
            },
        )
    )
    assert no_op.status_code == 200
    assert no_op.json()["active_revision"]["id"] == str(active_id)
    assert no_op.json()["candidate_revision"] is None

    changed = asyncio.run(
        product_request(
            "PATCH",
            access_token=admin_token,
            path=f"{ADMIN_PRODUCTS_PATH}/{product_id}",
            json_body={
                "name": "Published Product",
                "description": "candidate",
                "expected_candidate_version": 1,
            },
        )
    )
    assert changed.status_code == 200
    assert changed.json()["active_revision"] == no_op.json()["active_revision"]
    assert changed.json()["candidate_revision"]["id"] != str(active_id)
    assert changed.json()["candidate_revision"]["version"] == 2
    assert changed.json()["candidate_revision"]["description"] == "candidate"

    with product_session_factory.begin() as session:
        broken_id = uuid4()
        session.add(
            Product(
                id=broken_id,
                display_name="Pointerless Product",
                name_key="pointerless product",
                is_active=False,
            )
        )
    pointerless = asyncio.run(
        product_request(
            "PATCH",
            access_token=admin_token,
            path=f"{ADMIN_PRODUCTS_PATH}/{broken_id}",
            json_body={
                "name": "Pointerless Product",
                "description": None,
                "expected_candidate_version": 1,
            },
        )
    )
    assert pointerless.status_code == 409
    assert pointerless.json() == {"detail": "Product candidate conflict"}


def test_service_input_guards_reject_non_string_names_and_invalid_collection_options(
    product_session_factory: sessionmaker[Session],
) -> None:
    """Direct service callers receive the same bounded validation contract."""
    with pytest.raises(ValueError, match="must be a string"):
        normalize_product_name(42)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="page size"):
        list_products(product_session_factory(), limit=0)
    with pytest.raises(ValueError, match="status"):
        list_products(product_session_factory(), status="archived")


def _seed_products(factory: sessionmaker[Session], count: int) -> None:
    """Seed products in reverse order so the API must own deterministic ordering."""
    with factory.begin() as session:
        products: list[Product] = []
        revisions: list[ProductRevision] = []
        for index in reversed(range(count)):
            product_id = uuid4()
            revision_id = uuid4()
            name = f"Product {index:03d}"
            is_active = index % 2 == 0
            product = Product(
                id=product_id,
                display_name=name,
                name_key=_a01_key(name),
                is_active=is_active,
            )
            revision = ProductRevision(
                id=revision_id,
                product_id=product_id,
                description=f"Description {index:03d}",
                version=1,
                is_published=is_active,
                published_at=datetime.now(UTC) if is_active else None,
            )
            products.append(product)
            revisions.append(revision)
        session.add_all(products)
        session.flush()
        session.add_all(revisions)
        session.flush()
        revisions_by_product = {revision.product_id: revision for revision in revisions}
        for product in products:
            revision = revisions_by_product[product.id]
            if product.is_active:
                product.active_revision_id = revision.id
            else:
                product.candidate_revision_id = revision.id
        session.flush()


def test_product_collection_is_bounded_filtered_opaque_and_server_ordered(
    product_session_factory: sessionmaker[Session],
) -> None:
    """Prove empty/default/max pages, status filters, and stable keyset order."""
    _admin_id, admin_token = create_authority(
        product_session_factory,
        email="admin@example.com",
        roles=("admin",),
    )
    configure_dependencies(product_session_factory)

    empty = asyncio.run(product_request("GET", access_token=admin_token))
    assert empty.status_code == 200
    assert empty.json() == {"items": [], "next_cursor": None}

    _seed_products(product_session_factory, 105)
    first = asyncio.run(product_request("GET", access_token=admin_token))
    assert first.status_code == 200
    assert len(first.json()["items"]) == 50
    first_cursor = first.json()["next_cursor"]
    assert isinstance(first_cursor, str) and first_cursor
    assert "Product" not in first_cursor

    second = asyncio.run(
        product_request(
            "GET",
            access_token=admin_token,
            path=f"{ADMIN_PRODUCTS_PATH}?cursor={first_cursor}",
        )
    )
    third_cursor = second.json()["next_cursor"]
    third = asyncio.run(
        product_request(
            "GET",
            access_token=admin_token,
            path=f"{ADMIN_PRODUCTS_PATH}?cursor={third_cursor}",
        )
    )
    all_items = first.json()["items"] + second.json()["items"] + third.json()["items"]
    ordered_identities = [(_a01_key(item["name"]), item["id"]) for item in all_items]
    assert [len(page.json()["items"]) for page in (first, second, third)] == [50, 50, 5]
    assert third.json()["next_cursor"] is None
    assert ordered_identities == sorted(ordered_identities)
    assert len(set(ordered_identities)) == 105

    maximum = asyncio.run(
        product_request(
            "GET",
            access_token=admin_token,
            path=f"{ADMIN_PRODUCTS_PATH}?limit=100",
        )
    )
    assert maximum.status_code == 200
    assert len(maximum.json()["items"]) == 100
    assert maximum.json()["next_cursor"]

    active = asyncio.run(
        product_request(
            "GET",
            access_token=admin_token,
            path=f"{ADMIN_PRODUCTS_PATH}?status=active&limit=100",
        )
    )
    inactive = asyncio.run(
        product_request(
            "GET",
            access_token=admin_token,
            path=f"{ADMIN_PRODUCTS_PATH}?status=inactive&limit=100",
        )
    )
    assert active.status_code == inactive.status_code == 200
    assert len(active.json()["items"]) == 53
    assert len(inactive.json()["items"]) == 52
    assert all(item["is_active"] is True for item in active.json()["items"])
    assert all(item["is_active"] is False for item in inactive.json()["items"])

    active_first = asyncio.run(
        product_request(
            "GET",
            access_token=admin_token,
            path=f"{ADMIN_PRODUCTS_PATH}?status=active&limit=1",
        )
    )
    wrong_filter_cursor = asyncio.run(
        product_request(
            "GET",
            access_token=admin_token,
            path=(
                f"{ADMIN_PRODUCTS_PATH}?status=inactive&limit=1"
                f"&cursor={active_first.json()['next_cursor']}"
            ),
        )
    )
    over_limit = asyncio.run(
        product_request(
            "GET",
            access_token=admin_token,
            path=f"{ADMIN_PRODUCTS_PATH}?limit=101",
        )
    )
    invalid = asyncio.run(
        product_request(
            "GET",
            access_token=admin_token,
            path=f"{ADMIN_PRODUCTS_PATH}?cursor=not-a-valid-cursor",
        )
    )
    oversized = asyncio.run(
        product_request(
            "GET",
            access_token=admin_token,
            path=f"{ADMIN_PRODUCTS_PATH}?cursor={'x' * 1025}",
        )
    )
    first_padding = "=" * (-len(first_cursor) % 4)
    first_payload = json.loads(base64.urlsafe_b64decode(first_cursor + first_padding))
    noncanonical_cursor = _cursor_from_json(first_payload, compact=False)
    assert noncanonical_cursor != first_cursor
    wrong_shape_cursor = _cursor_from_json({}, compact=True)
    noncanonical = asyncio.run(
        product_request(
            "GET",
            access_token=admin_token,
            path=f"{ADMIN_PRODUCTS_PATH}?cursor={noncanonical_cursor}",
        )
    )
    wrong_shape = asyncio.run(
        product_request(
            "GET",
            access_token=admin_token,
            path=f"{ADMIN_PRODUCTS_PATH}?cursor={wrong_shape_cursor}",
        )
    )
    assert over_limit.status_code == 422
    assert (
        invalid.status_code
        == oversized.status_code
        == noncanonical.status_code
        == wrong_shape.status_code
        == wrong_filter_cursor.status_code
        == 422
    )
    assert (
        invalid.json()
        == oversized.json()
        == noncanonical.json()
        == wrong_shape.json()
        == wrong_filter_cursor.json()
        == {"detail": "Invalid cursor"}
    )


def test_affected_mapping_count_is_product_local_complete_and_response_consistent(
    product_session_factory: sessionmaker[Session],
) -> None:
    """Count only failed active mappings retaining a successful baseline."""
    admin_id, admin_token = create_authority(
        product_session_factory,
        email="admin@example.com",
        roles=("admin",),
    )
    zero_product_id, zero_revision_id = _seed_published_mapping_graph(
        product_session_factory,
        confirmed_by=admin_id,
        name="Zero affected mappings",
    )
    one_product_id, one_revision_id = _seed_published_mapping_graph(
        product_session_factory,
        confirmed_by=admin_id,
        name="One affected mapping",
    )
    many_product_id, many_revision_id = _seed_published_mapping_graph(
        product_session_factory,
        confirmed_by=admin_id,
        name="Many affected mappings",
    )
    candidate_mapping_id = _seed_candidate_mapping(
        product_session_factory,
        product_id=one_product_id,
    )

    with product_session_factory.begin() as session:
        zero_mapping_ids = tuple(
            session.scalars(
                select(ProductRepositoryMapping.id).where(
                    ProductRepositoryMapping.revision_id == zero_revision_id
                )
            )
        )
        one_mapping_ids = tuple(
            session.scalars(
                select(ProductRepositoryMapping.id).where(
                    ProductRepositoryMapping.revision_id == one_revision_id
                )
            )
        )
        many_mapping_ids = tuple(
            session.scalars(
                select(ProductRepositoryMapping.id).where(
                    ProductRepositoryMapping.revision_id == many_revision_id
                )
            )
        )
        candidate_mapping = session.get_one(
            ProductRepositoryMapping,
            candidate_mapping_id,
        )
        historical_revision_id, historical_mapping_id = _seed_historical_mapping(
            session,
            product_id=one_product_id,
        )

        _seed_import_state(
            session,
            product_id=zero_product_id,
            revision_id=zero_revision_id,
            mapping_id=zero_mapping_ids[0],
            failed=True,
            has_baseline=False,
        )
        _seed_import_state(
            session,
            product_id=zero_product_id,
            revision_id=zero_revision_id,
            mapping_id=zero_mapping_ids[1],
            failed=False,
            has_baseline=True,
        )
        _seed_import_state(
            session,
            product_id=one_product_id,
            revision_id=one_revision_id,
            mapping_id=one_mapping_ids[0],
            failed=True,
            has_baseline=True,
        )
        _seed_import_state(
            session,
            product_id=one_product_id,
            revision_id=one_revision_id,
            mapping_id=one_mapping_ids[1],
            failed=True,
            has_baseline=False,
        )
        _seed_import_state(
            session,
            product_id=one_product_id,
            revision_id=candidate_mapping.revision_id,
            mapping_id=candidate_mapping_id,
            failed=True,
            has_baseline=True,
        )
        _seed_import_state(
            session,
            product_id=one_product_id,
            revision_id=historical_revision_id,
            mapping_id=historical_mapping_id,
            failed=True,
            has_baseline=True,
        )
        for mapping_id in many_mapping_ids:
            _seed_import_state(
                session,
                product_id=many_product_id,
                revision_id=many_revision_id,
                mapping_id=mapping_id,
                failed=True,
                has_baseline=True,
            )

    configure_dependencies(product_session_factory)
    collection = asyncio.run(
        product_request(
            "GET",
            access_token=admin_token,
            path=f"{ADMIN_PRODUCTS_PATH}?limit=100",
        )
    )
    assert collection.status_code == 200
    counts = {item["id"]: item["affected_mapping_count"] for item in collection.json()["items"]}
    assert counts[str(zero_product_id)] == 0
    assert counts[str(one_product_id)] == 1
    assert counts[str(many_product_id)] == 2

    detail = asyncio.run(
        product_request(
            "GET",
            access_token=admin_token,
            path=f"{ADMIN_PRODUCTS_PATH}/{one_product_id}",
        )
    )
    assert detail.status_code == 200
    assert detail.json()["affected_mapping_count"] == 1

    deactivated = asyncio.run(
        product_request(
            "POST",
            access_token=admin_token,
            path=f"{ADMIN_PRODUCTS_PATH}/{many_product_id}/deactivate",
        )
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["affected_mapping_count"] == 2


def test_affected_mapping_query_count_is_constant_across_product_page_sizes(
    product_session_factory: sessionmaker[Session],
) -> None:
    """The aggregate stays inside the product query rather than expanding per row."""
    admin_id, _admin_token = create_authority(
        product_session_factory,
        email="query-count-admin@example.com",
        roles=("admin",),
    )
    for index in range(3):
        _seed_published_mapping_graph(
            product_session_factory,
            confirmed_by=admin_id,
            name=f"Query count product {index}",
        )

    engine = product_session_factory.kw["bind"]

    def statements_for(limit: int) -> tuple[str, ...]:
        statements: list[str] = []

        def record_select(
            _connection: object,
            _cursor: object,
            statement: str,
            _parameters: object,
            _context: object,
            _executemany: bool,
        ) -> None:
            if statement.lstrip().upper().startswith("SELECT"):
                statements.append(statement.casefold())

        event.listen(engine, "before_cursor_execute", record_select)
        try:
            with product_session_factory() as session:
                list_products(session, limit=limit)
        finally:
            event.remove(engine, "before_cursor_execute", record_select)
        return tuple(statements)

    one_product_page = statements_for(1)
    many_product_page = statements_for(100)
    assert len(one_product_page) == len(many_product_page) == 3
    assert sum("import_jobs" in statement for statement in one_product_page) == 1
    assert sum("import_jobs" in statement for statement in many_product_page) == 1
    assert all("bitbucket" not in statement for statement in many_product_page)


def test_product_mutation_cors_preflight_allows_the_registered_patch_contract(
    product_session_factory: sessionmaker[Session],
) -> None:
    """The browser can reach the guarded update route through configured CORS."""
    configure_dependencies(product_session_factory)
    response = asyncio.run(
        product_request(
            "OPTIONS",
            access_token=None,
            path=f"{ADMIN_PRODUCTS_PATH}/{uuid4()}",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "PATCH",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )
    )
    assert response.status_code == 200
    assert "PATCH" in response.headers["access-control-allow-methods"]


def test_admin_product_lifecycle_is_guarded_atomic_and_preview_fail_closed(
    product_session_factory: sessionmaker[Session],
) -> None:
    """Lifecycle routes expose committed state only and never bypass preview."""
    _admin_id, admin_token = create_authority(
        product_session_factory,
        email="admin@example.com",
        roles=("admin",),
    )
    _viewer_id, viewer_token = create_authority(
        product_session_factory,
        email="viewer@example.com",
        roles=("viewer",),
    )
    product_id, active_id, candidate_id = _seed_product_lifecycle_graph(product_session_factory)
    configure_dependencies(product_session_factory)

    publish_path = f"{ADMIN_PRODUCTS_PATH}/{product_id}/publish"
    deactivate_path = f"{ADMIN_PRODUCTS_PATH}/{product_id}/deactivate"
    reactivate_path = f"{ADMIN_PRODUCTS_PATH}/{product_id}/reactivate"
    publish_payload = {
        "candidate_revision_id": str(candidate_id),
        "expected_candidate_version": 7,
    }
    reactivate_payload = {
        "active_revision_id": str(active_id),
        "expected_active_version": 6,
    }
    before_denials = _product_graph(product_session_factory)

    for token, expected_status in ((None, 401), (viewer_token, 403)):
        for path, payload in (
            (publish_path, publish_payload),
            (deactivate_path, None),
            (reactivate_path, reactivate_payload),
        ):
            denied = asyncio.run(
                product_request(
                    "POST",
                    access_token=token,
                    path=path,
                    json_body=payload,
                )
            )
            assert denied.status_code == expected_status
            assert _product_graph(product_session_factory) == before_denials

    before_publish = asyncio.run(
        product_request(
            "GET",
            access_token=admin_token,
            path=f"{ADMIN_PRODUCTS_PATH}/{product_id}",
        )
    ).json()
    blocked_publish = asyncio.run(
        product_request(
            "POST",
            access_token=admin_token,
            path=publish_path,
            json_body=publish_payload,
        )
    )
    assert blocked_publish.status_code == 409
    assert blocked_publish.json() == {
        "detail": "Product publication blocked",
        "blockers": ["preview_confirmation_required"],
    }
    after_blocked_publish = asyncio.run(
        product_request(
            "GET",
            access_token=admin_token,
            path=f"{ADMIN_PRODUCTS_PATH}/{product_id}",
        )
    ).json()
    assert after_blocked_publish == before_publish

    already_active = asyncio.run(
        product_request(
            "POST",
            access_token=admin_token,
            path=reactivate_path,
            json_body=reactivate_payload,
        )
    )
    assert already_active.status_code == 200
    assert already_active.json() == before_publish

    deactivated = asyncio.run(
        product_request(
            "POST",
            access_token=admin_token,
            path=deactivate_path,
        )
    )
    assert deactivated.status_code == 200
    assert deactivated.json() == {
        **before_publish,
        "is_active": False,
    }
    assert deactivated.json()["active_revision"] == before_publish["active_revision"]
    assert deactivated.json()["candidate_revision"] == before_publish["candidate_revision"]

    blocked_reactivation = asyncio.run(
        product_request(
            "POST",
            access_token=admin_token,
            path=reactivate_path,
            json_body=reactivate_payload,
        )
    )
    assert blocked_reactivation.status_code == 409
    assert blocked_reactivation.json() == {
        "detail": "Product publication blocked",
        "blockers": ["preview_confirmation_required"],
    }
    after_blocked_reactivation = asyncio.run(
        product_request(
            "GET",
            access_token=admin_token,
            path=f"{ADMIN_PRODUCTS_PATH}/{product_id}",
        )
    )
    assert after_blocked_reactivation.status_code == 200
    assert after_blocked_reactivation.json() == deactivated.json()

    repeated_deactivation = asyncio.run(
        product_request(
            "POST",
            access_token=admin_token,
            path=deactivate_path,
        )
    )
    assert repeated_deactivation.status_code == 200
    assert repeated_deactivation.json() == deactivated.json()


def test_publish_route_projects_only_the_committed_active_summary(
    product_session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A confirmed service commit is re-read before its HTTP response is projected."""
    _admin_id, admin_token = create_authority(
        product_session_factory,
        email="admin@example.com",
        roles=("admin",),
    )
    product_id, _active_id, candidate_id = _seed_product_lifecycle_graph(product_session_factory)
    configure_dependencies(product_session_factory)

    def confirmed_publish(
        session: Session,
        *,
        product_id: UUID,
        candidate_revision_id: UUID,
        expected_candidate_version: int,
    ) -> publication_service.PublicationResult:
        return publication_service.publish_product_candidate(
            session,
            product_id=product_id,
            candidate_revision_id=candidate_revision_id,
            expected_candidate_version=expected_candidate_version,
            confirmation_predicate=lambda _session, _revision, _mapping: True,
        )

    monkeypatch.setattr(
        admin_product_routes,
        "publish_product_candidate",
        confirmed_publish,
    )
    published = asyncio.run(
        product_request(
            "POST",
            access_token=admin_token,
            path=f"{ADMIN_PRODUCTS_PATH}/{product_id}/publish",
            json_body={
                "candidate_revision_id": str(candidate_id),
                "expected_candidate_version": 7,
            },
        )
    )
    assert published.status_code == 200
    body = published.json()
    assert body["is_active"] is True
    assert body["active_revision"] == {
        "id": str(candidate_id),
        "version": 7,
        "name": "Lifecycle " + str(product_id),
        "description": "candidate",
        "is_published": True,
    }
    assert body["candidate_revision"] is None
    with product_session_factory() as session:
        product = session.get_one(Product, product_id)
        assert product.active_revision_id == candidate_id
        assert product.candidate_revision_id is None


def test_lifecycle_error_projection_never_hides_unexpected_failures() -> None:
    """Only closed domain conflicts may be converted into lifecycle responses."""
    failure = RuntimeError("unexpected lifecycle failure")
    with pytest.raises(RuntimeError, match="unexpected lifecycle failure"):
        admin_product_routes._lifecycle_conflict_response(failure)


def test_product_lifecycle_conflicts_are_stable_closed_and_non_mutating(
    product_session_factory: sessionmaker[Session],
) -> None:
    """Stale lifecycle inputs share one bounded 409 without durable side effects."""
    _admin_id, admin_token = create_authority(
        product_session_factory,
        email="admin@example.com",
        roles=("admin",),
    )
    product_id, active_id, candidate_id = _seed_product_lifecycle_graph(product_session_factory)
    configure_dependencies(product_session_factory)
    before = _product_graph(product_session_factory)

    extra_field = asyncio.run(
        product_request(
            "POST",
            access_token=admin_token,
            path=f"{ADMIN_PRODUCTS_PATH}/{product_id}/publish",
            json_body={
                "candidate_revision_id": str(candidate_id),
                "expected_candidate_version": 7,
                "provider_write": True,
            },
        )
    )
    assert extra_field.status_code == 422
    assert _product_graph(product_session_factory) == before

    stale_calls = (
        (
            f"{ADMIN_PRODUCTS_PATH}/{product_id}/publish",
            {
                "candidate_revision_id": str(candidate_id),
                "expected_candidate_version": 6,
            },
        ),
        (
            f"{ADMIN_PRODUCTS_PATH}/{product_id}/publish",
            {
                "candidate_revision_id": str(uuid4()),
                "expected_candidate_version": 7,
            },
        ),
        (
            f"{ADMIN_PRODUCTS_PATH}/{product_id}/reactivate",
            {
                "active_revision_id": str(active_id),
                "expected_active_version": 5,
            },
        ),
    )
    for path, payload in stale_calls:
        conflict = asyncio.run(
            product_request(
                "POST",
                access_token=admin_token,
                path=path,
                json_body=payload,
            )
        )
        assert conflict.status_code == 409
        assert conflict.json() == {
            "detail": "Product lifecycle conflict",
            "blockers": [],
        }
        assert _product_graph(product_session_factory) == before

    unknown = uuid4()
    for path, payload in (
        (
            f"{ADMIN_PRODUCTS_PATH}/{unknown}/publish",
            {
                "candidate_revision_id": str(candidate_id),
                "expected_candidate_version": 7,
            },
        ),
        (f"{ADMIN_PRODUCTS_PATH}/{unknown}/deactivate", None),
        (
            f"{ADMIN_PRODUCTS_PATH}/{unknown}/reactivate",
            {
                "active_revision_id": str(active_id),
                "expected_active_version": 6,
            },
        ),
    ):
        missing = asyncio.run(
            product_request(
                "POST",
                access_token=admin_token,
                path=path,
                json_body=payload,
            )
        )
        assert missing.status_code == 404
        assert missing.json() == {"detail": "Product unavailable"}
        assert _product_graph(product_session_factory) == before


def test_product_lifecycle_surface_exposes_no_provider_or_translation_write_capability(
    product_session_factory: sessionmaker[Session],
) -> None:
    """The lifecycle API remains a product-pointer boundary, never a provider writer."""
    configure_dependencies(product_session_factory)
    schema = app.openapi()
    lifecycle_operations = {
        path: schema["paths"][path]
        for path in (
            f"{ADMIN_PRODUCTS_PATH}/{{product_id}}/publish",
            f"{ADMIN_PRODUCTS_PATH}/{{product_id}}/deactivate",
            f"{ADMIN_PRODUCTS_PATH}/{{product_id}}/reactivate",
        )
    }
    assert {path: set(item) for path, item in lifecycle_operations.items()} == {
        path: {"post"} for path in lifecycle_operations
    }
    serialized = json.dumps(lifecycle_operations, sort_keys=True).casefold()
    for forbidden in (
        "branch_create",
        "canonical_translation",
        "commit_create",
        "provider_write",
        "pull_request_create",
        "webhook_create",
    ):
        assert forbidden not in serialized

    for path, operation in lifecycle_operations.items():
        post = operation["post"]
        assert post["security"] == [{"OAuth2PasswordBearer": []}]
        assert "409" in post["responses"] or path.endswith("/deactivate")


def test_admin_delete_is_idempotent_hidden_history_preserving_and_name_reusable(
    product_session_factory: sessionmaker[Session],
) -> None:
    admin_id, admin_token = create_authority(
        product_session_factory, email="delete-admin@example.com", roles=("admin",)
    )
    configure_dependencies(product_session_factory)
    created = asyncio.run(
        product_request(
            "POST",
            access_token=admin_token,
            json_body=create_payload(name="Reusable Product"),
        )
    )
    assert created.status_code == 201
    product_id = UUID(created.json()["id"])
    deletion_path = f"{ADMIN_PRODUCTS_PATH}/{product_id}"
    for role in ("viewer", "translator", "product_manager_reviewer"):
        _, token = create_authority(
            product_session_factory,
            email=f"delete-{role}@example.com",
            roles=(role,),
        )
        denied = asyncio.run(product_request("DELETE", access_token=token, path=deletion_path))
        assert denied.status_code == 403
    assert (
        asyncio.run(product_request("DELETE", access_token=None, path=deletion_path)).status_code
        == 401
    )
    deleted = asyncio.run(product_request("DELETE", access_token=admin_token, path=deletion_path))
    assert deleted.status_code == 204 and deleted.content == b""
    assert (
        asyncio.run(
            product_request("GET", access_token=admin_token, path=deletion_path)
        ).status_code
        == 404
    )
    hidden_candidate = asyncio.run(
        product_request(
            "GET",
            access_token=admin_token,
            path=f"{deletion_path}/candidate/mappings",
        )
    )
    assert hidden_candidate.status_code == 404
    hidden_update = asyncio.run(
        product_request(
            "PATCH",
            access_token=admin_token,
            path=deletion_path,
            json_body={
                "expected_candidate_version": 1,
                "name": "Must stay deleted",
                "description": None,
            },
        )
    )
    assert hidden_update.status_code == 404
    listed = asyncio.run(product_request("GET", access_token=admin_token))
    assert listed.status_code == 200 and listed.json()["items"] == []
    repeated = asyncio.run(product_request("DELETE", access_token=admin_token, path=deletion_path))
    assert repeated.status_code == 204 and repeated.content == b""
    with product_session_factory() as session:
        row = session.execute(
            text("SELECT deleted_at, deleted_by, is_active FROM products WHERE id = :product_id"),
            {"product_id": product_id},
        ).one()
        assert row.deleted_at is not None
        assert row.deleted_by == admin_id
        assert row.is_active is False
        assert (
            session.scalar(
                select(func.count())
                .select_from(ProductRevision)
                .where(ProductRevision.product_id == product_id)
            )
            == 1
        )
    replacement = asyncio.run(
        product_request(
            "POST",
            access_token=admin_token,
            json_body=create_payload(name="Reusable Product"),
        )
    )
    assert replacement.status_code == 201
    assert replacement.json()["id"] != str(product_id)
    missing = asyncio.run(
        product_request(
            "DELETE",
            access_token=admin_token,
            path=f"{ADMIN_PRODUCTS_PATH}/{uuid4()}",
        )
    )
    assert missing.status_code == 404


def test_product_delete_blocks_queued_preview_without_mutation(
    product_session_factory: sessionmaker[Session],
) -> None:
    admin_id, admin_token = create_authority(
        product_session_factory, email="delete-worker-admin@example.com", roles=("admin",)
    )
    configure_dependencies(product_session_factory)
    created = asyncio.run(
        product_request(
            "POST",
            access_token=admin_token,
            json_body=create_payload(name="Busy Product"),
        )
    )
    product_id = UUID(created.json()["id"])
    mapping_id = _seed_candidate_mapping(product_session_factory, product_id=product_id)
    now = datetime.now(UTC)
    with product_session_factory.begin() as session:
        product = session.get_one(Product, product_id)
        revision = session.get_one(ProductRevision, product.candidate_revision_id)
        mapping = session.get_one(ProductRepositoryMapping, mapping_id)
        job = PreviewJob(
            input_digest=hashlib.sha256(str(product_id).encode()).hexdigest(),
            attempt=1,
            state="queued",
            product_id=product_id,
            candidate_revision_id=revision.id,
            candidate_revision_version=revision.version,
            mapping_id=mapping.id,
            topology="direct",
            connection_generation=1,
            detector_version="delete-test-v1",
            layout_identity="delete-test-layout",
            repository_sides=[],
        )
        session.add(job)
        session.flush()
        job_id = job.id
    path = f"{ADMIN_PRODUCTS_PATH}/{product_id}"
    blocked = asyncio.run(product_request("DELETE", access_token=admin_token, path=path))
    assert blocked.status_code == 409
    assert blocked.json() == {
        "detail": "Product deletion blocked",
        "blockers": ["active_work"],
    }
    with product_session_factory.begin() as session:
        product = session.get_one(Product, product_id)
        assert product.is_active is False
        assert (
            session.execute(
                text("SELECT deleted_at FROM products WHERE id = :product_id"),
                {"product_id": product_id},
            ).scalar_one()
            is None
        )
        job = session.get_one(PreviewJob, job_id)
        job.state = "failed"
        job.error_code = "invalid_source"
        job.finished_at = now
    assert (
        asyncio.run(product_request("DELETE", access_token=admin_token, path=path)).status_code
        == 204
    )
    with product_session_factory() as session:
        assert (
            session.execute(
                text("SELECT deleted_by FROM products WHERE id = :product_id"),
                {"product_id": product_id},
            ).scalar_one()
            == admin_id
        )


def test_product_delete_blocks_queued_import_without_mutation(
    product_session_factory: sessionmaker[Session],
) -> None:
    admin_id, admin_token = create_authority(
        product_session_factory,
        email="delete-import-admin@example.com",
        roles=("admin",),
    )
    configure_dependencies(product_session_factory)
    product_id, revision_id = _seed_published_mapping_graph(
        product_session_factory,
        confirmed_by=admin_id,
        name="Busy Import Product",
    )
    now = datetime.now(UTC)
    with product_session_factory.begin() as session:
        mapping = _revision_mapping_graph(session, revision_id=revision_id)[0]
        job_id = uuid4()
        execution_id = uuid4()
        session.add(
            ImportJob(
                id=job_id,
                product_id=product_id,
                revision_id=revision_id,
                mapping_id=mapping.id,
                topology=mapping.topology,
                state="queued",
                current_execution_id=execution_id,
                active_baseline_execution_id=None,
                retry_count=0,
                latest_execution_at=now,
            )
        )
        session.flush()
        session.add(
            ImportExecution(
                id=execution_id,
                import_job_id=job_id,
                sequence=1,
                state="queued",
                connection_generation=1,
            )
        )
    path = f"{ADMIN_PRODUCTS_PATH}/{product_id}"
    blocked = asyncio.run(product_request("DELETE", access_token=admin_token, path=path))
    assert blocked.status_code == 409
    assert blocked.json() == {
        "detail": "Product deletion blocked",
        "blockers": ["active_work"],
    }
    with product_session_factory.begin() as session:
        product = session.get_one(Product, product_id)
        assert product.is_active is True
        assert product.deleted_at is None
        job = session.get_one(ImportJob, job_id)
        execution = session.get_one(ImportExecution, execution_id)
        job.state = "import_failed"
        job.error_category = "provider_unavailable"
        job.error_message = "Import provider unavailable"
        execution.state = "failed"
        execution.started_at = now
        execution.finished_at = now
    assert (
        asyncio.run(product_request("DELETE", access_token=admin_token, path=path)).status_code
        == 204
    )
