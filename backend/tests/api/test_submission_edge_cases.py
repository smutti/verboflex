"""Missing-input, terminal-action and independently prepared intake edge contracts."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from tests.api.test_submission_reviews import review_api as review_api
from tests.api.test_submissions import ready_api as ready_api
from tests.api.test_submissions import submit
from tests.integration.test_confirmed_layout_refresh import _run
from tests.integration.test_preview_jobs import clean_preview_database as clean_preview_database
from tests.integration.test_preview_jobs import preview_session_factory as preview_session_factory
from tests.integration.test_submission_review_jobs import create, get
from tests.integration.test_writeback_authority import PreparedSource
from verboflex.auth.principal import Principal
from verboflex.models.repository import Repository
from verboflex.models.review import TranslationProposal
from verboflex.models.role import Role
from verboflex.models.submission import ChangeSet, ChangeSetFile, ChangeSetItem, SubmissionBatch
from verboflex.models.translation import TranslationKey, TranslationValue, TranslationValueRevision
from verboflex.models.user import User
from verboflex.schemas.submissions import CreateSubmissionBatchRequest
from verboflex.schemas.users import RoleName
from verboflex.services.submission_reviews import execute_submission_review
from verboflex.services.submissions import SubmissionConflict, create_submission_batch
from verboflex.services.translation_reviews import (
    save_translation_proposal,
    transition_translation_proposal,
)


@pytest.mark.parametrize("body", [{}, {"proposals": None}, {"proposals": []}, None])
def test_null_missing_or_empty_selection_rejects_before_enqueue(review_api, body):
    client, seed, sent, factory = review_api
    response = client.post(f"/api/v1/products/{seed.product_id}/submission-reviews", json=body)
    assert response.status_code == 422
    assert sent == []
    from verboflex.models.submission import SubmissionReview

    with factory() as session:
        assert session.scalar(select(func.count()).select_from(SubmissionReview)) == 0


def test_retry_missing_and_succeeded_group_never_enqueues(ready_api):
    client, seed, factory, _, _, sent = ready_api
    missing = f"/api/v1/products/{seed.product_id}/change-sets/{uuid4()}/retry"
    assert client.post(missing, json={"expected_attempt": 1}).status_code == 404
    assert sent == []
    group = submit(ready_api).json()["groups"][0]
    with factory.begin() as session:
        row = session.get(ChangeSet, UUID(group["id"]))
        row.status, row.stage = "succeeded", "complete"
    sent.clear()
    path = f"/api/v1/products/{seed.product_id}/change-sets/{group['id']}"
    before = client.get(path).json()
    for _ in range(2):
        response = client.post(path + "/retry", json={"expected_attempt": 1})
        assert response.status_code == 409 and response.json()["code"] == "retry_unavailable"
    assert sent == [] and client.get(path).json() == before


def _second_approved_proposal(factory, seed):
    """Use a genuine refresh and public save/approve, not forged frozen proof."""
    seed.adapter.files = {
        path: raw.replace(b"</resources>", b'<string name="second">Second</string></resources>')
        for path, raw in seed.adapter.files.items()
    }
    seed.adapter.commit_hashes = ["b" * 40]
    assert _run(factory, seed.product_id, seed.mapping_id).state == "current"
    actor_id = uuid4()
    principal = Principal(actor_id, f"{actor_id}@example.test", "Other", (RoleName.ADMIN,), False)
    with factory.begin() as session:
        session.add(
            User(
                id=actor_id,
                email=principal.email,
                display_name="Other",
                hashed_password="unused",
                must_change_password=False,
                roles=[session.scalar(select(Role).where(Role.name == "admin"))],
            )
        )
    with factory.begin() as session:
        value = session.scalar(
            select(TranslationValue)
            .join(TranslationKey)
            .where(
                TranslationKey.product_id == seed.product_id,
                TranslationKey.raw_key == "second",
                TranslationValue.language == "it",
            )
        )
        revision = session.scalar(
            select(TranslationValueRevision)
            .where(TranslationValueRevision.value_id == value.id)
            .order_by(TranslationValueRevision.revision_number.desc())
            .limit(1)
        )
        saved = save_translation_proposal(
            session,
            principal=principal,
            translation_group_id=value.id,
            expected_version=0,
            values=[
                {
                    "translation_value_id": value.id,
                    "selector_version": value.selector_version,
                    "selector_digest": value.selector_digest,
                    "basis_revision_number": revision.revision_number,
                    "basis_digest": revision.revision_digest,
                    "proposed_text": "Second revised",
                }
            ],
        )
        approved = transition_translation_proposal(
            session,
            principal=principal,
            translation_group_id=value.id,
            target_state="approved",
            expected_version=saved.version,
            reason=None,
        )
        proposal = session.scalar(
            select(TranslationProposal).where(
                TranslationProposal.translation_key_id == value.translation_key_id,
                TranslationProposal.language == "it",
            )
        )
        return SimpleNamespace(
            **{
                **vars(seed),
                "actor_id": actor_id,
                "proposal_id": proposal.id,
                "version": approved.version,
            }
        )


def test_independent_ready_reviews_competing_for_same_file_have_one_claim_owner(review_api):
    _, seed, _, factory = review_api
    other = _second_approved_proposal(factory, seed)
    assert other.proposal_id != seed.proposal_id and other.actor_id != seed.actor_id
    ready = []
    for selected in (seed, other):
        queued = create(factory, selected)
        reader = PreparedSource(selected)
        with factory() as session:
            reader.heads = {
                r.repository_slug: "b" * 40 for r in session.scalars(select(Repository))
            }
        asyncio.run(execute_submission_review(factory, review_id=queued.id, adapter=reader))
        prepared = get(factory, selected, queued.id)
        assert prepared.state == "ready", prepared.error_code
        ready.append(prepared)
    assert ready[0].id != ready[1].id and ready[0].groups[0].id != ready[1].groups[0].id
    assert all(
        get(factory, selected, prepared.id).state == "ready"
        for selected, prepared in zip((seed, other), ready, strict=True)
    )
    barrier, sent = Barrier(2), []

    def accept(selected, prepared):
        request = CreateSubmissionBatchRequest(
            review_id=prepared.id,
            expected_review_attempt=prepared.attempt,
            expected_content_digest=prepared.manifest_digest,
            request_key=uuid4(),
        )
        barrier.wait(timeout=5)
        try:
            with factory() as session:
                return create_submission_batch(
                    session,
                    product_id=selected.product_id,
                    actor_id=selected.actor_id,
                    request=request,
                    enqueuer=sent.append,
                ).id
        except SubmissionConflict as error:
            assert error.code == "destination_claimed"
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(accept, selected, prepared)
            for selected, prepared in zip((seed, other), ready, strict=True)
        ]
        outcomes = [future.result(timeout=15) for future in futures]
    assert sum(outcome is not None for outcome in outcomes) == 1 and len(sent) == 1
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(SubmissionBatch)) == 1
        assert session.scalar(select(func.count()).select_from(ChangeSet)) == 1
        assert session.scalar(select(func.count()).select_from(ChangeSetItem)) == 1
        files = list(session.scalars(select(ChangeSetFile)))
        assert len(files) == 1 and files[0].active_claim and files[0].change_set_id == sent[0]
