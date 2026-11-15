"""Synthetic PostgreSQL proof of all-pages approval and atomic grouped delivery."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from tests.api.test_branch_workflow import configure
from tests.api.test_submission_reviews import review_api as review_api
from tests.integration.test_branch_workflow import Remote, run
from tests.integration.test_preview_jobs import clean_preview_database as clean_preview_database
from tests.integration.test_preview_jobs import preview_session_factory as preview_session_factory
from tests.integration.test_translation_authoring import draft
from tests.legacy_product_fixtures import mirror_fixture_role
from verboflex.models.authoring import AuthoringRequest
from verboflex.models.authoring_approval import AuthoringApproval
from verboflex.models.branch_workflow import BranchJob
from verboflex.models.role import Role
from verboflex.models.user import User
from verboflex.services import authoring_approvals as bulk
from verboflex.services import translation_authoring as authoring


def seed_drafts(factory, seed, count=2):
    data = draft(factory, seed)
    ids = []
    with factory.begin() as session:
        for index in range(count):
            request_id = uuid4()
            ids.append(request_id)
            authoring.save(
                session,
                product_id=seed.product_id,
                actor_id=seed.actor_id,
                request_id=request_id,
                data=data.model_copy(update={"key": f"new_{index}"}),
            )
    return ids


def queue(client, seed):
    url = f"/api/v1/products/{seed.product_id}/authoring"
    preview = client.get(url + "/approval-preview")
    assert preview.status_code == 200, preview.text
    body = {"fingerprint": preview.json()["fingerprint"]}
    job_id = uuid4()
    result = client.put(f"{url}/approvals/{job_id}", json=body)
    assert result.status_code == 202, result.text
    return url, job_id, body, result.json()


def test_all_pages_grouped_commit_preserves_text_and_duplicate_delivery(review_api):
    client, seed, _, factory = review_api
    configure(client, seed)
    ids = seed_drafts(factory, seed, 52)
    url, job_id, body, first = queue(client, seed)
    assert first["count"] == 52 and first["state"] == "queued"
    assert len(client.get(url).json()["items"]) == 50
    assert client.get(url + "/approval-preview").json()["languages"] == {"it": 52}
    assert client.put(f"{url}/approvals/{job_id}", json=body).json() == first
    assert client.put(f"{url}/approvals/{uuid4()}", json=body).status_code == 409
    with factory() as session:
        assert session.scalar(select(BranchJob)) is None  # HTTP is database-only intake.
        before = {row.id: row.payload for row in session.scalars(select(AuthoringRequest))}
    bulk.execute(factory, job_id=job_id)
    bulk.execute(factory, job_id=job_id)
    with factory() as session:
        job = session.get(AuthoringApproval, job_id)
        assert job.state == "succeeded", job.error
        assert len(job.branch_job_ids) == 1
        branch_id = UUID(job.branch_job_ids[0])
        rows = list(session.scalars(select(AuthoringRequest)))
        assert {row.id for row in rows} == set(ids)
        assert all(row.state == "approved" and row.version == 2 for row in rows)
        assert {row.id: row.payload for row in rows} == before
        assert len(list(session.scalars(select(BranchJob)))) == 1
    # Actual writeback worker with a synthetic provider proves one commit, all texts, no PR.
    remote = Remote(seed, factory)
    assert run(factory, remote, branch_id) == ("committed", None)
    assert len(remote.commits) == 1 and remote.prs == []
    assert len(remote.commits[0].files) == 1
    content = remote.commits[0].files[0].content.decode()
    for index in range(52):
        assert f'name="new_{index}"' in content
    assert content.count("Nuova stringa") == 52
    assert client.get(url + "/approval-preview").json()["count"] == 0
    assert client.put(f"{url}/approvals/{job_id}", json=body).json()["state"] == "succeeded"


@pytest.mark.parametrize("change", ["version", "blank", "revoked", "source"])
def test_worker_failure_rolls_back_every_approval(review_api, change):
    client, seed, _, factory = review_api
    configure(client, seed)
    ids = seed_drafts(factory, seed)
    _, job_id, _, _ = queue(client, seed)
    with factory.begin() as session:
        row = session.get(AuthoringRequest, max(ids))  # Failure after the first update.
        if change == "version":
            row.version += 1
        elif change == "blank":
            row.payload = {
                **row.payload,
                "input": {**row.payload["input"], "forms": [{"form": "other", "text": " "}]},
            }
        elif change == "source":
            row.payload = {
                **row.payload,
                "input": {**row.payload["input"], "execution_id": str(uuid4())},
            }
        else:
            session.get(User, seed.actor_id).is_active = False
    with factory() as session:
        before = {
            row.id: (row.version, row.payload) for row in session.scalars(select(AuthoringRequest))
        }
    bulk.execute(factory, job_id=job_id)
    with factory() as session:
        job = session.get(AuthoringApproval, job_id)
        assert job.state == "failed" and job.error
        assert session.scalar(select(BranchJob)) is None
        rows = list(session.scalars(select(AuthoringRequest)))
        assert all(row.state == "draft" for row in rows)
        assert {row.id: (row.version, row.payload) for row in rows} == before


@pytest.mark.parametrize("role", ["viewer", "translator"])
def test_api_requires_current_review_role(review_api, role):
    client, seed, _, factory = review_api
    seed_drafts(factory, seed)
    url = f"/api/v1/products/{seed.product_id}/authoring"
    digest = client.get(url + "/approval-preview").json()["fingerprint"]
    with factory.begin() as session:
        session.get(User, seed.actor_id).roles = [
            session.scalar(select(Role).where(Role.name == role))
        ]
        mirror_fixture_role(session, seed.actor_id)
    assert client.get(url + "/approval-preview").status_code == 403
    assert client.put(f"{url}/approvals/{uuid4()}", json={"fingerprint": digest}).status_code == 403


def test_changed_preview_foreign_product_and_skipped_claim(review_api):
    client, seed, _, factory = review_api
    ids = seed_drafts(factory, seed)
    url = f"/api/v1/products/{seed.product_id}/authoring"
    digest = client.get(url + "/approval-preview").json()["fingerprint"]
    with factory.begin() as session:
        session.get(AuthoringRequest, ids[0]).version += 1
    assert client.put(f"{url}/approvals/{uuid4()}", json={"fingerprint": digest}).status_code == 409
    assert client.get(f"/api/v1/products/{uuid4()}/authoring/approval-preview").status_code == 404
    _, job_id, _, _ = queue(client, seed)
    with factory.begin() as session:
        session.scalar(
            select(AuthoringApproval).where(AuthoringApproval.id == job_id).with_for_update()
        )
        bulk.execute(factory, job_id=job_id)  # Duplicate workers skip the held claim.
    with factory() as session:
        assert session.get(AuthoringApproval, job_id).state == "queued"
    bulk.execute(factory, job_id=job_id)
    with factory() as session:
        assert session.get(AuthoringApproval, job_id).state == "succeeded"


def test_durable_dispatch_recovers_broker_failure_without_browser(review_api, monkeypatch):
    from verboflex.worker import authoring_tasks

    client, seed, _, factory = review_api
    seed_drafts(factory, seed)
    _, job_id, _, _ = queue(client, seed)
    monkeypatch.setattr(authoring_tasks, "SessionFactory", factory)

    def unavailable(_):
        raise RuntimeError("synthetic broker unavailable")

    monkeypatch.setattr(authoring_tasks.approve_drafts, "delay", unavailable)
    with pytest.raises(RuntimeError):
        authoring_tasks.dispatch_approvals()
    sent = []
    monkeypatch.setattr(authoring_tasks.approve_drafts, "delay", sent.append)
    assert authoring_tasks.dispatch_approvals() == 1
    assert sent == [str(job_id)]
    authoring_tasks.approve_drafts(sent[0])
    assert authoring_tasks.dispatch_approvals() == 0
