"""Product-first durable read-only review jobs. HTTP does database work only."""

import hashlib
import json
from collections.abc import Callable
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from itertools import islice
from typing import Literal, cast
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from verboflex.localization.graphemes import grapheme_count
from verboflex.localization.writing.core import WritebackReason, WritebackRejected
from verboflex.models.authoring import AuthoringRequest
from verboflex.models.product import Product
from verboflex.models.review import TranslationProposal, TranslationProposalValue
from verboflex.models.submission import SubmissionBatch, SubmissionReview
from verboflex.models.translation import LocalizationScope, TranslationKey, TranslationValue
from verboflex.models.user import User
from verboflex.schemas.submissions import (
    ChangeSetCandidate,
    ChangeSetCandidatesResponse,
    MappingDestination,
    MappingTarget,
    ReviewedFile,
    ReviewedGroup,
    ReviewedSource,
    ReviewedValue,
    ReviewFilesPage,
    ReviewValuesPage,
    SelectedProposal,
    SubmissionReviewResponse,
)
from verboflex.services.submission_codec import (
    MAX_PAYLOAD_BYTES,
    decode_submission_review,
    encode_submission_review,
)
from verboflex.services.submission_selection import (
    MAX_SELECTED_PROPOSALS,
    PreparedSubmissionReview,
    SubmissionReadAdapter,
    destinations,
    partition_selection,
    prepare_submission_groups,
    proposal_mapping,
)
from verboflex.services.writeback import (
    ProposalSelection,
    WritebackSelection,
)
from verboflex.services.writeback_authority import (
    capture_writeback_authority,
)

REVIEW_ROLES = frozenset({"admin", "product_manager_reviewer"})
KNOWN_ROLES = REVIEW_ROLES | {"translator", "viewer"}
REVIEW_LIFETIME = timedelta(minutes=15)
ReviewEnqueuer = Callable[[UUID], None]


class SubmissionReviewUnavailable(LookupError):
    pass


class SubmissionReviewDenied(PermissionError):
    pass


def _product_actor(
    session: Session, product_id: UUID, actor_id: UUID, *, action: bool
) -> tuple[Product, User]:
    product = session.scalar(
        select(Product).where(Product.id == product_id).with_for_update(read=not action)
    )
    if (
        product is None
        or not product.is_active
        or product.deleted_at is not None
        or product.active_revision_id is None
    ):
        raise SubmissionReviewUnavailable("review unavailable")
    actor = session.scalar(
        select(User)
        .where(User.id == actor_id)
        .with_for_update(read=True)
        .execution_options(populate_existing=True)
    )
    roles = {role.name for role in actor.roles} if actor is not None else set()
    if (
        actor is None
        or not actor.is_active
        or actor.must_change_password
        or not roles
        or not roles <= KNOWN_ROLES
    ):
        raise SubmissionReviewDenied("review action denied")
    if action and REVIEW_ROLES.isdisjoint(roles):
        raise SubmissionReviewDenied("review action denied")
    return product, actor


def _selection(
    session: Session, *, product_id: UUID, actor_id: UUID, proposals: list[SelectedProposal]
) -> WritebackSelection:
    if not proposals or len(proposals) > MAX_SELECTED_PROPOSALS:
        raise WritebackRejected(WritebackReason.LIMIT_EXCEEDED)
    requested_ids = {p.proposal_id for p in proposals}
    if len(requested_ids) != len(proposals):
        raise WritebackRejected(WritebackReason.STALE_BASIS)
    owned = set(
        session.scalars(
            select(TranslationProposal.id)
            .join(LocalizationScope, LocalizationScope.id == TranslationProposal.scope_id)
            .where(
                TranslationProposal.id.in_(requested_ids),
                LocalizationScope.product_id == product_id,
            )
        )
    )
    owned.update(
        session.scalars(
            select(AuthoringRequest.id)
            .join(LocalizationScope)
            .where(
                AuthoringRequest.id.in_(requested_ids), LocalizationScope.product_id == product_id
            )
        )
    )
    if owned != requested_ids:
        raise SubmissionReviewUnavailable("review unavailable")
    selection = WritebackSelection(
        actor_id,
        tuple(
            ProposalSelection(p.proposal_id, p.expected_version)
            for p in sorted(proposals, key=lambda p: p.proposal_id)
        ),
    )
    # Local capture is bounded and provider-free; normal token renewal is worker work.
    capture_writeback_authority(session, selection=selection, allow_expired_connection=True)
    return selection


def list_change_set_candidates(
    session: Session,
    *,
    product_id: UUID,
    actor_id: UUID,
    after: UUID | None = None,
    state: Literal["approved", "draft", "rejected", "all"] = "approved",
    query: str = "",
    language: str = "",
    translation_group_id: UUID | None = None,
) -> ChangeSetCandidatesResponse:
    with session.begin():
        product, actor = _product_actor(session, product_id, actor_id, action=False)
        can_request = not REVIEW_ROLES.isdisjoint(role.name for role in actor.roles)
        statement = (
            select(TranslationProposal, func.substr(TranslationKey.raw_key, 1, 256))
            .join(LocalizationScope, LocalizationScope.id == TranslationProposal.scope_id)
            .join(TranslationKey, TranslationKey.id == TranslationProposal.translation_key_id)
            .where(
                LocalizationScope.product_id == product_id,
                LocalizationScope.current_revision_id == product.active_revision_id,
                TranslationKey.is_deleted.is_(False),
            )
            .order_by(TranslationProposal.id)
            .limit(51)
        )
        if after is not None:
            statement = statement.where(TranslationProposal.id > after)
        if state != "all":
            statement = statement.where(TranslationProposal.state == state)
        if query:
            statement = statement.where(TranslationKey.raw_key.icontains(query, autoescape=True))
        if language:
            statement = statement.where(TranslationProposal.language == language)
        if translation_group_id is not None:
            leading_value = (
                select(TranslationValue.id)
                .where(
                    TranslationValue.scope_id == TranslationProposal.scope_id,
                    TranslationValue.translation_key_id == TranslationProposal.translation_key_id,
                    TranslationValue.language == TranslationProposal.language,
                )
                .order_by(TranslationValue.id)
                .limit(1)
                .correlate(TranslationProposal)
                .scalar_subquery()
            )
            statement = statement.where(leading_value == translation_group_id)
        rows: list[tuple[TranslationProposal | AuthoringRequest, str]] = [
            (proposal, key) for proposal, key in session.execute(statement)
        ]
        if translation_group_id is None:
            additions = (
                select(AuthoringRequest)
                .join(LocalizationScope)
                .where(
                    LocalizationScope.product_id == product_id,
                    LocalizationScope.current_revision_id == product.active_revision_id,
                )
                .order_by(AuthoringRequest.id)
                .limit(51)
            )
            if after is not None:
                additions = additions.where(AuthoringRequest.id > after)
            if state != "all":
                additions = additions.where(AuthoringRequest.state == state)
            if query:
                additions = additions.where(
                    AuthoringRequest.raw_key.icontains(query, autoescape=True)
                )
            if language:
                additions = additions.where(AuthoringRequest.language == language)
            rows.extend((row, row.raw_key[:256]) for row in session.scalars(additions))
            rows = sorted(rows, key=lambda item: item[0].id)[:51]
        # Capture retains scope locks until this transaction ends. Page/filter
        # order is by proposal UUID and can visit scopes in opposite orders.
        # Lock the complete bounded page scope set once, in the same canonical
        # order used by the writeback authority service, before any row capture.
        scope_ids = {proposal.scope_id for proposal, _ in rows[:50]}
        if scope_ids:
            session.execute(
                select(LocalizationScope.id)
                .where(LocalizationScope.id.in_(scope_ids))
                .order_by(LocalizationScope.id)
                .with_for_update()
            ).all()
        items = []
        mapping_destinations = {}
        member_budget = 5000
        text_budget = 20_971_520
        for proposal, key in rows[:50]:
            blocker = None
            count = 0
            mapping_id = None
            published_excerpt = proposed_excerpt = ""
            try:
                if isinstance(proposal, AuthoringRequest):
                    from verboflex.schemas.authoring import AuthoringInput

                    data = AuthoringInput.model_validate(proposal.payload["input"])
                    count = len(data.forms)
                    pending_bytes = sum(len(form.text.encode()) for form in data.forms)
                    current_count = current_bytes = 0
                else:
                    count, pending_bytes = session.execute(
                        select(
                            func.count(),
                            func.coalesce(
                                func.sum(func.octet_length(TranslationProposalValue.proposed_text)),
                                0,
                            ),
                        ).where(TranslationProposalValue.proposal_id == proposal.id)
                    ).one()
                    current_count, current_bytes = session.execute(
                        select(
                            func.count(),
                            func.coalesce(
                                func.sum(func.octet_length(TranslationValue.display_text)), 0
                            ),
                        ).where(
                            TranslationValue.translation_key_id == proposal.translation_key_id,
                            TranslationValue.language == proposal.language,
                        )
                    ).one()
                if (
                    max(count, current_count) > member_budget
                    or pending_bytes + current_bytes > text_budget
                ):
                    raise WritebackRejected(WritebackReason.LIMIT_EXCEEDED)
                member_budget -= max(count, current_count)
                text_budget -= pending_bytes + current_bytes
                authority = capture_writeback_authority(
                    session,
                    selection=WritebackSelection(
                        actor_id, (ProposalSelection(proposal.id, proposal.version),)
                    ),
                    allow_expired_connection=True,
                )
                mapping_id = proposal_mapping(authority, proposal.id).mapping_id
                mapping_destinations.update({d.mapping_id: d for d in destinations(authority)})
                members = authority.proposals[0].members
                count = len(members)
                published_excerpt = members[0].edit.expected_text[:160]
                proposed_excerpt = members[0].edit.replacement_text[:160]
            except WritebackRejected as error:
                blocker = error.reason
            items.append(
                ChangeSetCandidate(
                    proposal_id=proposal.id,
                    version=proposal.version,
                    key=key,
                    language=proposal.language,
                    state=cast(Literal["draft", "approved", "rejected"], proposal.state),
                    value_count=count,
                    can_review=can_request and blocker is None,
                    blocker=blocker,
                    mapping_id=mapping_id,
                    published_excerpt=published_excerpt,
                    proposed_excerpt=proposed_excerpt,
                )
            )
        return ChangeSetCandidatesResponse(
            product_id=product_id,
            active_revision_id=cast(UUID, product.active_revision_id),
            can_request_review=can_request,
            items=items,
            destinations=list(mapping_destinations.values()),
            next_after=rows[49][0].id if len(rows) > 50 else None,
        )


def enqueue_submission_review(review_id: UUID) -> None:
    from verboflex.worker.celery_app import app

    app.send_task(
        "verboflex.submission_review.run",
        args=[str(review_id)],
        serializer="json",
        task_id=str(review_id),
    )


def _load_prepared(session: Session, row: SubmissionReview) -> PreparedSubmissionReview:
    length = session.scalar(
        select(func.octet_length(SubmissionReview.prepared_payload)).where(
            SubmissionReview.id == row.id
        )
    )
    if length is None or length > MAX_PAYLOAD_BYTES:
        raise WritebackRejected(WritebackReason.LIMIT_EXCEEDED)
    try:
        return decode_submission_review(cast(bytes, row.prepared_payload))
    except ValueError:
        raise WritebackRejected(WritebackReason.STALE_BASIS) from None


def _value_count(prepared: PreparedSubmissionReview) -> int:
    return sum(len(p.members) for g in prepared.groups for p in g.prepared.authority.proposals)


def _values(prepared: PreparedSubmissionReview, after: int = 0) -> list[ReviewedValue]:
    members = (
        (g, p, m)
        for g in prepared.groups
        for p in g.prepared.authority.proposals
        for m in p.members
    )
    return [
        ReviewedValue(
            proposal_id=p.proposal_id,
            proposal_version=p.version,
            group_id=g.id,
            key=m.edit.logical_key,
            file_path=m.authority.path,
            value_id=m.value_id,
            language=p.language,
            selector_kind=m.edit.selector.kind,
            selector=json.dumps(m.edit.selector.fields, ensure_ascii=False),
            effective_maximum=p.effective_maximum,
            character_count=grapheme_count(m.edit.replacement_text),
            published_text=m.edit.expected_text,
            proposed_text=m.edit.replacement_text,
        )
        for g, p, m in islice(members, after, after + 25)
    ]


def _record(session: Session, row: SubmissionReview) -> SubmissionReviewResponse:
    state = (
        "accepted"
        if row.accepted_at is not None
        else "expired"
        if datetime.now(UTC) >= row.expires_at
        else row.state
    )
    values: list[ReviewedValue] = []
    groups: list[ReviewedGroup] = []
    destination_rows: list[MappingDestination] = []
    digest = None
    file_count = proposal_count = value_count = 0
    if state in {"ready", "accepted"}:
        prepared = _load_prepared(session, row)
        digest = prepared.content_digest
        values = _values(prepared)
        value_count = _value_count(prepared)
        for group in prepared.groups:
            proof = group.prepared
            file_count += len(proof.files)
            proposal_count += len(proof.authority.proposals)
            destination_rows.extend(
                destinations(
                    proof.authority,
                    tuple(
                        MappingTarget(mapping_id=m.mapping_id, target_branch=group.target_branch)
                        for m in proof.authority.mappings
                    ),
                )
            )
            groups.append(
                ReviewedGroup(
                    id=group.id,
                    repository_id=group.repository_id,
                    workspace=group.workspace,
                    repository_slug=group.repository_slug,
                    target_branch=group.target_branch,
                    target_head=group.target_head,
                    source_branch=group.source_branch,
                    proposal_ids=[p.proposal_id for p in proof.authority.proposals],
                    value_count=sum(len(p.members) for p in proof.authority.proposals),
                    file_count=len(proof.files),
                    sources=[
                        ReviewedSource(
                            mapping_id=m.mapping_id,
                            repository_side=s.repository_side,
                            repository_id=s.repository_id,
                            branch=s.configured_branch,
                            commit_hash=s.commit_hash,
                        )
                        for m in proof.authority.mappings
                        for s in m.sides
                    ],
                )
            )
    return SubmissionReviewResponse(
        id=row.id,
        product_id=row.product_id,
        active_revision_id=row.revision_id,
        state=cast(Literal["queued", "running", "ready", "failed", "expired", "accepted"], state),
        attempt=row.attempt,
        created_at=row.created_at,
        started_at=row.started_at,
        expires_at=row.expires_at,
        error_code=WritebackReason(row.error_code) if row.error_code else None,
        values=values,
        value_count=value_count,
        proposal_count=proposal_count,
        file_count=file_count,
        manifest_digest=digest,
        groups=groups,
        destinations=destination_rows,
        next_values_after=25 if value_count > 25 else None,
        batch_id=session.scalar(
            select(SubmissionBatch.id).where(SubmissionBatch.review_id == row.id)
        )
        if row.accepted_at is not None
        else None,
    )


def create_submission_review(
    session: Session,
    *,
    product_id: UUID,
    actor_id: UUID,
    proposals: list[SelectedProposal],
    targets: tuple[MappingTarget, ...] = (),
    enqueuer: ReviewEnqueuer = enqueue_submission_review,
) -> SubmissionReviewResponse:
    with session.begin():
        product, actor = _product_actor(session, product_id, actor_id, action=True)
        # Serialize intake per product; worker never holds this lock over provider IO.
        session.execute(select(Product.id).where(Product.id == product_id).with_for_update()).one()
        selection = _selection(
            session, product_id=product_id, actor_id=actor_id, proposals=proposals
        )
        authority = capture_writeback_authority(
            session, selection=selection, allow_expired_connection=True
        )
        target_by_mapping = {
            d.mapping_id: d.chosen_target for d in destinations(authority, targets)
        }
        partition_selection(authority, targets=targets)
        frozen = [
            {
                "proposal_id": str(p.proposal_id),
                "expected_version": p.expected_version,
                "mapping_id": str(proposal_mapping(authority, p.proposal_id).mapping_id),
                "target_branch": target_by_mapping[
                    proposal_mapping(authority, p.proposal_id).mapping_id
                ],
            }
            for p in selection.proposals
        ]
        digest = hashlib.sha256(
            json.dumps(
                [str(product.active_revision_id), str(actor_id), actor.token_version, frozen],
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        now = datetime.now(UTC)
        row = session.scalar(
            select(SubmissionReview)
            .where(
                SubmissionReview.product_id == product_id,
                SubmissionReview.actor_id == actor_id,
                SubmissionReview.input_digest == digest,
                SubmissionReview.state.in_(("queued", "running")),
                SubmissionReview.expires_at > now,
            )
            .order_by(SubmissionReview.created_at.desc())
            .limit(1)
            .with_for_update()
        )
        if row is None:
            # A changed selection/target invalidates earlier unaccepted reviews
            # for this actor/product; reservations never silently migrate.
            from sqlalchemy import update

            session.execute(
                update(SubmissionReview)
                .where(
                    SubmissionReview.product_id == product_id,
                    SubmissionReview.actor_id == actor_id,
                    SubmissionReview.accepted_at.is_(None),
                    SubmissionReview.state.in_(("queued", "running", "ready")),
                    SubmissionReview.expires_at > now,
                )
                .values(expires_at=now)
            )
            row = SubmissionReview(
                id=uuid4(),
                actor_id=actor_id,
                actor_token_version=actor.token_version,
                product_id=product_id,
                revision_id=product.active_revision_id,
                selection=frozen,
                input_digest=digest,
                state="queued",
                attempt=1,
                expires_at=now + REVIEW_LIFETIME,
            )
            session.add(row)
            session.flush()
        result = _record(session, row)
    if result.state == "queued":
        # Durable intent survives broker outage; repeated authorized POST
        # redispatches this same UUID, and duplicate delivery is harmless.
        with suppress(Exception):
            enqueuer(result.id)
    return result


def get_submission_review(
    session: Session, *, product_id: UUID, actor_id: UUID, review_id: UUID
) -> SubmissionReviewResponse:
    with session.begin():
        product, _ = _product_actor(session, product_id, actor_id, action=False)
        row = session.scalar(
            select(SubmissionReview).where(
                SubmissionReview.id == review_id, SubmissionReview.product_id == product_id
            )
        )
        if row is None or (
            row.accepted_at is None and row.revision_id != product.active_revision_id
        ):
            raise SubmissionReviewUnavailable("review unavailable")
        return _record(session, row)


def _current(session: Session, row: SubmissionReview) -> WritebackSelection:
    product, actor = _product_actor(session, row.product_id, row.actor_id, action=True)
    if (
        actor.token_version != row.actor_token_version
        or product.active_revision_id != row.revision_id
        or datetime.now(UTC) >= row.expires_at
    ):
        raise WritebackRejected(WritebackReason.STALE_BASIS)
    return _selection(
        session,
        product_id=row.product_id,
        actor_id=row.actor_id,
        proposals=[
            SelectedProposal(
                proposal_id=UUID(str(p["proposal_id"])),
                expected_version=cast(int, p["expected_version"]),
            )
            for p in row.selection
        ],
    )


async def execute_submission_review(
    factory: sessionmaker[Session], *, review_id: UUID, adapter: SubmissionReadAdapter
) -> None:
    with factory.begin() as session:
        product_id = session.scalar(
            select(SubmissionReview.product_id).where(SubmissionReview.id == review_id)
        )
        if product_id is None:
            return
        session.execute(select(Product.id).where(Product.id == product_id).with_for_update()).one()
        row = session.scalar(
            select(SubmissionReview).where(SubmissionReview.id == review_id).with_for_update()
        )
        if row is None or row.state != "queued":
            return
        row.state, row.started_at = "running", datetime.now(UTC)
        attempt = row.attempt
    failure = None
    prepared: PreparedSubmissionReview | None = None
    encoded = None
    try:
        with factory.begin() as session:
            row = session.get(SubmissionReview, review_id)
            assert row is not None
            selection = _current(session, row)
            authority = capture_writeback_authority(
                session, selection=selection, allow_expired_connection=True
            )
            target_map = {
                UUID(str(p["mapping_id"])): str(p["target_branch"]) for p in row.selection
            }
            targets = tuple(
                MappingTarget(mapping_id=mid, target_branch=target)
                for mid, target in target_map.items()
            )
        prepared = await prepare_submission_groups(
            factory, authority=authority, targets=targets, adapter=adapter
        )
        encoded = encode_submission_review(prepared)
    except WritebackRejected as error:
        failure = error.reason
    except SubmissionReviewDenied, SubmissionReviewUnavailable:
        failure = WritebackReason.AUTHORITY_UNAVAILABLE
    except Exception:
        failure = WritebackReason.PROVIDER_UNAVAILABLE
    with factory.begin() as session:
        # Product-first matches intake's lock order; never upgrade a shared lock.
        session.execute(select(Product.id).where(Product.id == product_id).with_for_update()).one()
        row = session.scalar(
            select(SubmissionReview).where(SubmissionReview.id == review_id).with_for_update()
        )
        if row is None or row.state != "running" or row.attempt != attempt:
            return
        if failure is None:
            try:
                _current(session, row)
                if prepared is None:
                    raise WritebackRejected(WritebackReason.STALE_BASIS)
                for group in prepared.groups:
                    fresh = capture_writeback_authority(session, selection=group.prepared.selection)
                    # Capture order is stable; normalize via public group identity
                    # and compare exact frozen authority without provider IO.
                    if fresh != group.prepared.authority:
                        from verboflex.services.writeback import _normalize

                        if _normalize(fresh) != group.prepared.authority:
                            raise WritebackRejected(WritebackReason.STALE_BASIS)
            except SubmissionReviewDenied, SubmissionReviewUnavailable, WritebackRejected:
                failure = WritebackReason.STALE_BASIS
        row.state = "ready" if failure is None else "failed"
        row.error_code = failure.value if failure else None
        row.prepared_payload = encoded if failure is None else None
        row.finished_at = datetime.now(UTC)


def _read_ready(
    session: Session, *, product_id: UUID, actor_id: UUID, review_id: UUID
) -> PreparedSubmissionReview:
    product, _ = _product_actor(session, product_id, actor_id, action=False)
    row = session.scalar(
        select(SubmissionReview).where(
            SubmissionReview.id == review_id, SubmissionReview.product_id == product_id
        )
    )
    if (
        row is None
        or (row.accepted_at is None and row.revision_id != product.active_revision_id)
        or row.state != "ready"
        or (row.accepted_at is None and datetime.now(UTC) >= row.expires_at)
    ):
        raise SubmissionReviewUnavailable("review unavailable")
    return _load_prepared(session, row)


def get_review_files(
    session: Session, *, product_id: UUID, actor_id: UUID, review_id: UUID, after: int = 0
) -> ReviewFilesPage:
    with session.begin():
        prepared = _read_ready(
            session, product_id=product_id, actor_id=actor_id, review_id=review_id
        )
        files = [(g.id, f) for g in prepared.groups for f in g.prepared.files]
        if after < 0 or after > len(files):
            raise SubmissionReviewUnavailable("review unavailable")
        return ReviewFilesPage(
            items=[
                ReviewedFile(
                    index=index,
                    group_id=group_id,
                    path=file.authority.path,
                    before_sha256=file.before_sha256,
                    after_sha256=file.after_sha256,
                    changed_values=len(file.changed_edits),
                )
                for index, (group_id, file) in enumerate(files[after : after + 25], after)
            ],
            next_after=after + 25 if after + 25 < len(files) else None,
        )


def get_review_values(
    session: Session, *, product_id: UUID, actor_id: UUID, review_id: UUID, after: int = 0
) -> ReviewValuesPage:
    with session.begin():
        prepared = _read_ready(
            session, product_id=product_id, actor_id=actor_id, review_id=review_id
        )
        count = _value_count(prepared)
        if after < 0 or after > count:
            raise SubmissionReviewUnavailable("review unavailable")
        return ReviewValuesPage(
            items=_values(prepared, after),
            next_after=after + 25 if after + 25 < count else None,
        )
