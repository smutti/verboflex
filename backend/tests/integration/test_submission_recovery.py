"""Explicit recovery over real frozen intake, with independent durable journal checks."""

import asyncio
import hashlib
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from tests.api.test_submission_reviews import review_api as review_api
from tests.api.test_submissions import ready_api as ready_api
from tests.api.test_submissions import submit
from tests.integration.test_preview_jobs import clean_preview_database as clean_preview_database
from tests.integration.test_preview_jobs import preview_session_factory as preview_session_factory
from tests.integration.test_submission_jobs import Remote
from tests.integration.test_writeback_authority import PreparedSource
from verboflex.integrations.bitbucket.writes import PullRequestReceipt, WriteOutcome
from verboflex.localization.writing.core import WritebackRejected
from verboflex.models.bitbucket_connection import BitbucketConnection
from verboflex.models.review import TranslationProposal
from verboflex.models.submission import ChangeSet, ChangeSetEvent, ChangeSetFile, ChangeSetProof
from verboflex.models.user import User
from verboflex.services import submission_jobs
from verboflex.services.submission_recovery import (
    adopt_verified_admin_receipt,
    effect_summary,
    finalize_known_pre_pr,
    reauthorize_owned_change_set,
    release_verified_terminal_claims,
    request_reconcile,
    request_retry,
)
from verboflex.services.submissions import SubmissionConflict, load_change_set_bundle


@pytest.fixture
def accepted(ready_api):
    result = submit(ready_api)
    assert result.status_code == 202, result.text
    group_id = UUID(result.json()["groups"][0]["id"])
    return ready_api, group_id


def action(accepted, call=request_retry, **kwargs):
    ready, group_id = accepted
    _, seed, factory, _, _, _ = ready
    with factory() as session:
        return call(
            session,
            product_id=seed.product_id,
            actor_id=seed.actor_id,
            change_set_id=group_id,
            expected_attempt=kwargs.pop("expected_attempt", 1),
            **kwargs,
        )


def blocked(accepted):
    ready, group_id = accepted
    with ready[2].begin() as session:
        session.get(ChangeSet, group_id).status = "blocked"


def add_effect(
    session, group_id, *, step="branch", outcome=None, receipt=None, attempt=1, digest="a" * 64
):
    for kind, state in [("send_intent", "intent")] + (
        [("observation", outcome)] if outcome else []
    ):
        session.add(
            ChangeSetEvent(
                change_set_id=group_id,
                attempt=attempt,
                execution_fence=attempt,
                proof_sequence=1,
                event_kind=kind,
                step=step,
                outcome=state,
                request_digest=digest,
                receipt=receipt or {},
            )
        )


def test_explicit_retry_preserves_ids_bytes_and_queues_fresh_proof(accepted):
    ready, group_id = accepted
    factory = ready[2]
    blocked(accepted)
    with factory() as session:
        before = load_change_set_bundle(session, group_id)
    sent = []
    result = action(accepted, enqueuer=sent.append)
    assert result.id == group_id and result.attempt == 2 and result.status == "queued"
    assert sent == [group_id]
    with factory() as session:
        row = session.get(ChangeSet, group_id)
        assert row.execution_fence == 2 and row.dispatch_pending
        assert load_change_set_bundle(session, group_id) == before
        intent = session.scalars(select(ChangeSetEvent)).one()
        assert (intent.event_kind, intent.step, intent.outcome) == (
            "reauthorization",
            "authority",
            "intent",
        )
    with pytest.raises(SubmissionConflict, match="current unclaimed"):
        action(accepted, enqueuer=sent.append)
    assert sent == [group_id]


@pytest.mark.parametrize("mutation", ["stamp", "inactive", "password"])
def test_revoked_original_authority_never_authorizes_retry(accepted, mutation):
    ready, _ = accepted
    blocked(accepted)
    with ready[2].begin() as session:
        actor = session.get(User, ready[1].actor_id)
        if mutation == "stamp":
            actor.token_version += 1
        elif mutation == "inactive":
            actor.is_active = False
        else:
            actor.must_change_password = True
    with pytest.raises((SubmissionConflict, PermissionError)):
        action(accepted, enqueuer=lambda _: pytest.fail("must not dispatch"))


@pytest.mark.parametrize("outcome", [None, "unknown", "conflict"])
def test_unknown_or_inflight_effect_never_releases_claim(accepted, outcome):
    ready, group_id = accepted
    factory = ready[2]
    blocked(accepted)
    with factory.begin() as session:
        add_effect(session, group_id, outcome=outcome)
    with pytest.raises(SubmissionConflict):
        action(accepted, finalize_known_pre_pr)
    with pytest.raises(SubmissionConflict):
        action(accepted, enqueuer=lambda _: pytest.fail("must not retry"))
    with factory() as session:
        assert session.scalars(select(ChangeSetFile)).one().active_claim
        assert session.get(ChangeSet, group_id).claims_released_at is None


def test_never_sent_terminal_releases_claim_and_fences_worker(accepted):
    ready, group_id = accepted
    factory = ready[2]
    identity, bundle = submission_jobs._claim(factory, group_id)
    with factory.begin() as session:
        row = session.get(ChangeSet, group_id)
        row.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        row.status = "blocked"
    result = action(accepted, finalize_known_pre_pr)
    assert result.status == "resolved" and not result.can_retry
    assert not submission_jobs._begin_send(factory, identity, bundle, "branch", "a" * 64)
    with factory() as session:
        row = session.get(ChangeSet, group_id)
        assert row.execution_fence > identity.execution_fence
        assert not session.scalars(select(ChangeSetFile)).one().active_claim
        assert row.claims_released_at is not None


def test_generation_renewal_creates_separate_exact_proof(accepted):
    ready, group_id = accepted
    _, seed, factory, _, _, _ = ready
    blocked(accepted)
    with factory.begin() as session:
        session.get(BitbucketConnection, 1).generation += 1
    action(accepted, enqueuer=lambda _: None)
    identity, bundle = submission_jobs._claim(factory, group_id)
    with factory() as session:
        original_bytes = session.get(ChangeSet, group_id).original_prepared_payload
    fresh_identity, fresh_bundle = asyncio.run(
        reauthorize_owned_change_set(
            factory, identity=identity, bundle=bundle, reads=PreparedSource(seed)
        )
    )
    assert fresh_identity.proof_sequence == 2
    assert fresh_bundle.group == bundle.group
    assert (
        fresh_bundle.proof.authority.connection_generation
        == bundle.proof.authority.connection_generation + 1
    )
    assert fresh_bundle.proof.files == bundle.proof.files
    with factory() as session:
        assert session.get(ChangeSet, group_id).original_prepared_payload == original_bytes
        assert load_change_set_bundle(session, group_id) == fresh_bundle
        proofs = list(session.scalars(select(ChangeSetProof).order_by(ChangeSetProof.sequence)))
        assert len(proofs) == 2 and proofs[0].proof_digest != proofs[1].proof_digest
        assert all(hashlib.sha256(p.prepared_payload).hexdigest() == p.proof_digest for p in proofs)


@pytest.mark.parametrize("mutation", ["version", "bytes", "target", "repository"])
def test_renewal_never_replaces_frozen_bytes_or_changed_authority(accepted, mutation):
    ready, group_id = accepted
    _, seed, factory, _, _, _ = ready
    blocked(accepted)
    with factory.begin() as session:
        session.get(BitbucketConnection, 1).generation += 1
        if mutation == "version":
            session.get(TranslationProposal, seed.proposal_id).version += 1
    action(accepted, enqueuer=lambda _: None)
    identity, bundle = submission_jobs._claim(factory, group_id)
    reader = PreparedSource(seed)
    if mutation == "bytes":
        reader.seed.adapter.files = {
            p: raw.replace(b"old", b"bad") + b" " for p, raw in seed.adapter.files.items()
        }
    elif mutation == "target":
        original = reader.resolve_repository_branch

        async def moved(session, **kwargs):
            value = await original(session, **kwargs)
            return replace(value, commit_hash="b" * 40)

        reader.resolve_repository_branch = moved
    elif mutation == "repository":
        original_metadata = reader.read_repository_metadata

        async def replaced(session, **kwargs):
            value = await original_metadata(session, **kwargs)
            return {**value, "uuid": str(uuid4())}

        reader.read_repository_metadata = replaced
    with pytest.raises(WritebackRejected):
        asyncio.run(
            reauthorize_owned_change_set(factory, identity=identity, bundle=bundle, reads=reader)
        )
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(ChangeSetProof)) == 1
        assert session.get(ChangeSet, group_id).current_proof_sequence == 1


def test_renewal_with_unknown_effect_is_read_only(accepted):
    ready, group_id = accepted
    _, seed, factory, _, _, _ = ready
    with factory.begin() as session:
        row = session.get(ChangeSet, group_id)
        row.status = "reconciling"
        session.get(BitbucketConnection, 1).generation += 1
        session.get(User, seed.actor_id).token_version += 1
        add_effect(session, group_id, outcome="unknown")
    with pytest.raises(SubmissionConflict):
        action(accepted, enqueuer=lambda _: pytest.fail("write retry forbidden"))
    queued = []
    result = action(accepted, request_reconcile, enqueuer=queued.append)
    assert result.status == "reconciling" and result.attempt == 2 and queued == [group_id]
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(ChangeSetProof)) == 1


def test_positive_receipt_survives_later_failed_observation(accepted):
    ready, group_id = accepted
    with ready[2].begin() as session:
        add_effect(
            session,
            group_id,
            outcome="verified",
            receipt={"name": f"verboflex/change-set-{group_id}", "commit_hash": "a" * 40},
        )
        session.add(
            ChangeSetEvent(
                change_set_id=group_id,
                attempt=1,
                execution_fence=1,
                proof_sequence=1,
                event_kind="observation",
                step="branch",
                outcome="unknown",
                request_digest="a" * 64,
                receipt={},
            )
        )
    with ready[2]() as session:
        assert effect_summary(session, session.get(ChangeSet, group_id)).branch == "verified"


def test_conflicting_positive_receipts_never_release(accepted):
    ready, group_id = accepted
    with ready[2].begin() as session:
        add_effect(
            session,
            group_id,
            outcome="verified",
            receipt={"name": "owned", "commit_hash": "a" * 40},
        )
        session.add(
            ChangeSetEvent(
                change_set_id=group_id,
                attempt=1,
                execution_fence=1,
                proof_sequence=1,
                event_kind="observation",
                step="branch",
                outcome="verified",
                request_digest="a" * 64,
                receipt={"name": "owned", "commit_hash": "b" * 40},
            )
        )
    with ready[2]() as session:
        assert effect_summary(session, session.get(ChangeSet, group_id)).branch == "conflict"


def test_verified_commit_pr_never_sent_can_finalize_for_new_version(accepted):
    ready, group_id = accepted
    _, seed, factory, _, _, _ = ready
    remote = Remote(factory, group_id)

    def renew_after_commit(step):
        if step == "commit":
            with factory.begin() as session:
                session.get(BitbucketConnection, 1).generation += 1

    remote.after = renew_after_commit
    asyncio.run(
        submission_jobs.execute_change_set(
            factory, change_set_id=group_id, reads=PreparedSource(seed), writes=remote
        )
    )
    assert remote.calls == ["branch", "commit"]
    result = action(accepted, finalize_known_pre_pr)
    assert result.status == "resolved"
    with factory() as session:
        row = session.get(ChangeSet, group_id)
        assert row.commit_hash and row.branch_commit and row.pr_id is None
        assert not session.scalars(select(ChangeSetFile)).one().active_claim


def test_generation_renewal_after_commit_reauthorizes_same_group(accepted):
    ready, group_id = accepted
    _, seed, factory, _, _, _ = ready
    remote = Remote(factory, group_id)

    def renew_after_commit(step):
        if step == "commit":
            with factory.begin() as session:
                session.get(BitbucketConnection, 1).generation += 1

    remote.after = renew_after_commit
    asyncio.run(
        submission_jobs.execute_change_set(
            factory, change_set_id=group_id, reads=PreparedSource(seed), writes=remote
        )
    )
    action(accepted, enqueuer=lambda _: None)
    remote.after = lambda _: None
    asyncio.run(
        submission_jobs.execute_change_set(
            factory, change_set_id=group_id, reads=PreparedSource(seed), writes=remote
        )
    )
    assert remote.calls == ["branch", "commit", "pull_request"]
    with factory() as session:
        row = session.get(ChangeSet, group_id)
        assert row.status == "succeeded" and row.current_proof_sequence == 2
        assert row.source_branch == f"verboflex/change-set-{group_id}"


def test_terminal_pr_release_requires_matching_positive_evidence(accepted):
    ready, group_id = accepted
    _, seed, factory, _, _, _ = ready
    remote = Remote(factory, group_id)
    asyncio.run(
        submission_jobs.execute_change_set(
            factory, change_set_id=group_id, reads=PreparedSource(seed), writes=remote
        )
    )
    with factory.begin() as session:
        row = session.get(ChangeSet, group_id)
        row.pr_state = "MERGED"
        assert not release_verified_terminal_claims(session, row)
        prior = session.scalars(
            select(ChangeSetEvent).where(
                ChangeSetEvent.step == "pull_request", ChangeSetEvent.event_kind == "observation"
            )
        ).one()
        session.add(
            ChangeSetEvent(
                change_set_id=row.id,
                attempt=prior.attempt,
                execution_fence=prior.execution_fence,
                proof_sequence=prior.proof_sequence,
                event_kind="observation",
                step="pull_request",
                outcome="verified",
                request_digest=prior.request_digest,
                receipt={**prior.receipt, "state": "MERGED"},
            )
        )
        assert release_verified_terminal_claims(session, row)
        assert row.status == "resolved"
    with factory() as session:
        assert not session.scalars(select(ChangeSetFile)).one().active_claim


@pytest.mark.parametrize("positive", [False, True])
def test_admin_adoption_requires_positive_exact_provider_read(accepted, positive):
    ready, group_id = accepted
    _, seed, factory, _, _, _ = ready
    remote = Remote(factory, group_id)
    remote.failure = ("pull_request", "unknown")
    asyncio.run(
        submission_jobs.execute_change_set(
            factory, change_set_id=group_id, reads=PreparedSource(seed), writes=remote
        )
    )
    with factory() as session:
        row = session.get(ChangeSet, group_id)
        receipt = PullRequestReceipt(
            55,
            f"https://bitbucket.org/{row.workspace}/{row.repository_slug}/pull-requests/55",
            "MERGED",
            row.provider_repository_id,
            row.source_branch,
            row.commit_hash,
            row.target_branch,
            row.target_head,
        )

    class Evidence:
        calls = []

        async def read_pull_request(self, session, **kwargs):
            assert not session.in_transaction()
            self.calls.append(kwargs["pull_request_id"])
            return WriteOutcome(
                "verified" if positive else "unknown", "test", receipt if positive else None
            )

    evidence = Evidence()
    call = adopt_verified_admin_receipt(
        factory, actor_id=seed.actor_id, change_set_id=group_id, pull_request_id=55, writes=evidence
    )
    if positive:
        result = asyncio.run(call)
        assert result.status == "resolved" and result.pr_id == 55
        with factory() as session:
            assert (
                session.scalar(
                    select(ChangeSetEvent.id).where(
                        ChangeSetEvent.receipt["action"].as_string() == "admin_receipt_adoption"
                    )
                )
                is not None
            )
    else:
        with pytest.raises(SubmissionConflict):
            asyncio.run(call)
        with factory() as session:
            assert session.get(ChangeSet, group_id).pr_id is None
            assert session.scalars(select(ChangeSetFile)).one().active_claim
    assert evidence.calls == [55]


@pytest.mark.parametrize("terminal_pr", [False, True])
def test_fresh_later_approved_version_admits_after_resolution_but_old_version_stays_claimed(
    accepted, terminal_pr
):
    from types import SimpleNamespace

    from tests.integration.test_confirmed_layout_refresh import _run
    from tests.integration.test_submission_review_jobs import create, get
    from verboflex.auth.principal import Principal
    from verboflex.models.submission import ChangeSetItem
    from verboflex.models.translation import TranslationValue, TranslationValueRevision
    from verboflex.schemas.submissions import CreateSubmissionBatchRequest
    from verboflex.schemas.users import RoleName
    from verboflex.services.submission_reviews import execute_submission_review
    from verboflex.services.submissions import create_submission_batch
    from verboflex.services.translation_reviews import (
        save_translation_proposal,
        transition_translation_proposal,
    )

    ready_api, group_id = accepted
    _, seed, factory, _, _, _ = ready_api
    with factory() as session:
        original = load_change_set_bundle(session, group_id)
    if terminal_pr:
        asyncio.run(
            submission_jobs.execute_change_set(
                factory,
                change_set_id=group_id,
                reads=PreparedSource(seed),
                writes=Remote(factory, group_id),
            )
        )
        with factory.begin() as session:
            row = session.get(ChangeSet, group_id)
            observation = session.scalars(
                select(ChangeSetEvent).where(
                    ChangeSetEvent.step == "pull_request",
                    ChangeSetEvent.event_kind == "observation",
                )
            ).one()
            row.pr_state = "MERGED"
            session.add(
                ChangeSetEvent(
                    change_set_id=row.id,
                    attempt=observation.attempt,
                    execution_fence=observation.execution_fence,
                    proof_sequence=observation.proof_sequence,
                    event_kind="observation",
                    step="pull_request",
                    outcome="verified",
                    request_digest=observation.request_digest,
                    receipt={**observation.receipt, "state": "MERGED"},
                )
            )
            assert release_verified_terminal_claims(session, row)
    else:
        action(accepted, finalize_known_pre_pr)

    def review_and_accept(current_seed, head):
        queued = create(factory, current_seed)
        reader = PreparedSource(current_seed)
        reader.heads[original.group.repository_slug] = head
        asyncio.run(execute_submission_review(factory, review_id=queued.id, adapter=reader))
        ready = get(factory, current_seed, queued.id)
        assert ready.state == "ready", ready.error_code
        with factory() as session:
            return create_submission_batch(
                session,
                product_id=seed.product_id,
                actor_id=seed.actor_id,
                request=CreateSubmissionBatchRequest(
                    review_id=ready.id,
                    expected_review_attempt=ready.attempt,
                    expected_content_digest=ready.manifest_digest,
                    request_key=uuid4(),
                ),
                enqueuer=lambda _: None,
            )

    # Fresh review IDs do not bypass permanent exact-version dedupe after release.
    with pytest.raises(SubmissionConflict) as error:
        review_and_accept(seed, "a" * 40)
    assert error.value.code == "destination_claimed"
    if terminal_pr:
        for file in original.group.prepared.files:
            seed.adapter.files[file.authority.path] = file.content
    seed.adapter.commit_hashes = ["b" * 40]
    refreshed = _run(factory, seed.product_id, seed.mapping_id)
    assert refreshed.state == "current"
    assert refreshed.active_baseline_execution_id != seed.execution_id
    principal = Principal(seed.actor_id, "writer@example.test", "Writer", (RoleName.ADMIN,), False)
    with factory.begin() as session:
        values = list(
            session.scalars(
                select(TranslationValue)
                .where(
                    TranslationValue.translation_key_id == seed.key_id,
                    TranslationValue.language == "it",
                )
                .order_by(TranslationValue.id)
            )
        )
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
                    "proposed_text": "Later",
                }
            )
        current_version = session.get(TranslationProposal, seed.proposal_id).version
        saved = save_translation_proposal(
            session,
            principal=principal,
            translation_group_id=values[0].id,
            expected_version=current_version,
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
    later_seed = SimpleNamespace(**{**vars(seed), "version": approved.version})
    batch = review_and_accept(later_seed, "b" * 40)
    assert batch.groups[0].id != group_id
    with factory() as session:
        assert load_change_set_bundle(session, group_id) == original
        newer = load_change_set_bundle(session, batch.groups[0].id)
        assert (
            newer.group.prepared.authority.mappings[0].execution_id
            == refreshed.active_baseline_execution_id
        )
        assert session.get(TranslationProposal, seed.proposal_id).version == approved.version
        assert {i.proposal_version for i in session.scalars(select(ChangeSetItem))} == {
            seed.version,
            approved.version,
        }
        assert sum(f.active_claim for f in session.scalars(select(ChangeSetFile))) == 1
