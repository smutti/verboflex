"""Bind structural proposals into the existing immutable submission proof."""

import hashlib
from uuid import uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from verboflex.localization.graphemes import grapheme_count
from verboflex.localization.importing.core import canonical_selector_bytes
from verboflex.localization.writing.core import WritebackReason, WritebackRejected
from verboflex.models.authoring import AuthoringRequest
from verboflex.models.translation import LocalizationScope, TranslationKey
from verboflex.models.translation_constraint import TranslationConstraint
from verboflex.schemas.authoring import AuthoringInput
from verboflex.services.translation_authoring import (
    AuthoringError,
    _existing,
    operations,
    resolve_file,
    validate_complete,
)
from verboflex.services.translation_constraints import project_effective_constraint
from verboflex.services.writeback_authority import (
    CapturedConstraint,
    CapturedFile,
    CapturedMapping,
    CapturedMember,
    CapturedProposal,
)


def capture_addition(
    session: Session,
    row: AuthoringRequest,
    expected_version: int,
    scope: LocalizationScope,
    mapping: CapturedMapping,
) -> tuple[CapturedProposal, tuple[CapturedFile, ...]]:
    fresh = session.scalar(
        select(AuthoringRequest)
        .where(AuthoringRequest.id == row.id)
        .with_for_update(read=True)
        .execution_options(populate_existing=True)
    )
    if fresh is None or fresh.version != expected_version or fresh.state != "approved":
        raise WritebackRejected(WritebackReason.STALE_BASIS)
    row = fresh
    try:
        data = AuthoringInput.model_validate(row.payload["input"])
        current, ref, parser = resolve_file(session, scope, data)
        inserts = operations(data, parser.format)
        validate_complete(session, scope, data, parser.format)
        _existing(session, scope, ref, data, inserts)
    except AuthoringError, ValueError, KeyError:
        raise WritebackRejected(WritebackReason.STALE_BASIS) from None
    if (
        current != mapping
        or row.payload.get("path") != ref.path
        or row.payload.get("sha256") != ref.sha256
    ):
        raise WritebackRejected(WritebackReason.STALE_BASIS)
    parent = session.get(TranslationKey, row.parent_key_id) if row.parent_key_id else None
    rules = (
        session.scalars(
            select(TranslationConstraint)
            .where(
                TranslationConstraint.translation_key_id == row.parent_key_id,
                TranslationConstraint.language.in_({data.language, mapping.base_language}),
            )
            .order_by(TranslationConstraint.language)
        ).all()
        if parent
        else []
    )
    by_language = {r.language: r for r in rules}
    maximum = project_effective_constraint(
        language=data.language,
        base_language=mapping.base_language,
        explicit_constraint=by_language.get(data.language),
        base_constraint=by_language.get(mapping.base_language),
    ).maximum
    if data.max_chars is not None:
        maximum = data.max_chars if maximum is None else min(maximum, data.max_chars)
    if any(
        not op.replacement_text.strip()
        or (maximum is not None and grapheme_count(op.replacement_text) > maximum)
        for op in inserts
    ):
        raise WritebackRejected(WritebackReason.INVALID_REPLACEMENT)
    members = []
    for op in inserts:
        digest = hashlib.sha256(canonical_selector_bytes(op.selector)).hexdigest()
        members.append(CapturedMember(uuid5(row.id, digest), 1, digest, 0, ref.sha256, ref, op))
    proposal = CapturedProposal(
        row.id,
        row.version,
        row.parent_key_id or row.id,
        row.language,
        parent.constraint_generation if parent else 0,
        tuple(CapturedConstraint(r.id, r.language, r.version, r.max_chars) for r in rules),
        maximum,
        tuple(members),
    )
    return proposal, (CapturedFile(mapping.mapping_id, ref, parser, inserts),)
