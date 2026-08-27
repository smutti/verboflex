"""Candidate-version authority for revision-owned repository mappings."""

from __future__ import annotations

import base64
import binascii
import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, cast
from uuid import UUID, uuid4

from sqlalchemy import Select, and_, case, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased, selectinload
from sqlalchemy.sql.elements import ColumnElement

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


class InvalidMappingCursor(ValueError):
    """Raised when a mapping cursor is malformed or belongs to another candidate."""


DEFAULT_MAPPING_PAGE_SIZE = 50
MAX_MAPPING_PAGE_SIZE = 100
_CURSOR_VERSION = 1


@dataclass(frozen=True, slots=True)
class MappingRecord:
    """Closed direct/separate projection without lifecycle or manual controls."""

    id: UUID
    revision_id: UUID
    topology: Literal["direct", "separate"]
    primary_repository_id: UUID
    primary_source_branch: str
    translations_repository_id: UUID | None
    translations_source_branch: str | None
    allowed_target_branches: tuple[str, ...]
    default_target_branch: str
    selected_layout_candidate_id: UUID | None
    selected_layout_version: int | None
    candidate_version: int


@dataclass(frozen=True, slots=True)
class MappingPage:
    """One bounded candidate-owned mapping page."""

    items: tuple[MappingRecord, ...]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class _MappingCursor:
    revision_id: UUID
    topology_rank: int
    primary_repository_id: UUID
    primary_source_branch: str
    translations_repository_id: UUID | None
    translations_source_branch: str | None
    mapping_id: UUID


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
    if mapping.topology not in {"direct", "separate"}:
        raise InvalidMappingInput("invalid persisted mapping")
    topology = cast(Literal["direct", "separate"], mapping.topology)
    sides = {side.role: side for side in mapping.sides}
    primary_role = "direct" if topology == "direct" else "keys"
    primary = sides.get(primary_role)
    translations = sides.get("translations")
    defaults = [target.branch for target in mapping.allowed_targets if target.is_default]
    if primary is None or len(defaults) != 1 or not mapping.allowed_targets:
        raise InvalidMappingInput("invalid persisted mapping")
    return MappingRecord(
        id=mapping.id,
        revision_id=mapping.revision_id,
        topology=topology,
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


def _cursor_for_record(record: MappingRecord) -> _MappingCursor:
    return _MappingCursor(
        revision_id=record.revision_id,
        topology_rank=0 if record.topology == "direct" else 1,
        primary_repository_id=record.primary_repository_id,
        primary_source_branch=record.primary_source_branch,
        translations_repository_id=record.translations_repository_id,
        translations_source_branch=record.translations_source_branch,
        mapping_id=record.id,
    )


def _encode_cursor(position: _MappingCursor) -> str:
    payload = json.dumps(
        {
            "mapping_id": str(position.mapping_id),
            "primary_repository_id": str(position.primary_repository_id),
            "primary_source_branch": position.primary_source_branch,
            "revision_id": str(position.revision_id),
            "topology_rank": position.topology_rank,
            "translations_repository_id": (
                str(position.translations_repository_id)
                if position.translations_repository_id is not None
                else None
            ),
            "translations_source_branch": position.translations_source_branch,
            "version": _CURSOR_VERSION,
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")


def _decode_cursor(cursor: str) -> _MappingCursor:
    if not isinstance(cursor, str) or not cursor or len(cursor) > 2048:
        raise InvalidMappingCursor("invalid cursor")
    try:
        padding = "=" * (-len(cursor) % 4)
        raw = base64.b64decode(cursor + padding, altchars=b"-_", validate=True)
        payload = json.loads(raw)
        if not isinstance(payload, dict) or set(payload) != {
            "mapping_id",
            "primary_repository_id",
            "primary_source_branch",
            "revision_id",
            "topology_rank",
            "translations_repository_id",
            "translations_source_branch",
            "version",
        }:
            raise ValueError
        topology_rank = payload["topology_rank"]
        primary_source_branch = payload["primary_source_branch"]
        translations_repository_raw = payload["translations_repository_id"]
        translations_source_branch = payload["translations_source_branch"]
        if (
            payload["version"] != _CURSOR_VERSION
            or isinstance(topology_rank, bool)
            or topology_rank not in {0, 1}
            or not isinstance(primary_source_branch, str)
            or (
                translations_repository_raw is not None
                and not isinstance(translations_repository_raw, str)
            )
            or (
                translations_source_branch is not None
                and not isinstance(translations_source_branch, str)
            )
            or (translations_repository_raw is None) != (translations_source_branch is None)
        ):
            raise ValueError
        position = _MappingCursor(
            revision_id=UUID(payload["revision_id"]),
            topology_rank=topology_rank,
            primary_repository_id=UUID(payload["primary_repository_id"]),
            primary_source_branch=primary_source_branch,
            translations_repository_id=(
                UUID(translations_repository_raw)
                if translations_repository_raw is not None
                else None
            ),
            translations_source_branch=translations_source_branch,
            mapping_id=UUID(payload["mapping_id"]),
        )
    except (
        binascii.Error,
        json.JSONDecodeError,
        UnicodeDecodeError,
        ValueError,
        TypeError,
    ) as error:
        raise InvalidMappingCursor("invalid cursor") from error
    if _encode_cursor(position) != cursor:
        raise InvalidMappingCursor("invalid cursor")
    return position


def _nullable_after(
    column: ColumnElement[Any],
    value: Any,
    same_value_after: ColumnElement[bool],
) -> ColumnElement[bool]:
    """Build one ascending NULLS LAST keyset step."""
    if value is None:
        return and_(column.is_(None), same_value_after)
    return or_(
        column > value,
        column.is_(None),
        and_(column == value, same_value_after),
    )


def list_candidate_mappings(
    session: Session,
    *,
    product_id: UUID,
    limit: int = DEFAULT_MAPPING_PAGE_SIZE,
    cursor: str | None = None,
) -> MappingPage:
    """List the current candidate in the exact topology/repository/branch tuple order."""
    if not 1 <= limit <= MAX_MAPPING_PAGE_SIZE:
        raise ValueError("invalid page size")
    position = _decode_cursor(cursor) if cursor is not None else None
    primary_side = aliased(ProductMappingRepositorySide, name="primary_mapping_side")
    translations_side = aliased(
        ProductMappingRepositorySide,
        name="translations_mapping_side",
    )
    topology_rank = case(
        (ProductRepositoryMapping.topology == "direct", 0),
        else_=1,
    )
    primary_branch = primary_side.source_branch.collate("C")
    translations_branch = translations_side.source_branch.collate("C")

    with session.begin():
        product = session.get(Product, product_id)
        if product is None or product.candidate_revision_id is None:
            raise MappingNotFound("candidate unavailable")
        candidate = session.get(ProductRevision, product.candidate_revision_id)
        if candidate is None or candidate.is_published:
            raise MappingNotFound("candidate unavailable")
        if position is not None and position.revision_id != candidate.id:
            raise InvalidMappingCursor("invalid cursor")

        statement = (
            _mapping_statement()
            .join(
                primary_side,
                and_(
                    primary_side.mapping_id == ProductRepositoryMapping.id,
                    or_(
                        and_(
                            ProductRepositoryMapping.topology == "direct",
                            primary_side.role == "direct",
                        ),
                        and_(
                            ProductRepositoryMapping.topology == "separate",
                            primary_side.role == "keys",
                        ),
                    ),
                ),
            )
            .outerjoin(
                translations_side,
                and_(
                    translations_side.mapping_id == ProductRepositoryMapping.id,
                    translations_side.role == "translations",
                ),
            )
            .where(ProductRepositoryMapping.revision_id == candidate.id)
        )
        if position is not None:
            after_mapping_id = ProductRepositoryMapping.id > position.mapping_id
            after_translations_branch = _nullable_after(
                translations_branch,
                position.translations_source_branch,
                after_mapping_id,
            )
            after_translations_repository = _nullable_after(
                cast(ColumnElement[Any], translations_side.repository_id),
                position.translations_repository_id,
                after_translations_branch,
            )
            after_primary_branch = or_(
                primary_branch > position.primary_source_branch,
                and_(
                    primary_branch == position.primary_source_branch,
                    after_translations_repository,
                ),
            )
            after_primary_repository = or_(
                primary_side.repository_id > position.primary_repository_id,
                and_(
                    primary_side.repository_id == position.primary_repository_id,
                    after_primary_branch,
                ),
            )
            statement = statement.where(
                or_(
                    topology_rank > position.topology_rank,
                    and_(
                        topology_rank == position.topology_rank,
                        after_primary_repository,
                    ),
                )
            )
        mappings = list(
            session.execute(
                statement.order_by(
                    topology_rank,
                    primary_side.repository_id,
                    primary_branch,
                    translations_side.repository_id.asc().nulls_last(),
                    translations_branch.asc().nulls_last(),
                    ProductRepositoryMapping.id,
                ).limit(limit + 1)
            )
            .unique()
            .scalars()
        )
        records = tuple(
            _record(mapping, candidate_version=candidate.version) for mapping in mappings[:limit]
        )
        next_cursor = (
            _encode_cursor(_cursor_for_record(records[-1])) if len(mappings) > limit else None
        )
    return MappingPage(items=records, next_cursor=next_cursor)


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
