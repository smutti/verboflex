"""Candidate-version authority for revision-owned repository mappings."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from verboflex.models.product import Product, ProductRevision
from verboflex.models.product_mapping import (
    ProductMappingAllowedTarget,
    ProductMappingRepositorySide,
    ProductRepositoryMapping,
)
from verboflex.services.repositories import RepositoryNotFound, get_repository
from verboflex.services.repository_discovery import BranchDiscoveryAdapter


class InvalidMappingInput(ValueError):
    """Raised when mapping shape or branch values are malformed."""


class MappingConflict(ValueError):
    """Raised when one candidate already owns the requested mapping identity."""


class MappingVersionConflict(ValueError):
    """Raised when a mapping mutation targets a stale candidate version."""


class MappingBranchConflict(ValueError):
    """Raised when the exact source branch is absent from current discovery."""


class MappingTargetConflict(ValueError):
    """Raised when an exact target branch is absent from current discovery."""


class MappingNotFound(LookupError):
    """Raised when the product, candidate, or mapping cannot be addressed."""


@dataclass(frozen=True, slots=True)
class MappingRecord:
    """Closed direct/separate projection without lifecycle or manual controls."""

    id: UUID
    revision_id: UUID
    topology: str
    primary_repository_id: UUID
    primary_source_branch: str
    translations_repository_id: UUID | None
    translations_source_branch: str | None
    allowed_target_branches: tuple[str, ...]
    default_target_branch: str
    selected_layout_candidate_id: UUID | None
    selected_layout_version: int | None
    candidate_version: int


def _exact_branch(raw_branch: object) -> str:
    if (
        not isinstance(raw_branch, str)
        or not raw_branch
        or len(raw_branch) > 255
        or "\x00" in raw_branch
        or not raw_branch.isprintable()
    ):
        raise InvalidMappingInput("invalid branch")
    return raw_branch


def _normalized_targets(
    raw_targets: object,
    *,
    default_target: object,
) -> tuple[tuple[str, ...], str]:
    if isinstance(raw_targets, (str, bytes)) or not isinstance(raw_targets, Iterable):
        raise InvalidMappingInput("invalid target set")
    targets = tuple(_exact_branch(target) for target in raw_targets)
    if not targets:
        raise InvalidMappingInput("invalid target set")
    normalized = tuple(sorted(set(targets)))
    normalized_default = _exact_branch(default_target)
    if normalized_default not in normalized:
        raise InvalidMappingInput("default target must belong to target set")
    return normalized, normalized_default


def _direct_identity(repository_id: UUID, source_branch: str) -> str:
    return json.dumps(
        ["direct", str(repository_id), source_branch],
        ensure_ascii=True,
        separators=(",", ":"),
    )


async def _validate_live_branches(
    session: Session,
    *,
    repository_id: UUID,
    source_branch: str,
    targets: tuple[str, ...],
    adapter: BranchDiscoveryAdapter,
) -> None:
    try:
        repository = get_repository(session, repository_id=repository_id)
    except RepositoryNotFound as error:
        raise MappingNotFound("repository unavailable") from error
    discovered = await adapter.list_repository_branches(
        session,
        workspace=repository.workspace,
        repository_slug=repository.repository_slug,
    )
    branch_names = {branch.name for branch in discovered}
    if source_branch not in branch_names:
        raise MappingBranchConflict("source branch unavailable")
    if any(target not in branch_names for target in targets):
        raise MappingTargetConflict("target branch unavailable")


def _locked_candidate(
    session: Session,
    *,
    product_id: UUID,
    expected_version: int,
) -> ProductRevision:
    product = session.execute(
        select(Product).where(Product.id == product_id).with_for_update()
    ).scalar_one_or_none()
    if product is None or product.candidate_revision_id is None:
        raise MappingNotFound("candidate unavailable")
    candidate = session.execute(
        select(ProductRevision)
        .where(ProductRevision.id == product.candidate_revision_id)
        .with_for_update()
    ).scalar_one()
    if candidate.is_published or candidate.version != expected_version:
        raise MappingVersionConflict("candidate version conflict")
    return candidate


def _mapping_statement() -> Select[tuple[ProductRepositoryMapping]]:
    return select(ProductRepositoryMapping).options(
        selectinload(ProductRepositoryMapping.sides),
        selectinload(ProductRepositoryMapping.allowed_targets),
    )


def _record(
    mapping: ProductRepositoryMapping,
    *,
    candidate_version: int,
) -> MappingRecord:
    sides = {side.role: side for side in mapping.sides}
    primary_role = "direct" if mapping.topology == "direct" else "keys"
    primary = sides.get(primary_role)
    translations = sides.get("translations")
    defaults = [target.branch for target in mapping.allowed_targets if target.is_default]
    if primary is None or len(defaults) != 1 or not mapping.allowed_targets:
        raise InvalidMappingInput("invalid persisted mapping")
    return MappingRecord(
        id=mapping.id,
        revision_id=mapping.revision_id,
        topology=mapping.topology,
        primary_repository_id=primary.repository_id,
        primary_source_branch=primary.source_branch,
        translations_repository_id=(
            translations.repository_id if translations is not None else None
        ),
        translations_source_branch=(
            translations.source_branch if translations is not None else None
        ),
        allowed_target_branches=tuple(sorted(target.branch for target in mapping.allowed_targets)),
        default_target_branch=defaults[0],
        selected_layout_candidate_id=mapping.selected_layout_candidate_id,
        selected_layout_version=mapping.selected_layout_version,
        candidate_version=candidate_version,
    )


async def create_direct_mapping(
    session: Session,
    *,
    product_id: UUID,
    expected_candidate_version: int,
    repository_id: UUID,
    source_branch: str,
    allowed_target_branches: object,
    default_target_branch: object,
    adapter: BranchDiscoveryAdapter,
) -> MappingRecord:
    """Create one exact direct mapping and advance its candidate once."""
    exact_source = _exact_branch(source_branch)
    targets, default_target = _normalized_targets(
        allowed_target_branches,
        default_target=default_target_branch,
    )
    await _validate_live_branches(
        session,
        repository_id=repository_id,
        source_branch=exact_source,
        targets=targets,
        adapter=adapter,
    )
    mapping_id = uuid4()
    identity_key = _direct_identity(repository_id, exact_source)
    try:
        with session.begin():
            candidate = _locked_candidate(
                session,
                product_id=product_id,
                expected_version=expected_candidate_version,
            )
            duplicate = session.scalar(
                select(ProductRepositoryMapping.id).where(
                    ProductRepositoryMapping.revision_id == candidate.id,
                    ProductRepositoryMapping.identity_key == identity_key,
                )
            )
            if duplicate is not None:
                raise MappingConflict("mapping unavailable")
            mapping = ProductRepositoryMapping(
                id=mapping_id,
                revision_id=candidate.id,
                topology="direct",
                identity_key=identity_key,
                sides=[
                    ProductMappingRepositorySide(
                        role="direct",
                        repository_id=repository_id,
                        source_branch=exact_source,
                    )
                ],
                allowed_targets=[
                    ProductMappingAllowedTarget(
                        branch=target,
                        is_default=target == default_target,
                    )
                    for target in targets
                ],
            )
            session.add(mapping)
            candidate.version += 1
            session.flush()
            return _record(mapping, candidate_version=candidate.version)
    except IntegrityError as error:
        raise MappingConflict("mapping unavailable") from error


async def update_direct_mapping(
    session: Session,
    *,
    product_id: UUID,
    mapping_id: UUID,
    expected_candidate_version: int,
    repository_id: UUID,
    source_branch: str,
    allowed_target_branches: object,
    default_target_branch: object,
    adapter: BranchDiscoveryAdapter,
) -> MappingRecord:
    """Replace one direct candidate mapping or preserve a semantic no-op."""
    exact_source = _exact_branch(source_branch)
    targets, default_target = _normalized_targets(
        allowed_target_branches,
        default_target=default_target_branch,
    )
    await _validate_live_branches(
        session,
        repository_id=repository_id,
        source_branch=exact_source,
        targets=targets,
        adapter=adapter,
    )
    identity_key = _direct_identity(repository_id, exact_source)
    try:
        with session.begin():
            candidate = _locked_candidate(
                session,
                product_id=product_id,
                expected_version=expected_candidate_version,
            )
            mapping = session.execute(
                _mapping_statement().where(
                    ProductRepositoryMapping.id == mapping_id,
                    ProductRepositoryMapping.revision_id == candidate.id,
                )
            ).scalar_one_or_none()
            if mapping is None or mapping.topology != "direct":
                raise MappingNotFound("mapping unavailable")
            current = _record(mapping, candidate_version=candidate.version)
            if (
                current.primary_repository_id == repository_id
                and current.primary_source_branch == exact_source
                and current.allowed_target_branches == targets
                and current.default_target_branch == default_target
            ):
                return current
            duplicate = session.scalar(
                select(ProductRepositoryMapping.id).where(
                    ProductRepositoryMapping.revision_id == candidate.id,
                    ProductRepositoryMapping.identity_key == identity_key,
                    ProductRepositoryMapping.id != mapping.id,
                )
            )
            if duplicate is not None:
                raise MappingConflict("mapping unavailable")
            direct_side = next(
                (side for side in mapping.sides if side.role == "direct"),
                None,
            )
            if direct_side is None or len(mapping.sides) != 1:
                raise InvalidMappingInput("invalid persisted mapping")
            mapping.identity_key = identity_key
            mapping.selected_layout_candidate_id = None
            mapping.selected_layout_version = None
            mapping.updated_at = datetime.now(UTC)
            direct_side.repository_id = repository_id
            direct_side.source_branch = exact_source
            mapping.allowed_targets = [
                ProductMappingAllowedTarget(
                    branch=target,
                    is_default=target == default_target,
                )
                for target in targets
            ]
            candidate.version += 1
            session.flush()
            return _record(mapping, candidate_version=candidate.version)
    except IntegrityError as error:
        raise MappingConflict("mapping unavailable") from error


def get_mapping(session: Session, *, mapping_id: UUID) -> MappingRecord:
    """Return one closed mapping projection for service composition."""
    with session.begin():
        mapping = session.execute(
            _mapping_statement().where(ProductRepositoryMapping.id == mapping_id)
        ).scalar_one_or_none()
        if mapping is None:
            raise MappingNotFound("mapping unavailable")
        candidate_version = session.scalar(
            select(ProductRevision.version).where(ProductRevision.id == mapping.revision_id)
        )
        if candidate_version is None:
            raise MappingNotFound("candidate unavailable")
        return _record(mapping, candidate_version=candidate_version)
