"""Atomic publication and operational lifecycle authority for products."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from verboflex.models.product import Product, ProductRevision
from verboflex.models.product_mapping import ProductRepositoryMapping
from verboflex.services.preview_jobs import is_current_preview_confirmation


class PublicationBlocker(StrEnum):
    """Closed reasons that make a configuration ineligible for operation."""

    MAPPINGS_REQUIRED = "mappings_required"
    MAPPING_CONFIGURATION_INVALID = "mapping_configuration_invalid"
    TARGET_CONFIGURATION_INVALID = "target_configuration_invalid"
    LAYOUT_REQUIRED = "layout_required"
    PREVIEW_CONFIRMATION_REQUIRED = "preview_confirmation_required"


class PublicationBlocked(ValueError):
    """Raised with the complete stable set of eligibility blockers."""

    def __init__(self, blockers: Iterable[PublicationBlocker]) -> None:
        self.blockers = tuple(blockers)
        super().__init__("product publication blocked")


class PublicationConflict(ValueError):
    """Raised when publication targets a stale or different revision."""


class PublicationNotFound(LookupError):
    """Raised when the stable product UUID is unavailable."""


@dataclass(frozen=True, slots=True)
class PublicationResult:
    """Bounded outcome of a committed or idempotent lifecycle transition."""

    product_id: UUID
    active_revision_id: UUID | None
    candidate_revision_id: UUID | None
    is_active: bool
    changed: bool


ConfirmationPredicate = Callable[
    [Session, ProductRevision, ProductRepositoryMapping],
    bool,
]


def _locked_product(session: Session, product_id: UUID) -> Product:
    product = session.execute(
        select(Product).where(Product.id == product_id).with_for_update()
    ).scalar_one_or_none()
    if product is None:
        raise PublicationNotFound("product unavailable")
    return product


def _locked_revision(session: Session, revision_id: UUID) -> ProductRevision:
    revision = session.execute(
        select(ProductRevision).where(ProductRevision.id == revision_id).with_for_update()
    ).scalar_one_or_none()
    if revision is None:
        raise PublicationConflict("revision conflict")
    return revision


def _revision_mappings(
    session: Session,
    revision_id: UUID,
) -> tuple[ProductRepositoryMapping, ...]:
    statement = (
        select(ProductRepositoryMapping)
        .options(
            selectinload(ProductRepositoryMapping.sides),
            selectinload(ProductRepositoryMapping.allowed_targets),
        )
        .where(ProductRepositoryMapping.revision_id == revision_id)
        .order_by(ProductRepositoryMapping.id)
    )
    return tuple(session.execute(statement).scalars())


def _mapping_structure_is_valid(mapping: ProductRepositoryMapping) -> bool:
    roles = tuple(side.role for side in mapping.sides)
    if mapping.topology == "direct":
        return roles == ("direct",)
    if mapping.topology == "separate":
        if roles != ("keys", "translations"):
            return False
        return mapping.sides[0].repository_id != mapping.sides[1].repository_id
    return False


def _target_configuration_is_valid(mapping: ProductRepositoryMapping) -> bool:
    targets = tuple(mapping.allowed_targets)
    defaults = tuple(target for target in targets if target.is_default)
    return (
        bool(targets)
        and len(defaults) == 1
        and defaults[0].branch in {target.branch for target in targets}
    )


def _eligibility_blockers(
    session: Session,
    *,
    revision: ProductRevision,
    confirmation_predicate: ConfirmationPredicate,
) -> tuple[PublicationBlocker, ...]:
    mappings = _revision_mappings(session, revision.id)
    if not mappings:
        return (PublicationBlocker.MAPPINGS_REQUIRED,)

    found: set[PublicationBlocker] = set()
    for mapping in mappings:
        if not _mapping_structure_is_valid(mapping):
            found.add(PublicationBlocker.MAPPING_CONFIGURATION_INVALID)
            continue
        if not _target_configuration_is_valid(mapping):
            found.add(PublicationBlocker.TARGET_CONFIGURATION_INVALID)
            continue
        if mapping.selected_layout_candidate_id is None or mapping.selected_layout_version is None:
            found.add(PublicationBlocker.LAYOUT_REQUIRED)
            continue
        if not confirmation_predicate(session, revision, mapping):
            found.add(PublicationBlocker.PREVIEW_CONFIRMATION_REQUIRED)
    return tuple(blocker for blocker in PublicationBlocker if blocker in found)


def _require_eligible(
    session: Session,
    *,
    revision: ProductRevision,
    confirmation_predicate: ConfirmationPredicate,
) -> None:
    blockers = _eligibility_blockers(
        session,
        revision=revision,
        confirmation_predicate=confirmation_predicate,
    )
    if blockers:
        raise PublicationBlocked(blockers)


def _result(product: Product, *, changed: bool) -> PublicationResult:
    return PublicationResult(
        product_id=product.id,
        active_revision_id=product.active_revision_id,
        candidate_revision_id=product.candidate_revision_id,
        is_active=product.is_active,
        changed=changed,
    )


def publish_product_candidate(
    session: Session,
    *,
    product_id: UUID,
    candidate_revision_id: UUID,
    expected_candidate_version: int,
    confirmation_predicate: ConfirmationPredicate = is_current_preview_confirmation,
) -> PublicationResult:
    """Atomically validate and publish one exact candidate revision."""
    with session.begin():
        product = _locked_product(session, product_id)
        if product.active_revision_id == candidate_revision_id:
            active = _locked_revision(session, candidate_revision_id)
            if not active.is_published or active.version != expected_candidate_version:
                raise PublicationConflict("revision conflict")
            return _result(product, changed=False)
        if product.candidate_revision_id != candidate_revision_id:
            raise PublicationConflict("revision conflict")
        candidate = _locked_revision(session, candidate_revision_id)
        if candidate.is_published or candidate.version != expected_candidate_version:
            raise PublicationConflict("revision conflict")
        _require_eligible(
            session,
            revision=candidate,
            confirmation_predicate=confirmation_predicate,
        )
        candidate.is_published = True
        candidate.published_at = datetime.now(UTC)
        product.active_revision_id = candidate.id
        product.candidate_revision_id = None
        product.is_active = True
        session.flush()
        return _result(product, changed=True)


def deactivate_product(
    session: Session,
    *,
    product_id: UUID,
) -> PublicationResult:
    """Suspend operation without deleting or rewriting configuration."""
    with session.begin():
        product = _locked_product(session, product_id)
        if not product.is_active:
            return _result(product, changed=False)
        product.is_active = False
        session.flush()
        return _result(product, changed=True)


def reactivate_product(
    session: Session,
    *,
    product_id: UUID,
    active_revision_id: UUID,
    expected_active_version: int,
    confirmation_predicate: ConfirmationPredicate = is_current_preview_confirmation,
) -> PublicationResult:
    """Resume only the exact active revision after the publication predicate passes."""
    with session.begin():
        product = _locked_product(session, product_id)
        if product.active_revision_id != active_revision_id:
            raise PublicationConflict("revision conflict")
        active = _locked_revision(session, active_revision_id)
        if not active.is_published or active.version != expected_active_version:
            raise PublicationConflict("revision conflict")
        if product.is_active:
            return _result(product, changed=False)
        _require_eligible(
            session,
            revision=active,
            confirmation_predicate=confirmation_predicate,
        )
        product.is_active = True
        session.flush()
        return _result(product, changed=True)
