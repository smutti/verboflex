"""Saved additions are reopened by identity and never replaced by duplicate creates."""

from uuid import uuid4

from sqlalchemy import select

from tests.api.test_submission_reviews import review_api as review_api
from tests.integration.test_preview_jobs import clean_preview_database as clean_preview_database
from tests.integration.test_preview_jobs import preview_session_factory as preview_session_factory
from tests.integration.test_translation_authoring import draft
from tests.legacy_product_fixtures import mirror_fixture_role
from verboflex.models.role import Role
from verboflex.models.user import User


def test_reopen_duplicate_and_stale_save_preserve_current_text(review_api):
    client, seed, _, factory = review_api
    body = draft(factory, seed).model_dump(mode="json")
    base = f"/api/v1/products/{seed.product_id}/authoring"
    identity = uuid4()
    saved = client.put(f"{base}/{identity}", json=body)
    assert saved.status_code == 200, saved.text
    assert client.get(f"{base}/{identity}").json() == saved.json()
    duplicate = client.put(
        f"{base}/{uuid4()}", json={**body, "forms": [{"form": "other", "text": "Other text"}]}
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["existing_request_id"] == str(identity)
    changed = client.put(
        f"{base}/{identity}",
        json={**body, "expected_version": 1, "forms": [{"form": "other", "text": "Updated text"}]},
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["version"] == 2
    stale = client.put(f"{base}/{identity}", json={**body, "expected_version": 1})
    assert stale.status_code == 409
    assert client.get(f"{base}/{identity}").json()["input"]["forms"][0]["text"] == "Updated text"
    assert client.get(f"/api/v1/products/{uuid4()}/authoring/{identity}").status_code == 404
    with factory.begin() as session:
        session.get_one(User, seed.actor_id).roles = [
            session.scalar(select(Role).where(Role.name == "viewer"))
        ]
        mirror_fixture_role(session, seed.actor_id)
    assert client.get(f"{base}/{identity}").status_code == 200
    assert client.put(f"{base}/{identity}", json={**body, "expected_version": 2}).status_code == 403
    with factory.begin() as session:
        session.get_one(User, seed.actor_id).is_active = False
    assert client.get(f"{base}/{identity}").status_code in (401, 403)
