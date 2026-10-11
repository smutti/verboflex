"""Independent real-database checks of history authorization and paging boundaries."""

from uuid import uuid4

import pytest
from sqlalchemy import select

from tests.api.test_submission_history import history_api as history_api
from tests.api.test_submission_reviews import review_api as review_api
from tests.api.test_submissions import ready_api as ready_api
from tests.integration.test_preview_jobs import clean_preview_database as clean_preview_database
from tests.integration.test_preview_jobs import preview_session_factory as preview_session_factory
from verboflex.auth.principal import Principal, get_current_principal
from verboflex.models.role import Role
from verboflex.models.submission import ChangeSet, ChangeSetEvent
from verboflex.models.user import User
from verboflex.schemas.users import RoleName


def activity(history_api, count=31):
    ready, group_id = history_api
    client, seed, factory, _, _, _ = ready
    with factory.begin() as session:
        row = session.get(ChangeSet, group_id)
        for _ in range(count):
            session.add(
                ChangeSetEvent(
                    change_set_id=group_id,
                    attempt=row.attempt,
                    execution_fence=row.execution_fence,
                    proof_sequence=row.current_proof_sequence,
                    event_kind="reauthorization",
                    step="authority",
                    outcome="verified",
                    request_digest="a" * 64,
                    receipt={"action": "reauthorized"},
                )
            )
    base = f"/api/v1/products/{seed.product_id}/change-sets/{group_id}"
    first = client.get(base + "/activity")
    assert first.status_code == 200
    return first.json(), base


@pytest.mark.parametrize("boundary", ["actor", "stamp"])
def test_history_cursor_cannot_cross_authority_or_projection(history_api, boundary):
    ready, _ = history_api
    client, seed, factory, _, _, _ = ready
    first, base = activity(history_api)
    cursor = first["next_cursor"]
    suffix = "/activity"
    if boundary == "actor":
        actor_id = uuid4()
        with factory.begin() as session:
            session.add(
                User(
                    id=actor_id,
                    email=f"{actor_id}@example.test",
                    display_name="Other",
                    hashed_password="unused",
                    must_change_password=False,
                    roles=[session.scalar(select(Role).where(Role.name == "viewer"))],
                )
            )
        client.app.dependency_overrides[get_current_principal] = lambda: Principal(
            actor_id, "other@example.test", "Other", (RoleName.VIEWER,), False
        )
    elif boundary == "stamp":
        with factory.begin() as session:
            session.get(User, seed.actor_id).token_version += 1
    response = client.get(base + suffix, params={"cursor": cursor})
    assert response.status_code == 422
    assert "items" not in response.json()
