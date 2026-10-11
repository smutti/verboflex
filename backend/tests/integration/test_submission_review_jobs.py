"""The review worker uses real imported authority and immutable source bytes."""

# ruff: noqa: F811

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest
from alembic.config import Config
from sqlalchemy import func, select

from alembic import command
from tests.integration.test_preview_jobs import (
    BACKEND_ROOT,
    clean_preview_database,  # noqa: F401
    preview_session_factory,  # noqa: F401
)
from tests.integration.test_writeback_authority import PreparedSource, seed_writeback_authority
from verboflex.localization.writing.core import WritebackRejected
from verboflex.models.import_job import ImportJob
from verboflex.models.review import TranslationProposal, TranslationProposalValue
from verboflex.models.role import Role
from verboflex.models.submission import SubmissionReview
from verboflex.models.user import User
from verboflex.schemas.submissions import SelectedProposal
from verboflex.services import submission_codec, submission_reviews
from verboflex.services.submission_codec import (
    decode_prepared_writeback,
    decode_submission_review,
    encode_prepared_writeback,
    encode_submission_review,
)
from verboflex.services.submission_reviews import (
    create_submission_review,
    execute_submission_review,
    get_submission_review,
)
from verboflex.services.writeback import revalidate_writeback_authority


def create(factory, seed, enqueuer=lambda _: None):
    with factory() as session:
        return create_submission_review(
            session,
            product_id=seed.product_id,
            actor_id=seed.actor_id,
            proposals=[
                SelectedProposal(proposal_id=seed.proposal_id, expected_version=seed.version)
            ],
            enqueuer=enqueuer,
        )


def get(factory, seed, review_id):
    with factory() as session:
        return get_submission_review(
            session, product_id=seed.product_id, actor_id=seed.actor_id, review_id=review_id
        )


def approve_base_language(factory, seed):
    """Add a second complete proposal through the public review service."""
    from verboflex.auth.principal import Principal
    from verboflex.models.translation import TranslationValue, TranslationValueRevision
    from verboflex.schemas.users import RoleName
    from verboflex.services.translation_reviews import (
        save_translation_proposal,
        transition_translation_proposal,
    )

    principal = Principal(seed.actor_id, "writer@example.test", "Writer", (RoleName.ADMIN,), False)
    with factory.begin() as session:
        values = list(
            session.scalars(
                select(TranslationValue)
                .where(
                    TranslationValue.translation_key_id == seed.key_id,
                    TranslationValue.language == "en",
                )
                .order_by(TranslationValue.id)
            )
        )
        assert len(values) == 2
        proposed = []
        for value in values:
            revision = session.scalars(
                select(TranslationValueRevision)
                .where(TranslationValueRevision.value_id == value.id)
                .order_by(TranslationValueRevision.revision_number.desc())
            ).first()
            proposed.append(
                {
                    "translation_value_id": value.id,
                    "selector_version": value.selector_version,
                    "selector_digest": value.selector_digest,
                    "basis_revision_number": revision.revision_number,
                    "basis_digest": revision.revision_digest,
                    "proposed_text": "Good",
                }
            )
        saved = save_translation_proposal(
            session,
            principal=principal,
            translation_group_id=values[0].id,
            expected_version=0,
            values=proposed,
        )
        approved = transition_translation_proposal(
            session,
            principal=principal,
            translation_group_id=values[0].id,
            expected_version=saved.version,
            target_state="approved",
            reason=None,
        )
        proposal = session.scalar(
            select(TranslationProposal).where(
                TranslationProposal.translation_key_id == seed.key_id,
                TranslationProposal.language == "en",
            )
        )
        return SelectedProposal(proposal_id=proposal.id, expected_version=approved.version)


def test_multiple_complete_proposals_share_one_target_review(preview_session_factory, monkeypatch):
    factory = preview_session_factory
    seed = seed_writeback_authority(factory, monkeypatch)
    extra = approve_base_language(factory, seed)
    selected = [
        extra,
        SelectedProposal(proposal_id=seed.proposal_id, expected_version=seed.version),
    ]
    with factory() as session:
        queued = create_submission_review(
            session,
            product_id=seed.product_id,
            actor_id=seed.actor_id,
            proposals=selected,
            enqueuer=lambda _: None,
        )
    asyncio.run(
        execute_submission_review(factory, review_id=queued.id, adapter=PreparedSource(seed))
    )
    ready = get(factory, seed, queued.id)
    assert ready.state == "ready", ready.error_code
    assert ready.proposal_count == 2 and ready.value_count == 4 and ready.file_count == 2
    assert len(ready.groups) == 1 and ready.groups[0].target_branch == "release/1"
    with factory() as session:
        permuted = create_submission_review(
            session,
            product_id=seed.product_id,
            actor_id=seed.actor_id,
            proposals=list(reversed(selected)),
            enqueuer=lambda _: None,
        )
    assert permuted.id != ready.id and permuted.state == "queued"
    asyncio.run(
        execute_submission_review(factory, review_id=permuted.id, adapter=PreparedSource(seed))
    )
    assert get(factory, seed, permuted.id).manifest_digest == ready.manifest_digest


def test_worker_prepares_complete_review_and_duplicate_delivery_is_noop(
    preview_session_factory, monkeypatch
):
    factory = preview_session_factory
    seed = seed_writeback_authority(factory, monkeypatch)
    row = create(factory, seed)
    reader = PreparedSource(seed)
    asyncio.run(execute_submission_review(factory, review_id=row.id, adapter=reader))
    ready = get(factory, seed, row.id)
    assert ready.state == "ready", ready.error_code
    assert len(ready.values) == 2 and all(v.proposed_text == "Ok" for v in ready.values)
    assert {v.published_text for v in ready.values} == {"Ciao", "Saluti"}
    assert ready.file_count == 1 and ready.manifest_digest
    requests = len(reader.sessions)
    asyncio.run(execute_submission_review(factory, review_id=row.id, adapter=reader))
    assert len(reader.sessions) == requests
    with factory() as session:
        persisted = session.get(SubmissionReview, row.id)
        review = decode_submission_review(persisted.prepared_payload)
        assert encode_submission_review(review) == persisted.prepared_payload
        proof = review.groups[0].prepared
        assert session.get(TranslationProposal, seed.proposal_id).version == seed.version
    asyncio.run(revalidate_writeback_authority(factory, prepared=proof, adapter=reader))


def test_broker_failure_preserves_same_queued_uuid_for_redispatch(
    preview_session_factory, monkeypatch
):
    factory = preview_session_factory
    seed = seed_writeback_authority(factory, monkeypatch)
    failed = Mock(side_effect=RuntimeError("private broker detail"))
    original = create(factory, seed, failed)
    queued = []
    again = create(factory, seed, queued.append)
    assert original.id == again.id and again.state == "queued" and queued == [original.id]
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(SubmissionReview)) == 1


@pytest.mark.parametrize("mutation", ["role", "token", "disabled", "password", "version"])
def test_worker_rechecks_current_actor_and_proposal_before_provider(
    preview_session_factory, monkeypatch, mutation
):
    factory = preview_session_factory
    seed = seed_writeback_authority(factory, monkeypatch)
    row = create(factory, seed)
    with factory.begin() as session:
        user = session.get(User, seed.actor_id)
        if mutation == "role":
            user.roles = [session.scalars(select(Role).where(Role.name == "viewer")).one()]
        elif mutation == "token":
            user.token_version += 1
        elif mutation == "disabled":
            user.is_active = False
        elif mutation == "password":
            user.must_change_password = True
        else:
            session.get(TranslationProposal, seed.proposal_id).version += 1
    reader = PreparedSource(seed)
    asyncio.run(execute_submission_review(factory, review_id=row.id, adapter=reader))
    assert reader.sessions == []
    with factory() as session:
        stored = session.get(SubmissionReview, row.id)
        assert stored.state == "failed" and stored.prepared_payload is None


@pytest.mark.parametrize("mutation", ["draft", "rejected", "partial"])
def test_non_complete_approved_selection_never_creates_intent(
    preview_session_factory, monkeypatch, mutation
):
    factory = preview_session_factory
    seed = seed_writeback_authority(factory, monkeypatch)
    with factory.begin() as session:
        if mutation == "partial":
            session.delete(session.scalars(select(TranslationProposalValue)).first())
        else:
            session.get(TranslationProposal, seed.proposal_id).state = mutation
    with pytest.raises(WritebackRejected):
        create(factory, seed)
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(SubmissionReview)) == 0


def test_concurrent_duplicate_worker_cannot_prepare_twice(preview_session_factory, monkeypatch):
    factory = preview_session_factory
    seed = seed_writeback_authority(factory, monkeypatch)
    row = create(factory, seed)
    first, second = PreparedSource(seed), PreparedSource(seed)
    first.pause = True
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            lambda: asyncio.run(execute_submission_review(factory, review_id=row.id, adapter=first))
        )
        assert first.arrived.wait(10)
        try:
            asyncio.run(execute_submission_review(factory, review_id=row.id, adapter=second))
            assert second.sessions == []
        finally:
            first.release.set()
        future.result(15)
    assert get(factory, seed, row.id).state == "ready"


def test_codec_is_closed_bounded_and_checks_before_base64_decode(
    preview_session_factory, monkeypatch
):
    factory = preview_session_factory
    seed = seed_writeback_authority(factory, monkeypatch)
    row = create(factory, seed)
    asyncio.run(execute_submission_review(factory, review_id=row.id, adapter=PreparedSource(seed)))
    with factory() as session:
        raw = session.get(SubmissionReview, row.id).prepared_payload
    assert raw is not None
    raw = encode_prepared_writeback(decode_submission_review(raw).groups[0].prepared)
    data = json.loads(raw)
    assert data["version"] == 1
    for invalid in [
        b'{"version":1,"version":1,"prepared":{}}',
        b'{"version":true,"prepared":{}}',
        b'{"version":1,"prepared":{"record":"os.system","fields":{}}}',
    ]:
        with pytest.raises(ValueError, match="payload rejected"):
            decode_prepared_writeback(invalid)
    data["prepared"]["fields"]["files"]["tuple"][0]["fields"]["content"] = {
        "bytes": "A" * (4 * ((1_048_576 + 2) // 3) + 4)
    }
    # No binary field may be decoded after the offending one. Its preceding
    # original_bytes is within bounds; inspect call sizes rather than allocation.
    real = submission_codec.base64.b64decode
    spy = Mock(wraps=real)
    monkeypatch.setattr(submission_codec.base64, "b64decode", spy)
    with pytest.raises(ValueError):
        decode_prepared_writeback(json.dumps(data).encode())
    assert all(len(call.args[0]) <= 4 * ((1_048_576 + 2) // 3) for call in spy.call_args_list)


def test_expired_review_is_safe_and_does_not_restart(preview_session_factory, monkeypatch):
    factory = preview_session_factory
    seed = seed_writeback_authority(factory, monkeypatch)
    row = create(factory, seed)
    with factory.begin() as session:
        session.get(SubmissionReview, row.id).expires_at = datetime.now(UTC) - timedelta(seconds=1)
    assert get(factory, seed, row.id).state == "expired"
    reader = PreparedSource(seed)
    asyncio.run(execute_submission_review(factory, review_id=row.id, adapter=reader))
    assert reader.sessions == []


def test_migration_down_up_preserves_existing_imports_and_proposals(
    preview_session_factory, monkeypatch
):
    factory = preview_session_factory
    seed = seed_writeback_authority(factory, monkeypatch)
    config = Config(BACKEND_ROOT / "alembic.ini")
    config.set_main_option(
        "sqlalchemy.url", factory.kw["bind"].url.render_as_string(hide_password=False)
    )
    command.downgrade(config, "0029_bitbucket_workspace")
    command.upgrade(config, "head")
    with factory() as session:
        assert session.get(TranslationProposal, seed.proposal_id).version == seed.version
        assert session.scalar(select(func.count()).select_from(ImportJob)) == 1


def test_enqueue_is_only_opaque_uuid(monkeypatch):
    from uuid import uuid4

    from verboflex.worker.celery_app import app

    spy = Mock()
    monkeypatch.setattr(app, "send_task", spy)
    identity = uuid4()
    submission_reviews.enqueue_submission_review(identity)
    assert spy.call_args.args == ("verboflex.submission_review.run",)
    assert spy.call_args.kwargs["args"] == [str(identity)]
    assert spy.call_args.kwargs["serializer"] == "json"


def test_role_loss_during_provider_io_cannot_publish_ready(preview_session_factory, monkeypatch):
    factory = preview_session_factory
    seed = seed_writeback_authority(factory, monkeypatch)
    row = create(factory, seed)
    reader = PreparedSource(seed)
    reader.pause = True
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            lambda: asyncio.run(
                execute_submission_review(factory, review_id=row.id, adapter=reader)
            )
        )
        assert reader.arrived.wait(10)
        try:
            with factory.begin() as session:
                session.get(User, seed.actor_id).roles = [
                    session.scalars(select(Role).where(Role.name == "viewer")).one()
                ]
        finally:
            reader.release.set()
        future.result(15)
    with factory() as session:
        assert session.get(SubmissionReview, row.id).state == "failed"


def test_invalid_queue_identity_never_opens_provider(monkeypatch):
    from verboflex.worker import submission_tasks

    forbidden = Mock(side_effect=AssertionError("invalid UUID cannot acquire provider"))
    monkeypatch.setattr(submission_tasks, "_execute", forbidden)
    submission_tasks.run_submission_review("not-an-opaque-uuid")
    forbidden.assert_not_called()


@pytest.mark.parametrize("mismatch", [False, True, "attributes"])
def test_target_head_may_differ_only_with_exact_file_bytes(
    preview_session_factory, monkeypatch, mismatch
):
    from verboflex.integrations.bitbucket.client import BitbucketBranch

    factory = preview_session_factory
    seed = seed_writeback_authority(factory, monkeypatch)

    class TargetSource(PreparedSource):
        async def resolve_repository_branch(self, session, **kwargs):
            branch = await super().resolve_repository_branch(session, **kwargs)
            return BitbucketBranch(branch.name, "b" * 40) if branch.name == "release/1" else branch

        async def read_repository_source_file(self, session, **kwargs):
            raw = await super().read_repository_source_file(session, **kwargs)
            return (
                raw.replace(b"Ciao", b"Else")
                if mismatch is True and kwargs["commit_hash"] == "b" * 40
                else raw
            )

        async def read_repository_source_metadata(self, session, **kwargs):
            from dataclasses import replace

            metadata = await super().read_repository_source_metadata(session, **kwargs)
            return (
                replace(metadata, attributes=("binary",))
                if (mismatch == "attributes" and kwargs["commit_hash"] == "b" * 40)
                else metadata
            )

    row = create(factory, seed)
    asyncio.run(execute_submission_review(factory, review_id=row.id, adapter=TargetSource(seed)))
    result = get(factory, seed, row.id)
    if mismatch:
        assert result.state == "failed" and result.error_code == "source_file_changed"
    else:
        assert result.state == "ready" and result.groups[0].target_head == "b" * 40


def test_forbidden_target_never_creates_review(preview_session_factory, monkeypatch):
    from verboflex.schemas.submissions import MappingTarget

    factory = preview_session_factory
    seed = seed_writeback_authority(factory, monkeypatch)
    with factory() as session, pytest.raises(WritebackRejected):
        create_submission_review(
            session,
            product_id=seed.product_id,
            actor_id=seed.actor_id,
            proposals=[
                SelectedProposal(proposal_id=seed.proposal_id, expected_version=seed.version)
            ],
            targets=(MappingTarget(mapping_id=seed.mapping_id, target_branch="forbidden"),),
            enqueuer=lambda _: None,
        )
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(SubmissionReview)) == 0


def test_grouped_review_files_and_values_are_authorized_pages(preview_session_factory, monkeypatch):
    from verboflex.services.submission_reviews import get_review_files, get_review_values

    factory = preview_session_factory
    seed = seed_writeback_authority(factory, monkeypatch)
    row = create(factory, seed)
    asyncio.run(execute_submission_review(factory, review_id=row.id, adapter=PreparedSource(seed)))
    with factory() as session:
        files = get_review_files(
            session, product_id=seed.product_id, actor_id=seed.actor_id, review_id=row.id
        )
    with factory() as session:
        values = get_review_values(
            session, product_id=seed.product_id, actor_id=seed.actor_id, review_id=row.id
        )
    assert len(files.items) == 1 and files.items[0].changed_values == 2
    assert len(values.items) == 2 and values.next_after is None


def test_separate_review_writes_only_translations_and_keeps_keys_basis(
    preview_session_factory, monkeypatch
):
    factory = preview_session_factory
    seed = seed_writeback_authority(factory, monkeypatch, separate=True)
    row = create(factory, seed)
    asyncio.run(execute_submission_review(factory, review_id=row.id, adapter=PreparedSource(seed)))
    ready = get(factory, seed, row.id)
    assert ready.state == "ready"
    assert len(ready.groups) == 1 and ready.groups[0].repository_slug == "translations-repository"
    assert {s.repository_side for s in ready.groups[0].sources} == {"keys", "translations"}


def test_explicit_review_after_unchanged_import_refresh_uses_fresh_authority(
    preview_session_factory, monkeypatch
):
    from tests.integration.test_confirmed_layout_refresh import _run

    factory = preview_session_factory
    seed = seed_writeback_authority(factory, monkeypatch)
    original = create(factory, seed)
    asyncio.run(
        execute_submission_review(factory, review_id=original.id, adapter=PreparedSource(seed))
    )
    assert get(factory, seed, original.id).state == "ready"
    refreshed = _run(factory, seed.product_id, seed.mapping_id)
    assert (
        refreshed.state == "current" and refreshed.active_baseline_execution_id != seed.execution_id
    )
    with factory() as session:
        assert session.get(TranslationProposal, seed.proposal_id).version == seed.version
    again = create(factory, seed)
    assert again.id != original.id and again.state == "queued"
    assert get(factory, seed, original.id).state == "expired"
    asyncio.run(
        execute_submission_review(factory, review_id=again.id, adapter=PreparedSource(seed))
    )
    ready = get(factory, seed, again.id)
    assert ready.state == "ready"
    with factory() as session:
        proof = decode_submission_review(session.get(SubmissionReview, again.id).prepared_payload)
        assert (
            proof.groups[0].prepared.authority.mappings[0].execution_id
            == refreshed.active_baseline_execution_id
        )


def test_complete_32_member_review_pages_without_truncating_scope(
    preview_session_factory, monkeypatch
):
    from verboflex.services.submission_reviews import get_review_values

    factory = preview_session_factory
    seed = seed_writeback_authority(factory, monkeypatch, members=32)
    row = create(factory, seed)
    asyncio.run(execute_submission_review(factory, review_id=row.id, adapter=PreparedSource(seed)))
    ready = get(factory, seed, row.id)
    assert ready.state == "ready"
    assert ready.value_count == 32 and len(ready.values) == 25 and ready.next_values_after == 25
    with factory() as session:
        last = get_review_values(
            session, product_id=seed.product_id, actor_id=seed.actor_id, review_id=row.id, after=25
        )
    assert len(last.items) == 7 and last.next_after is None
    assert {v.value_id for v in ready.values + last.items} == set(seed.value_ids)
    assert all(
        v.group_id == ready.groups[0].id
        and v.proposal_version == seed.version
        and v.character_count == 2
        for v in last.items
    )
