"""PostgreSQL guards for immutable accepted evidence and physical destination claims."""

import asyncio
import hashlib
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from tests.api.test_submission_reviews import review_api as review_api
from tests.api.test_submissions import ready_api as ready_api
from tests.api.test_submissions import submit
from tests.integration.test_preview_jobs import (
    clean_preview_database as clean_preview_database,
)
from tests.integration.test_preview_jobs import (
    preview_session_factory as preview_session_factory,
)
from verboflex.models.repository import Repository
from verboflex.models.review import TranslationProposal
from verboflex.models.submission import (
    ChangeSet,
    ChangeSetEvent,
    ChangeSetFile,
    ChangeSetItem,
    ChangeSetProof,
)
from verboflex.services.submissions import load_change_set_bundle


def test_migration_down_up_preserves_existing_imports_and_proposals(
    preview_session_factory, monkeypatch
):
    from alembic.config import Config

    from alembic import command
    from tests.integration.test_preview_jobs import BACKEND_ROOT
    from tests.integration.test_submission_review_jobs import create, get
    from tests.integration.test_writeback_authority import PreparedSource, seed_writeback_authority
    from verboflex.models.import_job import ImportJob
    from verboflex.models.submission import SubmissionReview
    from verboflex.services.submission_reviews import execute_submission_review

    factory = preview_session_factory
    seed = seed_writeback_authority(factory, monkeypatch)
    queued = create(factory, seed)
    asyncio.run(
        execute_submission_review(factory, review_id=queued.id, adapter=PreparedSource(seed))
    )
    ready = get(factory, seed, queued.id)
    assert ready.state == "ready"
    config = Config(BACKEND_ROOT / "alembic.ini")
    config.set_main_option(
        "sqlalchemy.url", factory.kw["bind"].url.render_as_string(hide_password=False)
    )
    command.downgrade(config, "0030_submission_reviews")
    command.upgrade(config, "head")
    with factory() as session:
        assert session.get(TranslationProposal, seed.proposal_id).version == seed.version
        assert session.scalars(select(ImportJob)).one().product_id == seed.product_id
        assert session.get(SubmissionReview, queued.id).accepted_at is None
    assert get(factory, seed, queued.id) == ready


@pytest.fixture
def accepted(ready_api):
    response = submit(ready_api)
    assert response.status_code == 202, response.text
    return ready_api, UUID(response.json()["groups"][0]["id"])


def _event(group_id):
    return ChangeSetEvent(
        change_set_id=group_id,
        attempt=1,
        execution_fence=1,
        proof_sequence=1,
        event_kind="send_intent",
        step="branch",
        outcome="intent",
        request_digest="a" * 64,
        receipt={},
    )


def _clone_group(session, group, *, local_repository_id=None):
    # Deliberately create a second local alias for the same provider UUID. Physical
    # claims must stay unique even when local catalogue coordinates differ.
    local_id = local_repository_id or uuid4()
    if local_repository_id is None:
        session.add(Repository(id=local_id, workspace="alias", repository_slug=f"repo-{local_id}"))
        session.flush()
    values = {column.key: getattr(group, column.key) for column in inspect(ChangeSet).columns}
    new_id = uuid4()
    values.update(
        id=new_id,
        repository_id=local_id,
        source_branch=f"verboflex/change-set-{new_id}",
    )
    copied = ChangeSet(**values)
    session.add(copied)
    session.flush()
    return copied


def _clone_file(file, group, **changes):
    values = {
        column.key: getattr(file, column.key)
        for column in inspect(ChangeSetFile).columns
        if column.key != "path_digest"
    }
    values.update(id=uuid4(), change_set_id=group.id, repository_id=group.repository_id)
    values.update(changes)
    return ChangeSetFile(**values)


def test_intake_preserves_remote_uuid_separately_from_local_coordinates(accepted):
    ready, group_id = accepted
    _, seed, factory, _, _, _ = ready
    with factory() as session:
        group = session.get(ChangeSet, group_id)
        expected = uuid5(NAMESPACE_URL, f"{group.workspace}/{group.repository_slug}")
        assert group.provider_repository_id == expected != group.repository_id
        bundle = load_change_set_bundle(session, group_id)
        assert bundle.group.provider_repository_id == expected
        assert bundle.group.repository_id == group.repository_id
        assert bundle.actor_id == seed.actor_id
        assert bundle.proof == bundle.group.prepared
        for model in (ChangeSetItem, ChangeSetFile):
            row = session.scalars(select(model).where(model.change_set_id == group_id)).one()
            assert row.provider_repository_id == expected
            assert row.repository_id == group.repository_id
        item = session.scalars(select(ChangeSetItem)).one()
        assert len(item.members) == group.value_count == 2


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE submission_batches SET content_digest = repeat('0',64)",
        "UPDATE change_sets SET manifest_digest = repeat('0',64)",
        "UPDATE change_sets SET provider_repository_id = gen_random_uuid()",
        "UPDATE change_set_items SET language = 'zz'",
        "UPDATE change_set_files SET path = path || '.evil'",
        "UPDATE change_set_proofs SET connection_generation = connection_generation + 1",
        "UPDATE change_set_events SET outcome = 'unknown'",
        "UPDATE submission_reviews SET expires_at = expires_at + interval '1 day'",
        "DELETE FROM submission_batches",
        "DELETE FROM change_sets",
        "DELETE FROM change_set_items",
        "DELETE FROM change_set_files",
        "DELETE FROM change_set_proofs",
        "DELETE FROM change_set_events",
        "DELETE FROM submission_reviews",
    ],
)
def test_accepted_identity_and_evidence_reject_update_and_delete(accepted, statement):
    ready, group_id = accepted
    factory = ready[2]
    with factory.begin() as session:
        session.add(_event(group_id))
    with factory() as session, pytest.raises(DBAPIError, match="immutable"), session.begin():
        session.execute(text(statement))


def test_one_send_intent_per_attempt_and_step_is_a_database_invariant(accepted):
    ready, group_id = accepted
    factory = ready[2]
    with factory.begin() as session:
        session.add(_event(group_id))
    with (
        factory() as session,
        pytest.raises(IntegrityError, match="uq_change_set_send_intent"),
        session.begin(),
    ):
        session.add(_event(group_id))
        session.flush()


def test_unknown_destination_claim_cannot_be_released(accepted):
    ready, group_id = accepted
    factory = ready[2]
    with factory.begin() as session:
        session.get(ChangeSet, group_id).status = "reconciling"
    with factory() as session, pytest.raises(DBAPIError, match="unresolved"), session.begin():
        session.execute(text("UPDATE change_set_files SET active_claim = false"))


def test_exact_remote_target_path_is_exclusive_across_local_repository_aliases(accepted):
    ready, group_id = accepted
    factory = ready[2]
    with (
        factory() as session,
        pytest.raises(IntegrityError, match="uq_change_set_active_file"),
        session.begin(),
    ):
        group = session.get(ChangeSet, group_id)
        clone = _clone_group(session, group)
        file = session.scalars(select(ChangeSetFile)).one()
        session.add(_clone_file(file, clone))
        session.flush()


def test_positive_terminal_resolution_releases_file_but_never_exact_proposal_claim(accepted):
    ready, group_id = accepted
    factory = ready[2]
    with factory.begin() as session:
        group = session.get(ChangeSet, group_id)
        group.pr_state = "MERGED"
        group.claims_released_at = datetime.now(UTC)
        session.flush()
        file = session.scalars(select(ChangeSetFile)).one()
        file.active_claim = False
        session.flush()
        clone = _clone_group(session, group)
        session.add(_clone_file(file, clone, active_claim=True))
        session.flush()
        clone_id = clone.id
    with (
        factory() as session,
        pytest.raises(IntegrityError, match="uq_change_set_proposal_claim"),
        session.begin(),
    ):
        original = session.scalars(select(ChangeSetItem)).one()
        clone = session.get(ChangeSet, clone_id)
        values = {c.key: getattr(original, c.key) for c in inspect(ChangeSetItem).columns}
        values.update(change_set_id=clone.id, repository_id=clone.repository_id)
        session.add(ChangeSetItem(**values))
        session.flush()


def test_path_digest_handles_long_unicode_and_backslash_without_index_truncation(accepted):
    ready, group_id = accepted
    factory = ready[2]
    path = "locale/" + "界" * 4000 + "\\file.json"
    with factory.begin() as session:
        group = session.get(ChangeSet, group_id)
        file = session.scalars(select(ChangeSetFile)).one()
        row = _clone_file(file, group, path=path)
        session.add(row)
        session.flush()
        assert row.path_digest == hashlib.sha256(path.encode("utf-8")).digest()


def test_database_hash_checks_reject_mismatched_file_or_proof_bytes(accepted):
    ready, group_id = accepted
    factory = ready[2]
    with factory() as session, pytest.raises(IntegrityError, match="bytes_hashes"), session.begin():
        group = session.get(ChangeSet, group_id)
        file = session.scalars(select(ChangeSetFile)).one()
        session.add(_clone_file(file, group, path="other.json", content=b"tampered"))
        session.flush()
    with factory() as session, pytest.raises(IntegrityError, match="proof_digest"), session.begin():
        session.add(
            ChangeSetProof(
                change_set_id=group_id,
                sequence=2,
                connection_generation=1,
                proof_digest="0" * 64,
                prepared_payload=b"tampered",
            )
        )
        session.flush()


def test_later_proposal_edits_cannot_rewrite_accepted_bytes_or_frozen_members(accepted):
    ready, group_id = accepted
    _, seed, factory, _, _, _ = ready
    with factory() as session:
        before = load_change_set_bundle(session, group_id)
        members = session.scalars(select(ChangeSetItem)).one().members
    with factory.begin() as session:
        proposal = session.get(TranslationProposal, seed.proposal_id)
        proposal.version += 1
        proposal.state = "draft"
    with factory() as session:
        assert load_change_set_bundle(session, group_id) == before
        assert session.scalars(select(ChangeSetItem)).one().members == members
    # Recovering an already committed request returns its historical receipt.
    assert submit(ready).status_code == 202
