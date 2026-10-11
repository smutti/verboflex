"""Structural drafts use real imported authority and the normal submission proof."""

from dataclasses import replace
from uuid import uuid4

import pytest
from sqlalchemy import select

from tests.integration.test_preview_jobs import (
    clean_preview_database,  # noqa: F401
    preview_session_factory,  # noqa: F401
)
from tests.integration.test_writeback_authority import seed_writeback_authority
from tests.legacy_product_fixtures import mirror_fixture_role
from verboflex.localization.importing.registry import parse_canonical_snapshot
from verboflex.localization.writing.core import SourceFileSnapshot, WritebackRejected
from verboflex.localization.writing.registry import render_file
from verboflex.models.authoring import AuthoringRequest
from verboflex.models.translation import LocalizationScope
from verboflex.schemas.authoring import AuthoringInput
from verboflex.services import translation_authoring as authoring
from verboflex.services.submission_reviews import list_change_set_candidates
from verboflex.services.writeback import ProposalSelection, WritebackSelection
from verboflex.services.writeback_authority import capture_writeback_authority

__all__ = ["clean_preview_database", "preview_session_factory"]


def draft(factory, seed, **changes):
    with factory.begin() as session:
        options = authoring.destinations(
            session, product_id=seed.product_id, actor_id=seed.actor_id
        )
        destination = next(d for d in options.items if "it" in d.languages)
    data = AuthoringInput(
        scope_id=destination.scope_id,
        execution_id=destination.execution_id,
        file_position=destination.file_position,
        key="new_key",
        language="it",
        forms=[{"text": "Nuova stringa"}],
    )
    return data.model_copy(update=changes)


def test_new_key_draft_approval_candidate_and_exact_render(preview_session_factory, monkeypatch):
    factory = preview_session_factory
    seed = seed_writeback_authority(factory, monkeypatch)
    data = draft(factory, seed)
    request_id = uuid4()
    with factory.begin() as session:
        saved = authoring.save(
            session,
            product_id=seed.product_id,
            actor_id=seed.actor_id,
            request_id=request_id,
            data=data,
        )
        assert saved.version == 1
        assert (
            authoring.save(
                session,
                product_id=seed.product_id,
                actor_id=seed.actor_id,
                request_id=request_id,
                data=data,
            ).version
            == 1
        )
    selection = WritebackSelection(seed.actor_id, (ProposalSelection(request_id, 1),))
    with factory.begin() as session, pytest.raises(WritebackRejected):
        capture_writeback_authority(session, selection=selection)
    with factory.begin() as session:
        approved = authoring.transition(
            session,
            product_id=seed.product_id,
            actor_id=seed.actor_id,
            request_id=request_id,
            expected_version=1,
            state="approved",
        )
        assert approved.version == 2
    with factory() as session:
        page = list_change_set_candidates(
            session, product_id=seed.product_id, actor_id=seed.actor_id
        )
        candidate = next(c for c in page.items if c.proposal_id == request_id)
        assert candidate.can_review and candidate.proposed_excerpt == "Nuova stringa"
    with factory.begin() as session:
        captured = capture_writeback_authority(
            session,
            selection=WritebackSelection(seed.actor_id, (ProposalSelection(request_id, 2),)),
        )
        file = captured.files[0]
        content = seed.adapter.files[file.authority.path]
        source = SourceFileSnapshot(file.authority, replace(file.parser_input, content=content))
        rendered = render_file(source, file.edits)
        values = parse_canonical_snapshot(
            replace(file.parser_input, content=rendered.content)
        ).values
        assert any(v.logical_key == "new_key" and v.display_text == "Nuova stringa" for v in values)


def test_authoring_duplicate_stale_and_foreign_destination_rejected(
    preview_session_factory, monkeypatch
):
    factory = preview_session_factory
    seed = seed_writeback_authority(factory, monkeypatch)
    data = draft(factory, seed)
    request_id = uuid4()
    with factory.begin() as session:
        authoring.save(
            session,
            product_id=seed.product_id,
            actor_id=seed.actor_id,
            request_id=request_id,
            data=data,
        )
    for bad in (
        data.model_copy(update={"execution_id": uuid4()}),
        data.model_copy(update={"key": "hello"}),
        data.model_copy(update={"language": "de"}),
        data.model_copy(update={"expected_version": 5}),
    ):
        with factory.begin() as session, pytest.raises(authoring.AuthoringError):
            authoring.save(
                session,
                product_id=seed.product_id,
                actor_id=seed.actor_id,
                request_id=request_id,
                data=bad,
            )
    with factory.begin() as session, pytest.raises(authoring.AuthoringError, match="draft already"):
        authoring.save(
            session,
            product_id=seed.product_id,
            actor_id=seed.actor_id,
            request_id=uuid4(),
            data=data,
        )
    with factory.begin() as session:
        assert session.scalar(select(AuthoringRequest.version)) == 1
        assert (
            session.get(LocalizationScope, data.scope_id).active_execution_id == seed.execution_id
        )


def test_new_key_proof_survives_codec_and_import_consumes_only_matching_draft(
    preview_session_factory, monkeypatch
):
    import asyncio

    from tests.integration.test_confirmed_layout_refresh import _run
    from tests.integration.test_writeback_authority import PreparedSource
    from verboflex.models.translation import TranslationKey
    from verboflex.models.translation_constraint import TranslationConstraint
    from verboflex.services.submission_codec import (
        decode_prepared_writeback,
        encode_prepared_writeback,
    )
    from verboflex.services.writeback import prepare_writeback

    factory = preview_session_factory
    seed = seed_writeback_authority(factory, monkeypatch)
    data = draft(factory, seed, max_chars=40)
    request_id = uuid4()
    with factory.begin() as session:
        authoring.save(
            session,
            product_id=seed.product_id,
            actor_id=seed.actor_id,
            request_id=request_id,
            data=data,
        )
        authoring.transition(
            session,
            product_id=seed.product_id,
            actor_id=seed.actor_id,
            request_id=request_id,
            expected_version=1,
            state="approved",
        )
    proof = asyncio.run(
        prepare_writeback(
            factory,
            selection=WritebackSelection(seed.actor_id, (ProposalSelection(request_id, 2),)),
            adapter=PreparedSource(seed),
        )
    )
    assert decode_prepared_writeback(encode_prepared_writeback(proof)) == proof
    # Same-content refresh must not erase a structural proposal.
    _run(factory, seed.product_id, seed.mapping_id)
    with factory.begin() as session:
        assert session.get(AuthoringRequest, request_id) is not None
    for file in proof.files:
        seed.adapter.files[file.authority.path] = file.content
    seed.adapter.commit_hashes = ["b" * 40]
    _run(factory, seed.product_id, seed.mapping_id)
    with factory.begin() as session:
        assert session.get(AuthoringRequest, request_id) is None
        key = session.scalar(select(TranslationKey).where(TranslationKey.raw_key == data.key))
        assert key is not None
        rule = session.scalar(
            select(TranslationConstraint).where(TranslationConstraint.translation_key_id == key.id)
        )
        assert rule.max_chars == 40


def test_incomplete_plural_is_draft_but_cannot_be_approved(preview_session_factory, monkeypatch):
    from verboflex.schemas.authoring import AuthoringForm

    factory = preview_session_factory
    seed = seed_writeback_authority(factory, monkeypatch)
    data = draft(factory, seed, kind="plural", forms=[AuthoringForm(form="one", text="%d file")])
    request_id = uuid4()
    with factory.begin() as session:
        authoring.save(
            session,
            product_id=seed.product_id,
            actor_id=seed.actor_id,
            request_id=request_id,
            data=data,
        )
    with factory.begin() as session, pytest.raises(authoring.AuthoringError, match="plural forms"):
        authoring.transition(
            session,
            product_id=seed.product_id,
            actor_id=seed.actor_id,
            request_id=request_id,
            expected_version=1,
            state="approved",
        )


def test_viewer_cannot_save_and_translator_cannot_approve(preview_session_factory, monkeypatch):
    from verboflex.models.role import Role
    from verboflex.models.user import User

    factory = preview_session_factory
    seed = seed_writeback_authority(factory, monkeypatch)
    data = draft(factory, seed)
    request_id = uuid4()
    common = dict(product_id=seed.product_id, actor_id=seed.actor_id, request_id=request_id)
    with factory.begin() as session:
        session.get(User, seed.actor_id).roles = [
            session.scalar(select(Role).where(Role.name == "viewer"))
        ]
        mirror_fixture_role(session, session.get(User, seed.actor_id).id)
    with factory.begin() as session, pytest.raises(authoring.AuthoringError) as error:
        authoring.save(session, **common, data=data)
    assert error.value.status == 403
    with factory.begin() as session:
        session.get(User, seed.actor_id).roles = [
            session.scalar(select(Role).where(Role.name == "translator"))
        ]
        mirror_fixture_role(session, session.get(User, seed.actor_id).id)
    with factory.begin() as session:
        assert authoring.save(session, **common, data=data).state == "draft"
    with factory.begin() as session, pytest.raises(authoring.AuthoringError) as error:
        authoring.transition(session, **common, expected_version=1, state="approved")
    assert error.value.status == 403


def test_new_key_uses_normal_durable_branch_commit_pr_job(preview_session_factory, monkeypatch):
    from tests.integration.test_submission_jobs import Remote, accepted, run
    from verboflex.models.submission import ChangeSet

    factory = preview_session_factory
    seed = seed_writeback_authority(factory, monkeypatch)
    data = draft(factory, seed)
    entry_id = uuid4()
    with factory.begin() as session:
        authoring.save(
            session,
            product_id=seed.product_id,
            actor_id=seed.actor_id,
            request_id=entry_id,
            data=data,
        )
        authoring.transition(
            session,
            product_id=seed.product_id,
            actor_id=seed.actor_id,
            request_id=entry_id,
            expected_version=1,
            state="approved",
        )
    seed.proposal_id, seed.version = entry_id, 2
    _, reader, change_set_id = accepted(factory, monkeypatch, seed=seed)
    remote = Remote(factory, change_set_id)
    run(factory, change_set_id, reader, remote)
    assert remote.calls == ["branch", "commit", "pull_request"]
    with factory.begin() as session:
        assert session.get(ChangeSet, change_set_id).status == "succeeded"
        assert session.get(AuthoringRequest, entry_id).state == "approved"


def test_oversize_authoring_batch_rejected_before_payload_hydration(
    preview_session_factory, monkeypatch
):
    from sqlalchemy import event

    from verboflex.services import writeback_authority

    factory = preview_session_factory
    seed = seed_writeback_authority(factory, monkeypatch)
    data = draft(factory, seed)
    entry_id = uuid4()
    with factory.begin() as session:
        authoring.save(
            session,
            product_id=seed.product_id,
            actor_id=seed.actor_id,
            request_id=entry_id,
            data=data,
        )
    loaded = []

    def note_load(row, context):
        loaded.append(row.id)

    event.listen(AuthoringRequest, "load", note_load)
    monkeypatch.setattr(writeback_authority, "MAX_CANONICAL_AGGREGATE_BYTES", 100)
    try:
        with factory.begin() as session, pytest.raises(WritebackRejected) as error:
            capture_writeback_authority(
                session,
                selection=WritebackSelection(seed.actor_id, (ProposalSelection(entry_id, 1),)),
            )
        assert error.value.reason.value == "limit_exceeded"
        assert loaded == []
    finally:
        event.remove(AuthoringRequest, "load", note_load)
