"""Product permissions, database-only HTTP intake and explicit PR publication."""

from uuid import uuid4

import pytest
from sqlalchemy import select

from tests.api.test_submission_reviews import review_api as review_api
from tests.integration.test_branch_workflow import Remote, approve, republish, run
from tests.integration.test_preview_jobs import clean_preview_database as clean_preview_database
from tests.integration.test_preview_jobs import preview_session_factory as preview_session_factory
from tests.legacy_product_fixtures import mirror_fixture_role
from verboflex.models.branch_workflow import BranchJob
from verboflex.models.role import Role
from verboflex.models.user import User


def configure(client, seed):
    url = f"/api/v1/products/{seed.product_id}/branch-workflow"
    response = client.put(
        url,
        json={
            "mapping_id": str(seed.mapping_id),
            "work_branch": "feature/translations",
            "target_branch": "main",
        },
    )
    assert response.status_code == 200, response.text
    return url


def test_api_configure_approve_history_then_explicit_pr(review_api):
    client, seed, sent, factory = review_api
    url = configure(client, seed)
    remote = Remote(seed, factory)
    assert (
        client.get(f"/api/v1/translations/{seed.value_ids[0]}").json()["approval_commits_enabled"]
        is True
    )
    job_id = approve(factory, seed, "Sintetica")
    waiting = client.get(url).json()
    assert waiting["items"][0]["state"] == "queued"
    assert waiting["can_create_pr"] is False
    assert client.post(url + "/pull-request").status_code == 409
    assert run(factory, remote, job_id) == ("committed", None)
    ready = client.get(url).json()
    assert ready["can_create_pr"] is True
    assert ready["items"][0]["commit_url"].startswith("https://bitbucket.org/")
    assert "authority" not in str(ready) and "intent" not in str(ready)
    result = client.post(url + "/pull-request")
    assert result.status_code == 202, result.text
    assert result.json()["items"][0]["kind"] == "pull_request"
    assert result.json()["items"][0]["state"] == "queued"
    assert remote.prs == []  # HTTP must not call Bitbucket.
    assert sent == []  # No legacy submission job.
    duplicate = client.post(url + "/pull-request")
    assert duplicate.status_code == 409
    with factory() as s:
        assert len(list(s.scalars(select(BranchJob).where(BranchJob.kind == "pull_request")))) == 1


def test_all_http_projections_include_verified_target_status(review_api):
    from pydantic import SecretStr

    from tests.integration.test_approval_target import check, target_at
    from verboflex.core.config import Settings, get_settings
    from verboflex.main import app

    client, seed, _, factory = review_api
    app.dependency_overrides[get_settings] = lambda: Settings(
        jwt_secret_key=SecretStr("synthetic-target-status-signing-key" * 2)
    )
    configure(client, seed)
    remote = Remote(seed, factory)
    job = approve(factory, seed, "Approved translation")
    run(factory, remote, job)
    target_at(remote, remote.head)
    check(factory, remote, job)
    group_url = f"/api/v1/translations/{seed.value_ids[0]}"
    detail = client.get(group_url).json()
    assert detail["pending_change"]["target_integrated"] is True
    assert detail["pending_change"]["target_branch"] == "main"
    response = client.get(f"/api/v1/translations?product_id={seed.product_id}&language=it")
    assert response.status_code == 200, response.text
    summaries = response.json()
    assert summaries["items"][0]["pending_change"]["target_integrated"] is True
    # A new approval returns the target immediately in the mutation response,
    # before any commit or background presence check.
    rejected = client.post(
        group_url + "/proposal/state",
        json={
            "expected_version": detail["pending_change"]["version"],
            "target_state": "draft",
        },
    ).json()
    approved = client.post(
        group_url + "/proposal/state",
        json={
            "expected_version": rejected["version"],
            "target_state": "approved",
        },
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["target_branch"] == "main"
    assert approved.json()["target_integrated"] is False


@pytest.mark.parametrize("role", ["translator", "viewer"])
def test_readers_cannot_publish_or_configure(review_api, role):
    client, seed, _, factory = review_api
    url = configure(client, seed)
    with factory.begin() as s:
        s.get(User, seed.actor_id).roles = [s.scalar(select(Role).where(Role.name == role))]
        mirror_fixture_role(s, seed.actor_id)
    assert client.get(url).status_code == 200
    assert client.get(url).json()["can_publish"] is False
    assert client.post(url + "/pull-request").status_code == 403
    assert client.post(url + f"/jobs/{uuid4()}/retry").status_code == 403
    assert (
        client.put(
            url,
            json={
                "mapping_id": str(seed.mapping_id),
                "work_branch": "feature/translations",
                "target_branch": "main",
            },
        ).status_code
        == 403
    )


def test_rejects_foreign_and_dangerous_configuration(review_api):
    client, seed, _, _ = review_api
    url = f"/api/v1/products/{seed.product_id}/branch-workflow"
    for branch in ("main", "../main", "work.lock", "feature//work", 'feature/a"b'):
        result = client.put(
            url,
            json={
                "mapping_id": str(seed.mapping_id),
                "work_branch": branch,
                "target_branch": "main",
            },
        )
        assert result.status_code == 409
    assert client.get(f"/api/v1/products/{uuid4()}/branch-workflow").status_code == 404
    result = client.put(
        url,
        json={
            "mapping_id": str(uuid4()),
            "work_branch": "feature/translations",
            "target_branch": "main",
        },
    )
    assert result.status_code == 409


def test_legacy_submission_cannot_bypass_configured_workflow(review_api):
    client, seed, sent, _ = review_api
    configure(client, seed)
    result = client.post(
        f"/api/v1/products/{seed.product_id}/submission-reviews",
        json={
            "proposals": [{"proposal_id": str(seed.proposal_id), "expected_version": seed.version}]
        },
    )
    assert result.status_code == 403
    assert not sent


def test_merged_commit_is_not_offered_for_another_pr(review_api):
    client, seed, _, factory = review_api
    url = configure(client, seed)
    remote = Remote(seed, factory)
    job = approve(factory, seed, "Sintetica")
    assert run(factory, remote, job)[0] == "committed"
    client.post(url + "/pull-request")
    with factory.begin() as s:
        pr = s.scalar(select(BranchJob).where(BranchJob.kind == "pull_request"))
        pr.state, pr.commit_hash = "merged", remote.head
    assert client.get(url).json()["can_create_pr"] is False
    assert client.post(url + "/pull-request").status_code == 409


def test_each_source_can_configure_branches_and_pr_requires_exact_selection(review_api):
    client, seed, _, factory = review_api
    url = configure(client, seed)
    first_id = client.get(url).json()["workflow_id"]
    _, mapping_id = republish(factory, seed, extra_mapping=True)
    before = client.get(url).json()
    assert len(before["available_mappings"]) == 2
    assert before["workflows"][0]["active"] is True
    response = client.put(
        url,
        json={
            "mapping_id": str(mapping_id),
            "work_branch": "feature/localization",
            "target_branch": "release/2026",
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    second_id = data["workflow_id"]
    assert second_id != first_id
    assert len(data["workflows"]) == 2
    assert data["work_branch"] == "feature/localization"
    assert data["target_branch"] == "release/2026"
    assert (
        client.get(url, params={"workflow_id": first_id}).json()["work_branch"]
        == "feature/translations"
    )
    assert client.get(url, params={"workflow_id": str(uuid4())}).status_code == 404
    assert client.post(url + "/pull-request").status_code == 409
    assert "Select" in client.post(url + "/pull-request").json()["detail"]
    assert client.post(url + "/pull-request", params={"workflow_id": second_id}).status_code == 409
    assert (
        client.put(
            url,
            json={
                "mapping_id": str(mapping_id),
                "work_branch": "feature/localization",
                "target_branch": "release/2026",
            },
        ).json()["workflow_id"]
        == second_id
    )
    with factory() as session:
        assert not list(session.scalars(select(BranchJob)))


def test_pr_double_click_is_serialized(review_api):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    client, seed, _, factory = review_api
    url = configure(client, seed)
    remote = Remote(seed, factory)
    run(factory, remote, approve(factory, seed, "Ready"))
    barrier = Barrier(2)

    def publish():
        barrier.wait(timeout=10)
        return client.post(url + "/pull-request").status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: publish(), range(2)))
    assert sorted(results) == [202, 409]
    with factory() as session:
        job = session.scalars(select(BranchJob.id).where(BranchJob.kind == "pull_request")).one()
    assert run(factory, remote, job)[0] == "open"
    assert len(remote.prs) == 1
