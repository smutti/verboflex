"""Product-scoped read-only submission review tracer over a genuine imported basis."""

# ruff: noqa: F811

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from tests.integration.test_preview_jobs import (
    clean_preview_database,  # noqa: F401
    preview_session_factory,  # noqa: F401
)
from tests.integration.test_writeback_authority import seed_writeback_authority
from tests.legacy_product_fixtures import mirror_fixture_role
from verboflex.auth.principal import Principal, get_current_principal
from verboflex.db.session import get_db_session
from verboflex.main import app
from verboflex.models.role import Role
from verboflex.models.user import User
from verboflex.schemas.users import RoleName


@pytest.fixture
def review_api(preview_session_factory, monkeypatch):
    seed = seed_writeback_authority(preview_session_factory, monkeypatch)
    principal = Principal(
        seed.actor_id, "review@example.test", "Reviewer", (RoleName.ADMIN,), False
    )

    def session():
        with preview_session_factory() as value:
            yield value

    app.dependency_overrides[get_db_session] = session
    app.dependency_overrides[get_current_principal] = lambda: principal
    sent = []
    monkeypatch.setattr(app.state, "submission_review_enqueuer", sent.append, raising=False)
    with TestClient(app) as client:
        yield client, seed, sent, preview_session_factory
    app.dependency_overrides.clear()


def payload(seed):
    return {"proposals": [{"proposal_id": str(seed.proposal_id), "expected_version": seed.version}]}


def test_complete_approved_review_is_durable_202_and_queue_contains_only_uuid(review_api):
    client, seed, sent, _ = review_api
    base = f"/api/v1/products/{seed.product_id}"
    candidates = client.get(f"{base}/change-set-candidates")
    assert candidates.status_code == 200
    item = candidates.json()["items"][0]
    assert item["proposal_id"] == str(seed.proposal_id)
    assert item["can_review"] is True and item["value_count"] == 2
    response = client.post(f"{base}/submission-reviews", json=payload(seed))
    assert response.status_code == 202
    review = response.json()
    assert review["state"] == "queued" and review["values"] == []
    assert [str(value) for value in sent] == [review["id"]]
    assert client.get(f"{base}/submission-reviews/{review['id']}").json() == review
    assert "prepared" not in review and "token" not in str(review)


def test_detail_entry_selects_only_the_exact_current_translation_group(review_api):
    client, seed, sent, _ = review_api
    url = f"/api/v1/products/{seed.product_id}/change-set-candidates"
    exact = client.get(url, params={"translation_group_id": str(seed.value_ids[0])})
    assert exact.status_code == 200
    assert [item["proposal_id"] for item in exact.json()["items"]] == [str(seed.proposal_id)]
    for identity in (uuid4(), seed.value_ids[1]):
        unavailable = client.get(url, params={"translation_group_id": str(identity)})
        assert unavailable.status_code == 200
        assert unavailable.json()["items"] == []
    assert sent == []


@pytest.mark.parametrize("role", ["translator", "viewer"])
def test_read_only_roles_can_read_but_cannot_request_review(review_api, role):
    client, seed, sent, factory = review_api
    with factory.begin() as session:
        session.get(User, seed.actor_id).roles = [
            session.scalars(select(Role).where(Role.name == role)).one()
        ]
        mirror_fixture_role(session, session.get(User, seed.actor_id).id)
    base = f"/api/v1/products/{seed.product_id}"
    assert client.get(f"{base}/change-set-candidates").status_code == 200
    assert client.post(f"{base}/submission-reviews", json=payload(seed)).status_code == 403
    assert sent == []


def test_foreign_product_is_unavailable_before_action_denial(review_api):
    client, seed, sent, _ = review_api
    response = client.post(f"/api/v1/products/{uuid4()}/submission-reviews", json=payload(seed))
    assert response.status_code == 404 and sent == []


def test_stale_version_and_duplicate_selection_are_closed(review_api):
    client, seed, sent, _ = review_api
    body = payload(seed)
    body["proposals"][0]["expected_version"] += 1
    assert (
        client.post(f"/api/v1/products/{seed.product_id}/submission-reviews", json=body).status_code
        == 409
    )
    body = payload(seed)
    body["proposals"] *= 2
    assert (
        client.post(f"/api/v1/products/{seed.product_id}/submission-reviews", json=body).status_code
        == 422
    )
    assert sent == []


def test_reviewer_union_role_is_authorized_and_http_never_prepares(review_api, monkeypatch):
    from verboflex.services import submission_selection

    client, seed, sent, factory = review_api
    with factory.begin() as session:
        session.get(User, seed.actor_id).roles = list(
            session.scalars(
                select(Role).where(Role.name.in_(("viewer", "product_manager_reviewer")))
            )
        )
        mirror_fixture_role(session, session.get(User, seed.actor_id).id)

    def forbidden(*args, **kwargs):
        raise AssertionError("HTTP must not prepare or read the provider")

    monkeypatch.setattr(submission_selection, "prepare_writeback", forbidden)
    response = client.post(
        f"/api/v1/products/{seed.product_id}/submission-reviews", json=payload(seed)
    )
    assert response.status_code == 202 and len(sent) == 1


def test_over_limit_intake_is_rejected_before_any_rich_capture(review_api, monkeypatch):
    from verboflex.services import writeback_authority

    client, seed, sent, _ = review_api
    # The genuine two-member proposal exceeds this deliberately small aggregate
    # budget. Validation must not format or calculate graphemes first.
    monkeypatch.setattr(writeback_authority, "MAX_CANONICAL_AGGREGATE_BYTES", 1)
    response = client.post(
        f"/api/v1/products/{seed.product_id}/submission-reviews", json=payload(seed)
    )
    assert response.status_code == 409 and response.json()["code"] == "limit_exceeded"
    assert sent == []
