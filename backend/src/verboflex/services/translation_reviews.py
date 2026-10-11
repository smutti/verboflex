"""Transaction-local complete translation proposal aggregate authority."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, aliased

from verboflex.auth.principal import Principal
from verboflex.auth.translation_access import (
    TranslationGroupAccessMode,
    resolve_translation_group_access,
)
from verboflex.localization.graphemes import grapheme_count
from verboflex.models.product import Product
from verboflex.models.review import ReviewActivity, TranslationProposal, TranslationProposalValue
from verboflex.models.translation import (
    LocalizationScope,
    TranslationKey,
    TranslationValue,
    TranslationValueRevision,
)
from verboflex.services.signed_cursor import (
    CursorBinding,
    CursorPosition,
    InvalidSignedCursor,
    SignedCursorCodec,
)
from verboflex.services.translation_constraints import recompute_translation_constraints

MAX_TEXT_LENGTH = 1_048_576
MAX_GROUP_VALUE_COUNT = 10_000
MAX_EXACT_VERSION = 9_007_199_254_740_991
MAX_REJECTION_REASON_LENGTH = 4_096
REVIEW_ACTIVITY_PAGE_SIZE = 20
REVIEW_ACTIVITY_CURSOR_VERSION = 1
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
ReviewStateValue = Literal["draft", "approved", "rejected"]


class TranslationProposalUnavailable(LookupError):
    """The group or one submitted member is not current and writable."""


class TranslationProposalInputInvalid(ValueError):
    """A direct caller supplied an inexact, duplicate, or unbounded payload."""


class ProposalReviewBlocked(ValueError):
    """Current server authority does not permit the requested review transition."""


class InvalidReviewActivityCursor(ValueError):
    """An activity cursor failed its complete private collection binding."""


@dataclass(frozen=True, slots=True)
class ProposalValueInput:
    translation_value_id: UUID
    selector_version: Literal[1]
    selector_digest: str
    basis_revision_number: int
    basis_digest: str
    proposed_text: str


@dataclass(frozen=True, slots=True)
class ReviewTransitionInput:
    target_state: ReviewStateValue
    expected_version: int
    reason: str | None


@dataclass(frozen=True, slots=True)
class PublishedTranslationValue:
    translation_value_id: UUID
    selector_version: Literal[1]
    selector_digest: str
    revision_number: int
    revision_digest: str
    text: str | None
    review_state: Literal["draft", "approved", "rejected"]


@dataclass(frozen=True, slots=True)
class PendingTranslationValue:
    translation_value_id: UUID
    selector_version: Literal[1]
    selector_digest: str
    basis_revision_number: int
    basis_digest: str
    text: str
    grapheme_count: int
    maximum: int | None
    is_over_limit: bool
    approval_eligible: bool
    submission_eligible: bool


@dataclass(frozen=True, slots=True)
class TranslationProposalActivity:
    id: UUID
    translation_group_id: UUID
    language: str
    kind: Literal["proposal_saved", "state_changed"]
    proposal_version: int
    from_state: ReviewStateValue | None
    to_state: ReviewStateValue | None
    before_values: tuple[object, ...] | None
    after_values: tuple[object, ...] | None
    reason: str | None
    comment_id: UUID | None
    actor_id: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ReviewActivityPage:
    items: tuple[TranslationProposalActivity, ...]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class TranslationProposalProjection:
    translation_group_id: UUID
    language: str
    version: int
    state: Literal["draft", "approved", "rejected"]
    reconciliation_required: bool
    published: tuple[PublishedTranslationValue, ...]
    pending: tuple[PendingTranslationValue, ...]
    updated_by: UUID
    updated_at: datetime
    activity: TranslationProposalActivity | None


@dataclass(frozen=True, slots=True)
class TranslationProposalComparison:
    attempted_version: int
    attempted_values: tuple[ProposalValueInput, ...]
    latest: TranslationProposalProjection | None


class ProposalVersionConflict(ValueError):
    """The aggregate expected version lost to another complete save."""

    def __init__(self, comparison: TranslationProposalComparison) -> None:
        super().__init__("translation proposal conflict")
        self.comparison = comparison


class ProposalBasisStale(ValueError):
    """The submitted imported basis no longer matches current canonical rows."""

    def __init__(self, comparison: TranslationProposalComparison) -> None:
        super().__init__("translation proposal basis stale")
        self.comparison = comparison


TranslationProposalConflict = ProposalVersionConflict


def _exact_int(value: object, *, field: str, minimum: int) -> int:
    if type(value) is not int or value < minimum or value > MAX_EXACT_VERSION:
        raise TranslationProposalInputInvalid(f"{field} is not an exact bounded integer")
    return value


def _digest(value: object, *, field: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise TranslationProposalInputInvalid(f"{field} is not a SHA-256 digest")
    return value


def _text(value: object) -> str:
    if not isinstance(value, str) or len(value) > MAX_TEXT_LENGTH:
        raise TranslationProposalInputInvalid("proposed_text is invalid")
    return value


def _member_field(member: object, name: str) -> object:
    if isinstance(member, Mapping):
        try:
            return member[name]
        except KeyError as error:
            raise TranslationProposalInputInvalid(f"{name} is required") from error
    try:
        return getattr(member, name)
    except AttributeError as error:
        raise TranslationProposalInputInvalid(f"{name} is required") from error


def validate_proposal_values(values: object) -> tuple[ProposalValueInput, ...]:
    """Validate and canonicalize one closed, non-empty aggregate payload."""
    if (
        not isinstance(values, Sequence)
        or isinstance(values, (str, bytes, bytearray))
        or not 1 <= len(values) <= MAX_GROUP_VALUE_COUNT
    ):
        raise TranslationProposalInputInvalid("values must be a bounded non-empty sequence")
    canonical: list[ProposalValueInput] = []
    value_ids: set[UUID] = set()
    selectors: set[tuple[int, str]] = set()
    for member in values:
        value_id = _member_field(member, "translation_value_id")
        if not isinstance(value_id, UUID):
            raise TranslationProposalInputInvalid("translation_value_id must be a UUID")
        selector_version = _exact_int(
            _member_field(member, "selector_version"), field="selector_version", minimum=1
        )
        if selector_version != 1:
            raise TranslationProposalInputInvalid("selector_version is unavailable")
        selector_digest = _digest(_member_field(member, "selector_digest"), field="selector_digest")
        item = ProposalValueInput(
            translation_value_id=value_id,
            selector_version=1,
            selector_digest=selector_digest,
            basis_revision_number=_exact_int(
                _member_field(member, "basis_revision_number"),
                field="basis_revision_number",
                minimum=1,
            ),
            basis_digest=_digest(_member_field(member, "basis_digest"), field="basis_digest"),
            proposed_text=_text(_member_field(member, "proposed_text")),
        )
        selector = (item.selector_version, item.selector_digest)
        if item.translation_value_id in value_ids or selector in selectors:
            raise TranslationProposalInputInvalid("proposal values contain duplicate members")
        value_ids.add(item.translation_value_id)
        selectors.add(selector)
        canonical.append(item)
    return tuple(sorted(canonical, key=lambda item: (item.selector_version, item.selector_digest)))


def validate_review_transition(
    *,
    target_state: object,
    expected_version: object,
    reason: object,
) -> ReviewTransitionInput:
    """Validate one exact transition without widening the closed workflow."""
    if target_state not in ("draft", "approved", "rejected"):
        raise TranslationProposalInputInvalid("target_state is unavailable")
    exact_reason: str | None
    if reason is None:
        exact_reason = None
    elif isinstance(reason, str) and len(reason) <= MAX_REJECTION_REASON_LENGTH:
        exact_reason = reason
    else:
        raise TranslationProposalInputInvalid("reason is invalid")
    if target_state != "rejected" and exact_reason is not None:
        raise TranslationProposalInputInvalid("reason is only available for rejection")
    return ReviewTransitionInput(
        target_state=target_state,
        expected_version=_exact_int(expected_version, field="expected_version", minimum=1),
        reason=exact_reason,
    )


def _lock_group(
    session: Session,
    *,
    translation_group_id: UUID,
    product_id: UUID,
) -> tuple[LocalizationScope, TranslationKey, TranslationValue]:
    """Revalidate group currentness under the shared Product-first lock order."""
    product = session.execute(
        select(Product)
        .where(Product.id == product_id)
        .with_for_update(read=True)
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if (
        product is None
        or not product.is_active
        or product.deleted_at is not None
        or product.active_revision_id is None
    ):
        raise TranslationProposalUnavailable("translation unavailable")
    identity = session.execute(
        select(TranslationValue.scope_id, TranslationValue.translation_key_id).where(
            TranslationValue.id == translation_group_id
        )
    ).one_or_none()
    if identity is None:
        raise TranslationProposalUnavailable("translation unavailable")
    scope = session.execute(
        select(LocalizationScope)
        .where(LocalizationScope.id == identity.scope_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if (
        scope is None
        or scope.product_id != product.id
        or scope.current_revision_id != product.active_revision_id
        or scope.active_execution_id is None
    ):
        raise TranslationProposalUnavailable("translation unavailable")
    key = session.execute(
        select(TranslationKey)
        .where(
            TranslationKey.id == identity.translation_key_id,
            TranslationKey.scope_id == scope.id,
            TranslationKey.product_id == product.id,
            TranslationKey.is_deleted.is_(False),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if key is None:
        raise TranslationProposalUnavailable("translation unavailable")
    anchor = session.execute(
        select(TranslationValue)
        .where(
            TranslationValue.id == translation_group_id,
            TranslationValue.scope_id == scope.id,
            TranslationValue.translation_key_id == key.id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if anchor is None:
        raise TranslationProposalUnavailable("translation unavailable")
    leading_id = session.scalar(
        select(TranslationValue.id)
        .where(
            TranslationValue.scope_id == scope.id,
            TranslationValue.translation_key_id == key.id,
            TranslationValue.language == anchor.language,
        )
        .order_by(TranslationValue.id)
        .limit(1)
    )
    if leading_id != translation_group_id:
        raise TranslationProposalUnavailable("translation unavailable")
    return scope, key, anchor


def _lock_current_values(
    session: Session,
    *,
    scope_id: UUID,
    key_id: UUID,
    language: str,
) -> tuple[TranslationValue, ...]:
    values = tuple(
        session.scalars(
            select(TranslationValue)
            .where(
                TranslationValue.scope_id == scope_id,
                TranslationValue.translation_key_id == key_id,
                TranslationValue.language == language,
                TranslationValue.is_deleted.is_(False),
            )
            .order_by(
                TranslationValue.selector_version,
                TranslationValue.selector_digest,
                TranslationValue.id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    )
    if (
        not values
        or len(values) > MAX_GROUP_VALUE_COUNT
        or all(value.is_deleted for value in values)
    ):
        raise TranslationProposalUnavailable("translation unavailable")
    return values


def _lock_latest_revisions(
    session: Session,
    *,
    value_ids: tuple[UUID, ...],
) -> dict[UUID, TranslationValueRevision]:
    candidate = aliased(TranslationValueRevision)
    latest_number = (
        select(func.max(candidate.revision_number))
        .where(candidate.value_id == TranslationValueRevision.value_id)
        .correlate(TranslationValueRevision)
        .scalar_subquery()
    )
    revisions = tuple(
        session.scalars(
            select(TranslationValueRevision)
            .where(
                TranslationValueRevision.value_id.in_(value_ids),
                TranslationValueRevision.revision_number == latest_number,
            )
            .order_by(TranslationValueRevision.value_id)
            .with_for_update(read=True)
        )
    )
    by_value = {revision.value_id: revision for revision in revisions}
    if len(by_value) != len(value_ids):
        raise TranslationProposalUnavailable("translation basis unavailable")
    return by_value


def _project_proposal(
    *,
    translation_group_id: UUID,
    proposal: TranslationProposal,
    values: tuple[TranslationValue, ...],
    revisions: dict[UUID, TranslationValueRevision],
    activity: ReviewActivity | None,
) -> TranslationProposalProjection:
    current_by_id = {value.id: value for value in values}
    published = tuple(
        PublishedTranslationValue(
            translation_value_id=value.id,
            selector_version=1,
            selector_digest=value.selector_digest,
            revision_number=revisions[value.id].revision_number,
            revision_digest=revisions[value.id].revision_digest,
            text=value.translated_text,
            review_state=cast(Literal["draft", "approved", "rejected"], value.review_state),
        )
        for value in values
    )
    basis_stale = any(
        item.translation_value_id not in current_by_id
        or item.translation_value_id not in revisions
        or item.basis_revision_number != revisions[item.translation_value_id].revision_number
        or item.basis_digest != revisions[item.translation_value_id].revision_digest
        for item in proposal.values
    )
    reconciliation_required = proposal.reconciliation_required or basis_stale
    pending_items: list[PendingTranslationValue] = []
    for item in sorted(
        proposal.values, key=lambda row: (row.selector_version, row.selector_digest)
    ):
        current = current_by_id.get(item.translation_value_id)
        maximum = current.effective_max_chars if current is not None else None
        count = grapheme_count(item.proposed_text)
        over_limit = maximum is not None and count > maximum
        eligible = (
            current is not None
            and not current.is_deleted
            and not over_limit
            and not reconciliation_required
        )
        pending_items.append(
            PendingTranslationValue(
                translation_value_id=item.translation_value_id,
                selector_version=1,
                selector_digest=item.selector_digest,
                basis_revision_number=item.basis_revision_number,
                basis_digest=item.basis_digest,
                text=item.proposed_text,
                grapheme_count=count,
                maximum=maximum,
                is_over_limit=over_limit,
                approval_eligible=eligible,
                submission_eligible=eligible,
            )
        )
    projected_activity = (
        TranslationProposalActivity(
            id=activity.id,
            translation_group_id=translation_group_id,
            language=activity.language,
            kind=cast(Literal["proposal_saved", "state_changed"], activity.kind),
            proposal_version=activity.proposal_version,
            from_state=cast(ReviewStateValue | None, activity.from_state),
            to_state=cast(ReviewStateValue | None, activity.to_state),
            before_values=(
                tuple(activity.before_values) if activity.before_values is not None else None
            ),
            after_values=(
                tuple(activity.after_values) if activity.after_values is not None else None
            ),
            reason=activity.reason,
            comment_id=activity.comment_id,
            actor_id=activity.actor_id,
            created_at=activity.created_at,
        )
        if activity is not None
        else None
    )
    return TranslationProposalProjection(
        translation_group_id=translation_group_id,
        language=proposal.language,
        version=proposal.version,
        state=cast(Literal["draft", "approved", "rejected"], proposal.state),
        reconciliation_required=reconciliation_required,
        published=published,
        pending=tuple(pending_items),
        updated_by=proposal.updated_by,
        updated_at=proposal.updated_at,
        activity=projected_activity,
    )


def _proposal_value_snapshot(proposal: TranslationProposal) -> list[object]:
    return [
        {
            "translation_value_id": str(item.translation_value_id),
            "selector_version": item.selector_version,
            "selector_digest": item.selector_digest,
            "basis_revision_number": item.basis_revision_number,
            "basis_digest": item.basis_digest,
            "text": item.proposed_text,
        }
        for item in sorted(
            proposal.values, key=lambda row: (row.selector_version, row.selector_digest)
        )
    ]


def _comparison(
    *,
    attempted_version: int,
    attempted: tuple[ProposalValueInput, ...],
    latest: TranslationProposalProjection | None,
) -> TranslationProposalComparison:
    return TranslationProposalComparison(
        attempted_version=attempted_version,
        attempted_values=attempted,
        latest=latest,
    )


def save_translation_proposal(
    session: Session,
    *,
    principal: Principal,
    translation_group_id: UUID,
    values: object,
    expected_version: object,
) -> TranslationProposalProjection:
    """Replace a complete key-language proposal under one optimistic version."""
    access = resolve_translation_group_access(
        session,
        principal=principal,
        translation_group_id=translation_group_id,
        mode=TranslationGroupAccessMode.PROPOSE,
    )
    attempted = validate_proposal_values(values)
    exact_expected_version = _exact_int(expected_version, field="expected_version", minimum=0)
    scope, key, anchor = _lock_group(
        session,
        translation_group_id=translation_group_id,
        product_id=access.product_id,
    )
    current_values = _lock_current_values(
        session,
        scope_id=scope.id,
        key_id=key.id,
        language=anchor.language,
    )
    constraint_projections = recompute_translation_constraints(
        session,
        scope_id=scope.id,
        raw_key=key.raw_key,
    )
    projection_ids = {projection.value_id for projection in constraint_projections}
    if any(value.id not in projection_ids for value in current_values):
        raise TranslationProposalUnavailable("translation constraint authority unavailable")
    current_revisions = _lock_latest_revisions(
        session, value_ids=tuple(value.id for value in current_values)
    )
    proposal = session.execute(
        select(TranslationProposal)
        .where(
            TranslationProposal.translation_key_id == key.id,
            TranslationProposal.language == anchor.language,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    latest_activity = (
        session.execute(
            select(ReviewActivity)
            .where(ReviewActivity.proposal_id == proposal.id)
            .order_by(ReviewActivity.created_at.desc(), ReviewActivity.id.desc())
            .limit(1)
        ).scalar_one_or_none()
        if proposal is not None
        else None
    )
    latest = (
        _project_proposal(
            translation_group_id=translation_group_id,
            proposal=proposal,
            values=current_values,
            revisions=current_revisions,
            activity=latest_activity,
        )
        if proposal is not None
        else None
    )
    if proposal is None and exact_expected_version != 0:
        raise ProposalVersionConflict(
            _comparison(
                attempted_version=exact_expected_version,
                attempted=attempted,
                latest=None,
            )
        )
    if proposal is not None and proposal.version != exact_expected_version:
        raise ProposalVersionConflict(
            _comparison(
                attempted_version=exact_expected_version,
                attempted=attempted,
                latest=latest,
            )
        )

    current_identity = {
        (value.id, value.selector_version, value.selector_digest) for value in current_values
    }
    attempted_identity = {
        (item.translation_value_id, item.selector_version, item.selector_digest)
        for item in attempted
    }
    if attempted_identity != current_identity:
        raise TranslationProposalUnavailable("translation selector set unavailable")
    current_by_id = {value.id: value for value in current_values}
    stale_basis = any(
        item.basis_revision_number != current_revisions[item.translation_value_id].revision_number
        or item.basis_digest != current_revisions[item.translation_value_id].revision_digest
        for item in attempted
    )
    if stale_basis:
        if proposal is not None:
            proposal.state = "draft"
            proposal.reconciliation_required = True
            session.flush()
            latest = _project_proposal(
                translation_group_id=translation_group_id,
                proposal=proposal,
                values=current_values,
                revisions=current_revisions,
                activity=latest_activity,
            )
        raise ProposalBasisStale(
            _comparison(
                attempted_version=exact_expected_version,
                attempted=attempted,
                latest=latest,
            )
        )

    now = datetime.now(UTC)
    if proposal is None:
        previous_state: ReviewStateValue | None = None
        proposal = TranslationProposal(
            scope_id=scope.id,
            translation_key_id=key.id,
            language=anchor.language,
            version=1,
            state="draft",
            reconciliation_required=False,
            created_by=principal.user_id,
            updated_by=principal.user_id,
            created_at=now,
            updated_at=now,
        )
        session.add(proposal)
        session.flush()
        before_values: list[object] = []
    else:
        previous_state = cast(ReviewStateValue, proposal.state)
        before_values = _proposal_value_snapshot(proposal)
        proposal.values.clear()
        session.flush()
        proposal.version += 1
        proposal.state = "draft"
        proposal.reconciliation_required = False
        proposal.updated_by = principal.user_id
        proposal.updated_at = now

    after_values: list[object] = []
    for item in attempted:
        current = current_by_id[item.translation_value_id]
        child = TranslationProposalValue(
            proposal_id=proposal.id,
            translation_key_id=key.id,
            language=anchor.language,
            translation_value_id=current.id,
            selector_version=1,
            selector_digest=item.selector_digest,
            basis_revision_number=item.basis_revision_number,
            basis_digest=item.basis_digest,
            proposed_text=item.proposed_text,
            grapheme_count=grapheme_count(item.proposed_text),
        )
        proposal.values.append(child)
        after_values.append(
            {
                "translation_value_id": str(current.id),
                "selector_version": 1,
                "selector_digest": item.selector_digest,
                "basis_revision_number": item.basis_revision_number,
                "basis_digest": item.basis_digest,
                "text": item.proposed_text,
            }
        )
    activity = ReviewActivity(
        proposal_id=proposal.id,
        translation_key_id=key.id,
        language=anchor.language,
        kind="proposal_saved",
        proposal_version=proposal.version,
        from_state=previous_state,
        to_state="draft",
        before_values=before_values,
        after_values=after_values,
        reason=None,
        comment_id=None,
        actor_id=principal.user_id,
        created_at=now,
    )
    session.add(activity)
    session.flush()
    return _project_proposal(
        translation_group_id=translation_group_id,
        proposal=proposal,
        values=current_values,
        revisions=current_revisions,
        activity=activity,
    )


def _activity_binding(
    *,
    principal: Principal,
    translation_group_id: UUID,
    translation_key_id: UUID,
    language: str,
) -> CursorBinding:
    return CursorBinding(
        kind="activity",
        principal_id=principal.user_id,
        scope=f"{translation_key_id}:{language}",
        filters={"group": str(translation_group_id), "language": language},
        page_size=REVIEW_ACTIVITY_PAGE_SIZE,
        direction="descending",
        version=REVIEW_ACTIVITY_CURSOR_VERSION,
    )


def _project_activity(
    *,
    translation_group_id: UUID,
    activity: ReviewActivity,
) -> TranslationProposalActivity:
    return TranslationProposalActivity(
        id=activity.id,
        translation_group_id=translation_group_id,
        language=activity.language,
        kind=cast(Literal["proposal_saved", "state_changed"], activity.kind),
        proposal_version=activity.proposal_version,
        from_state=cast(ReviewStateValue | None, activity.from_state),
        to_state=cast(ReviewStateValue | None, activity.to_state),
        before_values=(
            tuple(activity.before_values) if activity.before_values is not None else None
        ),
        after_values=(tuple(activity.after_values) if activity.after_values is not None else None),
        reason=activity.reason,
        comment_id=activity.comment_id,
        actor_id=activity.actor_id,
        created_at=activity.created_at,
    )


def list_review_activity(
    session: Session,
    *,
    principal: Principal,
    translation_group_id: UUID,
    cursor: str | None,
    cursor_secret: str,
) -> ReviewActivityPage:
    """Return one newest-first immutable activity page for an authorized group."""
    access = resolve_translation_group_access(
        session,
        principal=principal,
        translation_group_id=translation_group_id,
        mode=TranslationGroupAccessMode.READ,
    )
    anchor = session.get(TranslationValue, access.group.id)
    if (
        anchor is None
        or anchor.id != translation_group_id
        or anchor.language != access.group.language
        or anchor.key.product_id != access.product_id
    ):
        raise TranslationProposalUnavailable("translation unavailable")
    binding = _activity_binding(
        principal=principal,
        translation_group_id=translation_group_id,
        translation_key_id=anchor.translation_key_id,
        language=anchor.language,
    )
    position = None
    if cursor is not None:
        try:
            position = SignedCursorCodec(cursor_secret).decode(cursor, binding=binding)
        except InvalidSignedCursor as error:
            raise InvalidReviewActivityCursor("invalid review activity cursor") from error

    proposal_id = session.scalar(
        select(TranslationProposal.id).where(
            TranslationProposal.translation_key_id == anchor.translation_key_id,
            TranslationProposal.language == anchor.language,
        )
    )
    if proposal_id is None:
        if position is not None:
            raise InvalidReviewActivityCursor("invalid review activity cursor")
        return ReviewActivityPage(items=(), next_cursor=None)

    query = select(ReviewActivity).where(
        ReviewActivity.proposal_id == proposal_id,
        ReviewActivity.translation_key_id == anchor.translation_key_id,
        ReviewActivity.language == anchor.language,
    )
    if position is not None:
        cursor_anchor = session.scalar(
            select(ReviewActivity.id).where(
                ReviewActivity.proposal_id == proposal_id,
                ReviewActivity.id == position.id,
                ReviewActivity.created_at == position.created_at,
            )
        )
        if cursor_anchor is None:
            raise InvalidReviewActivityCursor("invalid review activity cursor")
        query = query.where(
            or_(
                ReviewActivity.created_at < position.created_at,
                and_(
                    ReviewActivity.created_at == position.created_at,
                    ReviewActivity.id < position.id,
                ),
            )
        )
    rows = tuple(
        session.scalars(
            query.order_by(ReviewActivity.created_at.desc(), ReviewActivity.id.desc()).limit(
                REVIEW_ACTIVITY_PAGE_SIZE + 1
            )
        )
    )
    visible = rows[:REVIEW_ACTIVITY_PAGE_SIZE]
    next_cursor = None
    if len(rows) > REVIEW_ACTIVITY_PAGE_SIZE and visible:
        last = visible[-1]
        next_cursor = SignedCursorCodec(cursor_secret).encode(
            binding=binding,
            position=CursorPosition(created_at=last.created_at, id=last.id),
        )
    return ReviewActivityPage(
        items=tuple(
            _project_activity(translation_group_id=translation_group_id, activity=activity)
            for activity in visible
        ),
        next_cursor=next_cursor,
    )


def transition_translation_proposal(
    session: Session,
    *,
    principal: Principal,
    translation_group_id: UUID,
    target_state: object,
    expected_version: object,
    reason: object,
) -> TranslationProposalProjection:
    """Move one complete pending proposal through the closed review state machine."""
    access = resolve_translation_group_access(
        session,
        principal=principal,
        translation_group_id=translation_group_id,
        mode=TranslationGroupAccessMode.REVIEW,
    )
    transition = validate_review_transition(
        target_state=target_state,
        expected_version=expected_version,
        reason=reason,
    )
    scope, key, anchor = _lock_group(
        session,
        translation_group_id=translation_group_id,
        product_id=access.product_id,
    )
    current_values = _lock_current_values(
        session,
        scope_id=scope.id,
        key_id=key.id,
        language=anchor.language,
    )
    constraint_projections = recompute_translation_constraints(
        session,
        scope_id=scope.id,
        raw_key=key.raw_key,
    )
    constraint_by_value = {item.value_id: item for item in constraint_projections}
    current_revisions = _lock_latest_revisions(
        session,
        value_ids=tuple(value.id for value in current_values),
    )
    proposal = session.execute(
        select(TranslationProposal)
        .where(
            TranslationProposal.translation_key_id == key.id,
            TranslationProposal.language == anchor.language,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if proposal is None:
        raise TranslationProposalUnavailable("translation proposal unavailable")
    latest_activity = session.execute(
        select(ReviewActivity)
        .where(ReviewActivity.proposal_id == proposal.id)
        .order_by(ReviewActivity.created_at.desc(), ReviewActivity.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    latest = _project_proposal(
        translation_group_id=translation_group_id,
        proposal=proposal,
        values=current_values,
        revisions=current_revisions,
        activity=latest_activity,
    )
    if proposal.version != transition.expected_version:
        raise ProposalVersionConflict(
            _comparison(
                attempted_version=transition.expected_version,
                attempted=(),
                latest=latest,
            )
        )
    if proposal.state == transition.target_state:
        raise TranslationProposalInputInvalid("target_state is already current")

    current_identity = {
        (value.id, value.selector_version, value.selector_digest) for value in current_values
    }
    proposal_identity = {
        (item.translation_value_id, item.selector_version, item.selector_digest)
        for item in proposal.values
    }
    complete = (
        proposal_identity == current_identity
        and len(proposal.values) == len(current_values)
        and all(not value.is_deleted for value in current_values)
        and all(value.id in constraint_by_value for value in current_values)
    )
    if not complete:
        raise ProposalReviewBlocked("translation proposal review blocked")
    if transition.target_state == "approved":
        current_by_id = {value.id: value for value in current_values}
        stale_basis = proposal.reconciliation_required or any(
            item.translation_value_id not in current_by_id
            or item.translation_value_id not in current_revisions
            or item.basis_revision_number
            != current_revisions[item.translation_value_id].revision_number
            or item.basis_digest != current_revisions[item.translation_value_id].revision_digest
            for item in proposal.values
        )
        # Approval applies to the proposed text. The imported text can be shorter
        # (or longer) than the edit; its cached violation must not decide this gate.
        ineligible = stale_basis or any(item.is_over_limit for item in latest.pending)
        if ineligible:
            raise ProposalReviewBlocked("translation proposal review blocked")

    before_state = cast(ReviewStateValue, proposal.state)
    snapshot = _proposal_value_snapshot(proposal)
    now = datetime.now(UTC)
    proposal.version += 1
    proposal.state = transition.target_state
    proposal.updated_by = principal.user_id
    proposal.updated_at = now
    activity = ReviewActivity(
        proposal_id=proposal.id,
        translation_key_id=key.id,
        language=anchor.language,
        kind="state_changed",
        proposal_version=proposal.version,
        from_state=before_state,
        to_state=transition.target_state,
        before_values=snapshot,
        after_values=snapshot,
        reason=transition.reason,
        comment_id=None,
        actor_id=principal.user_id,
        created_at=now,
    )
    session.add(activity)
    session.flush()
    return _project_proposal(
        translation_group_id=translation_group_id,
        proposal=proposal,
        values=current_values,
        revisions=current_revisions,
        activity=activity,
    )
