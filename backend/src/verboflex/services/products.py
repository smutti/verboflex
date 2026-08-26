"""Transactional product identity and candidate-revision authority."""

from uuid import UUID

from sqlalchemy.orm import Session


class ProductNameConflict(ValueError):
    """Raised when a global normalized product identity already exists."""


class ProductVersionConflict(ValueError):
    """Raised when a candidate mutation targets a stale revision version."""


def normalize_product_name(raw_name: str) -> tuple[str, str]:
    """Normalize one product identity according to the approved A-01 contract."""
    raise NotImplementedError


def create_product(
    session: Session,
    *,
    name: str,
    description: str | None,
) -> object:
    """Create one stable product with an editable candidate revision."""
    raise NotImplementedError


def save_product_candidate(
    session: Session,
    *,
    product_id: UUID,
    expected_version: int,
    name: str,
    description: str | None,
) -> object:
    """Create or update a candidate without mutating an active revision."""
    raise NotImplementedError
