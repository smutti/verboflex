"""Administrator-only product candidate and collection HTTP contracts."""

from __future__ import annotations

import asyncio
import base64
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
from sqlalchemy import create_engine, delete, func, select, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.sql import Executable

from alembic import command
from verboflex.auth.access_tokens import issue_access_token
from verboflex.auth.passwords import hash_password
from verboflex.core.config import Settings, get_settings
from verboflex.db.session import get_db_session
from verboflex.main import app
from verboflex.models.auth_session import AuthSession
from verboflex.models.product import Product, ProductRevision
from verboflex.models.role import Role
from verboflex.models.user import User
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
        "active_revision": None,
        "candidate_revision": {
            "id": body["candidate_revision"]["id"],
            "version": 1,
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
    assert product_paths == {
        ADMIN_PRODUCTS_PATH,
        f"{ADMIN_PRODUCTS_PATH}/{{product_id}}",
        f"{ADMIN_PRODUCTS_PATH}/{{product_id}}/candidate/mappings",
        f"{ADMIN_PRODUCTS_PATH}/{{product_id}}/candidate/mappings/{{mapping_id}}",
    }
    assert "delete" not in app.openapi()["paths"][f"{ADMIN_PRODUCTS_PATH}/{{product_id}}"]
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
