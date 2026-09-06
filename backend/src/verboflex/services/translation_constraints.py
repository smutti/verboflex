"""Transaction-local maximum-length projection and mutation authority."""

from __future__ import annotations

import re
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
MAX_CONSTRAINT_CHARS = 1_048_576

_LANGUAGE_PATTERN = re.compile(r"^[a-z]{2,3}(-[A-Z][a-z]{3})?(-([A-Z]{2}|[0-9]{3}))?$")


class ConstraintAuthorityUnavailable(LookupError):
    """Raised when no exact current mapping/base-language authority exists."""


class ConstraintInputInvalid(ValueError):
    """Raised before persistence when a direct caller supplies inexact input."""


class ConstraintVersionConflict(ValueError):
    """Raised when expected_version is not exact current rule authority."""


class ConstraintNotFound(LookupError):
    """Raised when DELETE addresses no explicit rule."""


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


@dataclass(frozen=True, slots=True)
class ConstraintMutationProjection:
    """Explicit rule state plus freshly recomputed values after one mutation."""

    translation_group_id: UUID
    language: str
    base_language: str
    explicit_maximum: int | None
    version: int | None
    values: tuple[ConstraintValueProjection, ...]


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


def put_translation_constraint(
    session: Session,
    *,
    translation_group_id: UUID,
    language: str,
    max_chars: object,
    expected_version: object,
    actor_id: UUID,
) -> ConstraintMutationProjection:
    """Create or replace one explicit rule under exact optimistic authority."""
    maximum = _require_exact_integer(
        max_chars,
        field="max_chars",
        minimum=0,
        maximum=MAX_CONSTRAINT_CHARS,
    )
    expected = _require_exact_integer(
        expected_version,
        field="expected_version",
        minimum=0,
    )
    if not isinstance(actor_id, UUID):
        raise ConstraintInputInvalid("actor_id must be a UUID")
    scope, key, base_language = _lock_mutation_group(
        session,
        translation_group_id=translation_group_id,
        language=language,
    )
    rule = _lock_explicit_rule(
        session,
        scope_id=scope.id,
        translation_key_id=key.id,
        language=language,
    )
    changed = rule is None or rule.max_chars != maximum
    if rule is None:
        if expected != 0:
            raise ConstraintVersionConflict("constraint version conflict")
        key.constraint_generation += 1
        rule = TranslationConstraint(
            scope_id=scope.id,
            translation_key_id=key.id,
            language=language,
            max_chars=maximum,
            version=key.constraint_generation,
            created_by=actor_id,
            updated_by=actor_id,
        )
        session.add(rule)
    else:
        if rule.version != expected:
            raise ConstraintVersionConflict("constraint version conflict")
        if rule.max_chars != maximum:
            rule.max_chars = maximum
            key.constraint_generation = max(key.constraint_generation, rule.version) + 1
            rule.version = key.constraint_generation
            rule.updated_by = actor_id

    if changed and scope.active_execution_id is not None:
        scope.dataset_version += 1
    values = recompute_translation_constraints(
        session,
        scope_id=scope.id,
        raw_key=key.raw_key,
        base_language=base_language,
    )
    return ConstraintMutationProjection(
        translation_group_id=translation_group_id,
        language=language,
        base_language=base_language,
        explicit_maximum=rule.max_chars,
        version=rule.version,
        values=values,
    )


def delete_translation_constraint(
    session: Session,
    *,
    translation_group_id: UUID,
    language: str,
    expected_version: object,
) -> ConstraintMutationProjection:
    """Delete only one addressed explicit rule and restore dynamic fallback."""
    expected = _require_exact_integer(
        expected_version,
        field="expected_version",
        minimum=0,
    )
    scope, key, base_language = _lock_mutation_group(
        session,
        translation_group_id=translation_group_id,
        language=language,
    )
    rule = _lock_explicit_rule(
        session,
        scope_id=scope.id,
        translation_key_id=key.id,
        language=language,
    )
    if rule is None:
        raise ConstraintNotFound("constraint rule is unavailable")
    if rule.version != expected:
        raise ConstraintVersionConflict("constraint version conflict")
    session.delete(rule)
    if scope.active_execution_id is not None:
        scope.dataset_version += 1
    values = recompute_translation_constraints(
        session,
        scope_id=scope.id,
        raw_key=key.raw_key,
        base_language=base_language,
    )
    return ConstraintMutationProjection(
        translation_group_id=translation_group_id,
        language=language,
        base_language=base_language,
        explicit_maximum=None,
        version=None,
        values=values,
    )


def _lock_mutation_group(
    session: Session,
    *,
    translation_group_id: UUID,
    language: str,
) -> tuple[LocalizationScope, TranslationKey, str]:
    if not isinstance(translation_group_id, UUID):
        raise ConstraintInputInvalid("translation_group_id must be a UUID")
    if not isinstance(language, str) or _LANGUAGE_PATTERN.fullmatch(language) is None:
        raise ConstraintInputInvalid("language is invalid")
    anchor = session.get(TranslationValue, translation_group_id)
    if anchor is None or anchor.language != language or anchor.is_deleted:
        raise ConstraintAuthorityUnavailable("constraint group is unavailable")
    scope, base_language = _lock_scope_authority(
        session,
        scope_id=anchor.scope_id,
        base_language=None,
    )
    key = session.execute(
        select(TranslationKey)
        .where(
            TranslationKey.id == anchor.translation_key_id,
            TranslationKey.scope_id == scope.id,
            TranslationKey.is_deleted.is_(False),
        )
        .with_for_update()
    ).scalar_one_or_none()
    if key is None:
        raise ConstraintAuthorityUnavailable("constraint group is unavailable")
    leading_value_id = session.scalar(
        select(TranslationValue.id)
        .where(
            TranslationValue.scope_id == scope.id,
            TranslationValue.translation_key_id == key.id,
            TranslationValue.language == language,
            TranslationValue.is_deleted.is_(False),
        )
        .order_by(TranslationValue.id)
        .limit(1)
    )
    if leading_value_id != translation_group_id:
        raise ConstraintAuthorityUnavailable("constraint group is unavailable")
    return scope, key, base_language


def _lock_explicit_rule(
    session: Session,
    *,
    scope_id: UUID,
    translation_key_id: UUID,
    language: str,
) -> TranslationConstraint | None:
    return session.execute(
        select(TranslationConstraint)
        .where(
            TranslationConstraint.scope_id == scope_id,
            TranslationConstraint.translation_key_id == translation_key_id,
            TranslationConstraint.language == language,
        )
        .with_for_update()
    ).scalar_one_or_none()


def _require_exact_integer(
    value: object,
    *,
    field: str,
    minimum: int,
    maximum: int | None = None,
) -> int:
    if type(value) is not int:
        raise ConstraintInputInvalid(f"{field} must be an exact integer")
    exact = value
    if exact < minimum or (maximum is not None and exact > maximum):
        raise ConstraintInputInvalid(f"{field} is outside its allowed bound")
    return exact


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
