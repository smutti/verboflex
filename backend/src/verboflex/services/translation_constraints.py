"""Transaction-local maximum-length projection and mutation authority."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from verboflex.localization.graphemes import grapheme_count
from verboflex.models.product_mapping import ProductRepositoryMapping
from verboflex.models.translation import LocalizationScope, TranslationKey, TranslationValue
from verboflex.models.translation_constraint import TranslationConstraint

ConstraintSource = Literal["none", "base_default", "language_override"]
ConstraintLabel = Literal["none", "default", "inherited", "override"]


class ConstraintAuthorityUnavailable(LookupError):
    """Raised when no exact current mapping/base-language authority exists."""


@dataclass(frozen=True, slots=True)
class EffectiveConstraint:
    """Resolved rule authority for one exact key/language value."""

    maximum: int | None
    source: ConstraintSource
    label: ConstraintLabel


@dataclass(frozen=True, slots=True)
class ConstraintValueProjection:
    """Fresh server-owned eligibility projection for one canonical value."""

    value_id: UUID
    language: str
    actual: int
    maximum: int | None
    source: ConstraintSource
    label: ConstraintLabel
    is_over_limit: bool
    approval_eligible: bool
    submission_eligible: bool


def project_effective_constraint(
    *,
    language: str,
    base_language: str,
    explicit_constraint: TranslationConstraint | None,
    base_constraint: TranslationConstraint | None,
) -> EffectiveConstraint:
    """Resolve exact override, dynamic base default, then no-rule authority."""
    if language == base_language:
        default = explicit_constraint or base_constraint
        if default is None:
            return EffectiveConstraint(maximum=None, source="none", label="none")
        return EffectiveConstraint(
            maximum=default.max_chars,
            source="base_default",
            label="default",
        )
    if explicit_constraint is not None:
        return EffectiveConstraint(
            maximum=explicit_constraint.max_chars,
            source="language_override",
            label="override",
        )
    if base_constraint is not None:
        return EffectiveConstraint(
            maximum=base_constraint.max_chars,
            source="base_default",
            label="inherited",
        )
    return EffectiveConstraint(maximum=None, source="none", label="none")


def recompute_translation_constraints(
    session: Session,
    *,
    scope_id: UUID,
    raw_key: str | None = None,
    base_language: str | None = None,
) -> tuple[ConstraintValueProjection, ...]:
    """Lock and recompute every affected value inside the caller transaction."""
    scope, resolved_base_language = _lock_scope_authority(
        session,
        scope_id=scope_id,
        base_language=base_language,
    )
    key_statement = (
        select(TranslationKey)
        .where(TranslationKey.scope_id == scope.id)
        .order_by(TranslationKey.id)
        .with_for_update()
    )
    if raw_key is not None:
        key_statement = key_statement.where(TranslationKey.raw_key == raw_key)
    keys = tuple(session.scalars(key_statement))
    if not keys:
        session.flush()
        return ()

    key_ids = tuple(key.id for key in keys)
    values = tuple(
        session.scalars(
            select(TranslationValue)
            .where(
                TranslationValue.scope_id == scope.id,
                TranslationValue.translation_key_id.in_(key_ids),
            )
            .order_by(TranslationValue.id)
            .with_for_update()
        )
    )
    constraints = tuple(
        session.scalars(
            select(TranslationConstraint)
            .where(
                TranslationConstraint.scope_id == scope.id,
                TranslationConstraint.translation_key_id.in_(key_ids),
            )
            .order_by(
                TranslationConstraint.translation_key_id,
                TranslationConstraint.language,
            )
            .with_for_update()
        )
    )
    key_by_id = {key.id: key for key in keys}
    exact_constraints = {
        (constraint.translation_key_id, constraint.language): constraint
        for constraint in constraints
    }
    base_constraints_by_raw_key: dict[str, TranslationConstraint] = {}
    for constraint in constraints:
        if constraint.language != resolved_base_language:
            continue
        key = key_by_id[constraint.translation_key_id]
        current = base_constraints_by_raw_key.setdefault(key.raw_key, constraint)
        if current.id != constraint.id:
            raise ConstraintAuthorityUnavailable("constraint base authority is ambiguous")

    projections: list[ConstraintValueProjection] = []
    for value in values:
        key = key_by_id[value.translation_key_id]
        effective = project_effective_constraint(
            language=value.language,
            base_language=resolved_base_language,
            explicit_constraint=exact_constraints.get((key.id, value.language)),
            base_constraint=base_constraints_by_raw_key.get(key.raw_key),
        )
        actual = grapheme_count(value.display_text)
        is_over_limit = effective.maximum is not None and actual > effective.maximum
        value.grapheme_count = actual
        value.effective_max_chars = effective.maximum
        value.effective_constraint_source = effective.source
        value.is_over_limit = is_over_limit
        eligible = not is_over_limit and not value.is_deleted
        projections.append(
            ConstraintValueProjection(
                value_id=value.id,
                language=value.language,
                actual=actual,
                maximum=effective.maximum,
                source=effective.source,
                label=effective.label,
                is_over_limit=is_over_limit,
                approval_eligible=eligible,
                submission_eligible=eligible,
            )
        )
    session.flush()
    return tuple(projections)


def recompute_after_translation_edit(
    session: Session,
    *,
    value: TranslationValue,
) -> ConstraintValueProjection:
    """Expose the exact recomputation seam required by later translation edits."""
    key = session.get(TranslationKey, value.translation_key_id)
    if key is None or key.scope_id != value.scope_id:
        raise ConstraintAuthorityUnavailable("constraint value authority is unavailable")
    projections = recompute_translation_constraints(
        session,
        scope_id=value.scope_id,
        raw_key=key.raw_key,
    )
    projection = next((item for item in projections if item.value_id == value.id), None)
    if projection is None:
        raise ConstraintAuthorityUnavailable("constraint value authority is unavailable")
    return projection


def _lock_scope_authority(
    session: Session,
    *,
    scope_id: UUID,
    base_language: str | None,
) -> tuple[LocalizationScope, str]:
    scope = session.execute(
        select(LocalizationScope).where(LocalizationScope.id == scope_id).with_for_update()
    ).scalar_one_or_none()
    if scope is None:
        raise ConstraintAuthorityUnavailable("constraint scope is unavailable")
    if base_language is not None:
        return scope, base_language
    mapping = session.execute(
        select(ProductRepositoryMapping)
        .where(
            ProductRepositoryMapping.id == scope.current_mapping_id,
            ProductRepositoryMapping.revision_id == scope.current_revision_id,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if mapping is None or mapping.base_language is None:
        raise ConstraintAuthorityUnavailable("constraint base authority is unavailable")
    return scope, mapping.base_language
