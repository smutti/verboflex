"""Atomic explicit submission over real Approved imports and frozen reviews."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from tests.api.test_submission_reviews import review_api as review_api
from tests.integration.test_preview_jobs import (
    clean_preview_database as clean_preview_database,
)
from tests.integration.test_preview_jobs import (
    preview_session_factory as preview_session_factory,
)
from tests.integration.test_submission_review_jobs import create, get
from tests.integration.test_writeback_authority import PreparedSource
from verboflex.services.submission_reviews import execute_submission_review


def submit(ready_api, body=None):
    client, seed, _, _, original, _ = ready_api
    return client.post(
        f"/api/v1/products/{seed.product_id}/submission-batches", json=body or original
    )


@pytest.fixture
def ready_api(review_api, monkeypatch):
    client, seed, _, factory = review_api
    queued = create(factory, seed)
    asyncio.run(
        execute_submission_review(factory, review_id=queued.id, adapter=PreparedSource(seed))
    )
    ready = get(factory, seed, queued.id)
    assert ready.state == "ready"
    sent = []
    monkeypatch.setattr(client.app.state, "submission_enqueuer", sent.append, raising=False)
    body = {
        "review_id": str(ready.id),
        "expected_review_attempt": ready.attempt,
        "expected_content_digest": ready.manifest_digest,
        "request_key": str(uuid4()),
    }
    return client, seed, factory, ready, body, sent


def test_intake_adopts_review_group_reservations_and_recovers_same_key(ready_api):
    client, seed, _, ready, body, sent = ready_api
    base = f"/api/v1/products/{seed.product_id}"
    response = client.post(f"{base}/submission-batches", json=body)
    assert response.status_code == 202, response.text
    batch = response.json()
    assert [g["id"] for g in batch["groups"]] == [str(g.id) for g in ready.groups]
    assert [g["source_branch"] for g in batch["groups"]] == [g.source_branch for g in ready.groups]
    assert [str(value) for value in sent] == [g["id"] for g in batch["groups"]]
    again = client.post(f"{base}/submission-batches", json=body)
    assert again.status_code == 202 and again.json() == batch
    recovered = client.get(f"{base}/submission-batches/by-key/{body['request_key']}")
    assert recovered.status_code == 200 and recovered.json() == batch
    assert "prepared_payload" not in str(batch) and "ciphertext" not in str(batch)


def test_stale_content_or_version_never_accepts_a_subset(ready_api):
    client, seed, _, _, body, sent = ready_api
    base = f"/api/v1/products/{seed.product_id}"
    body["expected_content_digest"] = "0" * 64
    response = client.post(f"{base}/submission-batches", json=body)
    assert response.status_code == 409
    assert sent == []


def test_known_unsent_failure_exposes_actor_authorized_retry(ready_api):
    from uuid import UUID

    from verboflex.models.submission import ChangeSet

    client, seed, factory, _, _, _ = ready_api
    group_id = submit(ready_api).json()["groups"][0]["id"]
    with factory.begin() as session:
        row = session.get(ChangeSet, UUID(group_id))
        row.status = "failed"
        row.error_code = "provider_not_sent"
    detail = client.get(f"/api/v1/products/{seed.product_id}/change-sets/{group_id}")
    assert detail.status_code == 200
    assert detail.json()["can_retry"] is True


def test_retry_route_is_database_only_and_fences_duplicate_confirmation(ready_api, monkeypatch):
    from uuid import UUID

    from verboflex.models.submission import ChangeSet
    from verboflex.services import submission_recovery

    client, seed, factory, _, _, sent = ready_api
    group_id = submit(ready_api).json()["groups"][0]["id"]
    with factory.begin() as session:
        session.get(ChangeSet, UUID(group_id)).status = "failed"

    async def forbidden(*args, **kwargs):
        pytest.fail("HTTP recovery actions must not read or mutate the provider")

    monkeypatch.setattr(submission_recovery, "prepare_writeback", forbidden)
    base = f"/api/v1/products/{seed.product_id}/change-sets/{group_id}"
    result = client.post(base + "/retry", json={"expected_attempt": 1})
    assert result.status_code == 202, result.text
    assert result.json()["id"] == group_id and result.json()["attempt"] == 2
    assert len(sent) == 2
    assert client.post(base + "/retry", json={"expected_attempt": 1}).status_code == 409
    assert len(sent) == 2


def test_unknown_outcome_exposes_only_readonly_reconciliation(ready_api, monkeypatch):
    from uuid import UUID

    from verboflex.models.submission import ChangeSet, ChangeSetEvent

    client, seed, factory, _, _, _ = ready_api
    group_id = submit(ready_api).json()["groups"][0]["id"]
    with factory.begin() as session:
        session.get(ChangeSet, UUID(group_id)).status = "reconciling"
        session.add(
            ChangeSetEvent(
                change_set_id=UUID(group_id),
                attempt=1,
                execution_fence=1,
                proof_sequence=1,
                event_kind="send_intent",
                step="branch",
                outcome="intent",
                request_digest="a" * 64,
                receipt={},
            )
        )
    sent = []
    monkeypatch.setattr(
        client.app.state, "submission_reconciliation_enqueuer", sent.append, raising=False
    )
    base = f"/api/v1/products/{seed.product_id}/change-sets/{group_id}"
    state = client.get(base).json()
    assert state["can_reconcile"] and not state["can_retry"] and not state["can_finalize"]
    assert state["recovery_reason"] == "reconciliation_required"
    for action in ("retry", "finalize"):
        assert client.post(base + "/" + action, json={"expected_attempt": 1}).status_code == 409
    response = client.post(base + "/reconcile", json={"expected_attempt": 1})
    assert response.status_code == 202 and sent == [UUID(group_id)]


def test_recovery_routes_enforce_product_roles_and_strict_attempt(ready_api):
    from uuid import UUID

    from verboflex.models.role import Role
    from verboflex.models.submission import ChangeSet
    from verboflex.models.user import User

    client, seed, factory, _, _, _ = ready_api
    group_id = submit(ready_api).json()["groups"][0]["id"]
    with factory.begin() as session:
        session.get(ChangeSet, UUID(group_id)).status = "blocked"
    base = f"/api/v1/products/{seed.product_id}/change-sets/{group_id}"
    assert client.post(base + "/retry", json={"expected_attempt": True}).status_code == 422
    assert (
        client.post(
            base.replace(str(seed.product_id), str(uuid4())) + "/retry",
            json={"expected_attempt": 1},
        ).status_code
        == 404
    )
    with factory.begin() as session:
        session.get(User, seed.actor_id).roles = [
            session.scalar(select(Role).where(Role.name == "viewer"))
        ]
    for action in ("retry", "reconcile", "finalize"):
        assert client.post(base + "/" + action, json={"expected_attempt": 1}).status_code == 403
    assert not client.get(base).json()["can_retry"]


def test_never_sent_finalization_route_returns_irreversible_resolution(ready_api):
    client, seed, _, _, _, _ = ready_api
    group_id = submit(ready_api).json()["groups"][0]["id"]
    base = f"/api/v1/products/{seed.product_id}/change-sets/{group_id}"
    result = client.post(base + "/finalize", json={"expected_attempt": 1})
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "resolved"
    assert not result.json()["can_retry"] and not result.json()["can_reconcile"]
    assert client.post(base + "/retry", json={"expected_attempt": 1}).status_code == 409


def test_same_key_changed_payload_conflicts_without_second_dispatch(ready_api):
    assert submit(ready_api).status_code == 202
    changed = {**ready_api[4], "expected_content_digest": "0" * 64}
    result = submit(ready_api, changed)
    assert result.status_code == 409 and result.json()["code"] == "idempotency_conflict"
    assert len(ready_api[5]) == 1


def test_new_key_cannot_accept_the_same_reserved_review_twice(ready_api):
    assert submit(ready_api).status_code == 202
    assert submit(ready_api, {**ready_api[4], "request_key": str(uuid4())}).status_code == 409
    assert len(ready_api[5]) == 1


@pytest.mark.parametrize("mutation", ["version", "state", "token", "generation", "expiry"])
def test_changed_local_authority_prevents_all_admission(ready_api, mutation):
    from verboflex.models.bitbucket_connection import BitbucketConnection
    from verboflex.models.review import TranslationProposal
    from verboflex.models.submission import SubmissionBatch
    from verboflex.models.user import User

    _, seed, factory, _, _, sent = ready_api
    with factory.begin() as session:
        if mutation == "version":
            session.get(TranslationProposal, seed.proposal_id).version += 1
        elif mutation == "state":
            session.get(TranslationProposal, seed.proposal_id).state = "draft"
        elif mutation == "token":
            session.get(User, seed.actor_id).token_version += 1
        elif mutation == "generation":
            session.get(BitbucketConnection, 1).generation += 1
        else:
            session.get(BitbucketConnection, 1).provider_expires_at = datetime.now(UTC) - timedelta(
                seconds=1
            )
    result = submit(ready_api)
    assert result.status_code == 409, result.text
    assert sent == []
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(SubmissionBatch)) == 0


def test_generation_change_before_acceptance_requires_review(ready_api):
    from verboflex.models.bitbucket_connection import BitbucketConnection

    client, seed, factory, ready, _, _ = ready_api
    with factory.begin() as session:
        session.get(BitbucketConnection, 1).generation += 1
    assert submit(ready_api).status_code == 409
    response = client.get(f"/api/v1/products/{seed.product_id}/submission-reviews/{ready.id}")
    assert response.json()["state"] == "expired"


def test_intake_role_loss_denies_but_accepted_read_remains_authorized(ready_api):
    from verboflex.models.role import Role
    from verboflex.models.user import User

    client, seed, factory, _, body, _ = ready_api
    batch = submit(ready_api).json()
    with factory.begin() as session:
        session.get(User, seed.actor_id).roles = [
            session.scalar(select(Role).where(Role.name == "viewer"))
        ]
    assert submit(ready_api).status_code == 403
    base = f"/api/v1/products/{seed.product_id}"
    recovered = client.get(f"{base}/submission-batches/by-key/{body['request_key']}").json()
    assert recovered["id"] == batch["id"]
    capabilities = {"can_retry", "can_reconcile", "can_finalize", "recovery_reason"}
    assert [
        {key: value for key, value in group.items() if key not in capabilities}
        for group in recovered["groups"]
    ] == [
        {key: value for key, value in group.items() if key not in capabilities}
        for group in batch["groups"]
    ]
    assert not recovered["groups"][0]["can_finalize"]


def test_accepted_review_survives_deadline_and_new_review_and_preserves_paging(
    ready_api, monkeypatch
):
    from verboflex.models.submission import SubmissionReview
    from verboflex.services import submission_reviews

    client, seed, factory, ready, _, _ = ready_api
    batch = submit(ready_api).json()
    with factory() as session:
        expiry = session.get(SubmissionReview, ready.id).expires_at

    class Later(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.now(tz) + timedelta(hours=1)

    monkeypatch.setattr(submission_reviews, "datetime", Later)
    create(factory, seed)
    base = f"/api/v1/products/{seed.product_id}/submission-reviews/{ready.id}"
    response = client.get(base)
    assert response.json()["state"] == "accepted"
    assert response.json()["batch_id"] == batch["id"]
    assert response.json()["manifest_digest"] == ready.manifest_digest
    assert client.get(base + "/files").status_code == 200
    assert client.get(base + "/values").status_code == 200
    with factory() as session:
        assert session.get(SubmissionReview, ready.id).expires_at == expiry


def test_broker_failure_preserves_discoverable_pending_groups(ready_api, monkeypatch):
    from verboflex.models.submission import ChangeSet

    client, _, factory, _, _, _ = ready_api

    def unavailable(_):
        raise RuntimeError("private broker details")

    monkeypatch.setattr(client.app.state, "submission_enqueuer", unavailable)
    result = submit(ready_api)
    assert result.status_code == 202
    with factory() as session:
        rows = list(session.scalars(select(ChangeSet)))
        assert len(rows) == 1 and rows[0].dispatch_pending


def test_late_database_conflict_rolls_back_all_intake_evidence(ready_api, monkeypatch):
    from verboflex.models.submission import (
        ChangeSet,
        ChangeSetFile,
        ChangeSetItem,
        ChangeSetProof,
        SubmissionBatch,
        SubmissionReview,
    )
    from verboflex.services import submissions

    _, _, factory, ready, _, sent = ready_api
    persist = submissions._persist_group

    def conflict_after_freezing(session, batch, group):
        persist(session, batch, group)
        session.flush()
        frozen = session.scalars(select(ChangeSetFile)).one()
        # A real database claim conflict after every snapshot table was inserted.
        session.add(
            ChangeSetFile(
                id=uuid4(),
                change_set_id=group.id,
                repository_id=group.repository_id,
                provider_repository_id=group.provider_repository_id,
                target_branch=group.target_branch,
                path=frozen.path,
                original_bytes=frozen.original_bytes,
                content=frozen.content,
                before_sha256=frozen.before_sha256,
                after_sha256=frozen.after_sha256,
                attributes=frozen.attributes,
            )
        )
        session.flush()

    monkeypatch.setattr(submissions, "_persist_group", conflict_after_freezing)
    result = submit(ready_api)
    assert result.status_code == 409 and result.json()["code"] == "destination_claimed"
    assert sent == []
    with factory() as session:
        for model in (SubmissionBatch, ChangeSet, ChangeSetItem, ChangeSetFile, ChangeSetProof):
            assert session.scalar(select(func.count()).select_from(model)) == 0
        assert session.get(SubmissionReview, ready.id).accepted_at is None


@pytest.mark.parametrize("same_key", [False, True])
def test_concurrent_confirmation_has_one_durable_batch(ready_api, same_key):
    from verboflex.models.submission import ChangeSet, SubmissionBatch
    from verboflex.schemas.submissions import CreateSubmissionBatchRequest
    from verboflex.services.submissions import SubmissionConflict, create_submission_batch

    _, seed, factory, _, body, _ = ready_api
    barrier = Barrier(2)

    def accept(key):
        request = CreateSubmissionBatchRequest.model_validate({**body, "request_key": key})
        barrier.wait(timeout=5)
        try:
            with factory() as session:
                return create_submission_batch(
                    session,
                    product_id=seed.product_id,
                    actor_id=seed.actor_id,
                    request=request,
                    enqueuer=lambda _: None,
                ).id
        except SubmissionConflict:
            return None

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(accept, body["request_key"]),
            executor.submit(accept, body["request_key"] if same_key else str(uuid4())),
        ]
        results = [future.result(timeout=10) for future in futures]
    assert len({result for result in results if result is not None}) == 1
    assert sum(result is not None for result in results) == (2 if same_key else 1)
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(SubmissionBatch)) == 1
        assert session.scalar(select(func.count()).select_from(ChangeSet)) == 1
