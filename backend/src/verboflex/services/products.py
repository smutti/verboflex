"""Transactional product identity and candidate-revision authority."""

from __future__ import annotations

import base64
import binascii
import json
import unicodedata
from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy import Select, and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from verboflex.models.product import Product, ProductRevision
from verboflex.models.product_mapping import (
    ProductMappingAllowedTarget,
    ProductMappingRepositorySide,
    ProductRepositoryMapping,
)


class ProductNameConflict(ValueError):
    """Raised when a global normalized product identity already exists."""


class ProductVersionConflict(ValueError):
    """Raised when a candidate mutation targets a stale revision version."""


class ProductNotFound(LookupError):
    """Raised when an administrator-selected UUID has no durable product."""


class InvalidProductCursor(ValueError):
    """Raised when a collection cursor is invalid or belongs to another filter."""


DEFAULT_PRODUCT_PAGE_SIZE = 50
MAX_PRODUCT_PAGE_SIZE = 100
_CURSOR_VERSION = 1
_STATUS_VALUES = frozenset({"active", "inactive"})


@dataclass(frozen=True, slots=True)
class ProductRevisionRecord:
    """Safe closed projection of one active or candidate revision."""

    id: UUID
    version: int
    name: str
    description: str | None
    is_published: bool


@dataclass(frozen=True, slots=True)
class ProductRecord:
    """Safe product projection shared by detail, mutation, and collection APIs."""

    id: UUID
    name: str
    is_active: bool
    active_revision: ProductRevisionRecord | None
    candidate_revision: ProductRevisionRecord | None


@dataclass(frozen=True, slots=True)
class ProductPage:
    """One stable keyset page."""

    items: tuple[ProductRecord, ...]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class _CursorPosition:
    name_key: str
    product_id: UUID
    status: str | None


def normalize_product_name(raw_name: str) -> tuple[str, str]:
    """Return the exact A-01 normalized display value and collation-independent key."""
    if not isinstance(raw_name, str):
        raise ValueError("product name must be a string")
    compatibility = unicodedata.normalize("NFKC", raw_name)
    display_name = " ".join(compatibility.split())
    if not display_name or len(display_name) > 120:
        raise ValueError("product name must contain 1 to 120 code points")
    if "\x00" in display_name or not display_name.isprintable():
        raise ValueError("product name contains unsupported characters")
    return display_name, display_name.casefold()


def create_product(
    session: Session,
    *,
    name: str,
    description: str | None,
) -> Product:
    """Create one stable UUID and its first unpublished candidate revision."""
    display_name, name_key = normalize_product_name(name)
    product_id = uuid4()
    revision_id = uuid4()
    try:
        with session.begin():
            if session.scalar(select(Product.id).where(Product.name_key == name_key)) is not None:
                raise ProductNameConflict("product name is unavailable")
            product = Product(
                id=product_id,
                display_name=display_name,
                name_key=name_key,
                is_active=False,
            )
            session.add(product)
            session.flush()
            session.add(
                ProductRevision(
                    id=revision_id,
                    product_id=product_id,
                    display_name=display_name,
                    name_key=name_key,
                    description=description,
                    version=1,
                    is_published=False,
                )
            )
            session.flush()
            product.candidate_revision_id = revision_id
            session.flush()
    except IntegrityError as error:
        raise ProductNameConflict("product name is unavailable") from error
    return product


def _locked_product(session: Session, product_id: UUID) -> Product:
    product = session.execute(
        select(Product).where(Product.id == product_id).with_for_update()
    ).scalar_one_or_none()
    if product is None:
        raise ProductNotFound("product unavailable")
    return product


def _locked_revision(session: Session, revision_id: UUID) -> ProductRevision:
    return session.execute(
        select(ProductRevision).where(ProductRevision.id == revision_id).with_for_update()
    ).scalar_one()


def _matches_revision_input(
    revision: ProductRevision,
    *,
    display_name: str,
    name_key: str,
    description: str | None,
) -> bool:
    return (
        revision.display_name == display_name
        and revision.name_key == name_key
        and revision.description == description
    )


def _require_product_name_available(
    session: Session,
    *,
    product_id: UUID,
    name_key: str,
) -> None:
    conflicting_id = session.scalar(
        select(Product.id).where(
            Product.name_key == name_key,
            Product.id != product_id,
        )
    )
    if conflicting_id is not None:
        raise ProductNameConflict("product name is unavailable")


def _clone_active_revision_graph(
    session: Session,
    *,
    active: ProductRevision,
    display_name: str,
    name_key: str,
    description: str | None,
) -> ProductRevision:
    """Deep-clone one complete published graph with fresh candidate identities."""
    active_mappings = tuple(
        session.execute(
            select(ProductRepositoryMapping)
            .options(
                selectinload(ProductRepositoryMapping.sides),
                selectinload(ProductRepositoryMapping.allowed_targets),
            )
            .where(ProductRepositoryMapping.revision_id == active.id)
            .order_by(ProductRepositoryMapping.id)
        ).scalars()
    )
    candidate = ProductRevision(
        id=uuid4(),
        product_id=active.product_id,
        display_name=display_name,
        name_key=name_key,
        description=description,
        version=active.version + 1,
        is_published=False,
    )
    session.add(candidate)
    session.flush()

    mapping_id_map = {mapping.id: uuid4() for mapping in active_mappings}
    for active_mapping in active_mappings:
        candidate_mapping_id = mapping_id_map[active_mapping.id]
        session.add(
            ProductRepositoryMapping(
                id=candidate_mapping_id,
                revision_id=candidate.id,
                topology=active_mapping.topology,
                identity_key=active_mapping.identity_key,
                selected_layout_candidate_id=active_mapping.selected_layout_candidate_id,
                selected_layout_version=active_mapping.selected_layout_version,
                confirmed_preview_job_id=None,
                confirmed_preview_digest=None,
                preview_confirmed_by=None,
                preview_confirmed_at=None,
                sides=[
                    ProductMappingRepositorySide(
                        mapping_id=candidate_mapping_id,
                        role=side.role,
                        repository_id=side.repository_id,
                        source_branch=side.source_branch,
                    )
                    for side in active_mapping.sides
                ],
                allowed_targets=[
                    ProductMappingAllowedTarget(
                        mapping_id=candidate_mapping_id,
                        branch=target.branch,
                        is_default=target.is_default,
                    )
                    for target in active_mapping.allowed_targets
                ],
            )
        )
    session.flush()
    return candidate


def save_product_candidate(
    session: Session,
    *,
    product_id: UUID,
    expected_version: int,
    name: str,
    description: str | None,
) -> Product:
    """Compare and save one candidate while preserving the published graph byte-for-byte."""
    display_name, name_key = normalize_product_name(name)
    try:
        with session.begin():
            product = _locked_product(session, product_id)
            if product.candidate_revision_id is not None:
                candidate = _locked_revision(session, product.candidate_revision_id)
                if _matches_revision_input(
                    candidate,
                    display_name=display_name,
                    name_key=name_key,
                    description=description,
                ):
                    return product
                if candidate.is_published or candidate.version != expected_version:
                    raise ProductVersionConflict("candidate version conflict")
                _require_product_name_available(
                    session,
                    product_id=product.id,
                    name_key=name_key,
                )
                candidate.display_name = display_name
                candidate.name_key = name_key
                candidate.description = description
                candidate.version += 1
                session.flush()
                return product

            if product.active_revision_id is None:
                raise ProductVersionConflict("candidate version conflict")
            active = _locked_revision(session, product.active_revision_id)
            if not active.is_published or active.version != expected_version:
                raise ProductVersionConflict("candidate version conflict")
            if _matches_revision_input(
                active,
                display_name=display_name,
                name_key=name_key,
                description=description,
            ):
                return product

            _require_product_name_available(
                session,
                product_id=product.id,
                name_key=name_key,
            )
            candidate = _clone_active_revision_graph(
                session,
                active=active,
                display_name=display_name,
                name_key=name_key,
                description=description,
            )
            product.candidate_revision_id = candidate.id
            session.flush()
            return product
    except IntegrityError as error:
        raise ProductNameConflict("product name is unavailable") from error


def _revision_record(revision: ProductRevision | None) -> ProductRevisionRecord | None:
    if revision is None:
        return None
    return ProductRevisionRecord(
        id=revision.id,
        version=revision.version,
        name=revision.display_name,
        description=revision.description,
        is_published=revision.is_published,
    )


def _product_record(product: Product) -> ProductRecord:
    return ProductRecord(
        id=product.id,
        name=product.display_name,
        is_active=product.is_active,
        active_revision=_revision_record(product.active_revision),
        candidate_revision=_revision_record(product.candidate_revision),
    )


def _product_projection_statement() -> Select[tuple[Product]]:
    return select(Product).options(
        selectinload(Product.active_revision),
        selectinload(Product.candidate_revision),
    )


def get_product(session: Session, *, product_id: UUID) -> ProductRecord:
    """Return one product through the closed active/candidate projection."""
    with session.begin():
        product = session.execute(
            _product_projection_statement().where(Product.id == product_id)
        ).scalar_one_or_none()
        if product is None:
            raise ProductNotFound("product unavailable")
        return _product_record(product)


def _encode_cursor(position: _CursorPosition) -> str:
    payload = json.dumps(
        {
            "id": str(position.product_id),
            "name_key": position.name_key,
            "status": position.status,
            "version": _CURSOR_VERSION,
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")


def _decode_cursor(cursor: str, *, status: str | None) -> _CursorPosition:
    if not cursor or len(cursor) > 1024:
        raise InvalidProductCursor("invalid cursor")
    try:
        padding = "=" * (-len(cursor) % 4)
        raw = base64.b64decode(cursor + padding, altchars=b"-_", validate=True)
        payload = json.loads(raw)
        if not isinstance(payload, dict) or set(payload) != {
            "id",
            "name_key",
            "status",
            "version",
        }:
            raise ValueError
        if (
            payload["version"] != _CURSOR_VERSION
            or not isinstance(payload["name_key"], str)
            or payload["status"] not in {None, "active", "inactive"}
            or payload["status"] != status
        ):
            raise ValueError
        position = _CursorPosition(
            name_key=payload["name_key"],
            product_id=UUID(payload["id"]),
            status=payload["status"],
        )
    except (
        binascii.Error,
        json.JSONDecodeError,
        UnicodeDecodeError,
        ValueError,
        TypeError,
    ) as error:
        raise InvalidProductCursor("invalid cursor") from error
    if _encode_cursor(position) != cursor:
        raise InvalidProductCursor("invalid cursor")
    return position


def list_products(
    session: Session,
    *,
    limit: int = DEFAULT_PRODUCT_PAGE_SIZE,
    cursor: str | None = None,
    status: str | None = None,
) -> ProductPage:
    """Return products in database-owned name-key and UUID order."""
    if not 1 <= limit <= MAX_PRODUCT_PAGE_SIZE:
        raise ValueError("invalid page size")
    if status is not None and status not in _STATUS_VALUES:
        raise ValueError("invalid status")
    position = _decode_cursor(cursor, status=status) if cursor is not None else None
    with session.begin():
        statement = _product_projection_statement()
        if status is not None:
            statement = statement.where(Product.is_active.is_(status == "active"))
        if position is not None:
            statement = statement.where(
                or_(
                    Product.name_key > position.name_key,
                    and_(
                        Product.name_key == position.name_key,
                        Product.id > position.product_id,
                    ),
                )
            )
        products = list(
            session.execute(
                statement.order_by(Product.name_key, Product.id).limit(limit + 1)
            ).scalars()
        )
        records = tuple(_product_record(product) for product in products[:limit])
        next_cursor = (
            _encode_cursor(
                _CursorPosition(
                    name_key=products[limit - 1].name_key,
                    product_id=products[limit - 1].id,
                    status=status,
                )
            )
            if len(products) > limit
            else None
        )
    return ProductPage(items=records, next_cursor=next_cursor)
