"""Transactional product identity and candidate-revision authority."""

from __future__ import annotations

import unicodedata
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from verboflex.models.product import Product, ProductRevision


class ProductNameConflict(ValueError):
    """Raised when a global normalized product identity already exists."""


class ProductVersionConflict(ValueError):
    """Raised when a candidate mutation targets a stale revision version."""


class ProductNotFound(LookupError):
    """Raised when an administrator-selected UUID has no durable product."""


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
    product: Product,
    revision: ProductRevision,
    *,
    display_name: str,
    name_key: str,
    description: str | None,
) -> bool:
    return (
        product.display_name == display_name
        and product.name_key == name_key
        and revision.description == description
    )


def _set_product_identity(product: Product, *, display_name: str, name_key: str) -> None:
    product.display_name = display_name
    product.name_key = name_key


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
                if candidate.is_published or candidate.version != expected_version:
                    raise ProductVersionConflict("candidate version conflict")
                if _matches_revision_input(
                    product,
                    candidate,
                    display_name=display_name,
                    name_key=name_key,
                    description=description,
                ):
                    return product
                _set_product_identity(product, display_name=display_name, name_key=name_key)
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
                product,
                active,
                display_name=display_name,
                name_key=name_key,
                description=description,
            ):
                return product

            candidate = ProductRevision(
                product_id=product.id,
                description=description,
                version=active.version + 1,
                is_published=False,
            )
            session.add(candidate)
            session.flush()
            _set_product_identity(product, display_name=display_name, name_key=name_key)
            product.candidate_revision_id = candidate.id
            session.flush()
            return product
    except IntegrityError as error:
        raise ProductNameConflict("product name is unavailable") from error
