"""Synthetic coverage for atomic account creation with initial product roles."""
# ruff: noqa: F401, F811

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, event, select
from sqlalchemy.orm import Session

from tests.api.test_admin_users import admin_request, create_payload
from tests.api.test_product_team import (
    admin_session_factory,
    clean_admin_users_database,
    request,
    setup_team,
)
from verboflex.auth.passwords import verify_password
from verboflex.models.product import Product
from verboflex.models.product_member import ProductMember, ProductTeamEvent
from verboflex.models.user import User


@pytest.fixture(autouse=True)
def clean_team_events(admin_session_factory):
    with admin_session_factory.begin() as session:
        session.execute(delete(ProductTeamEvent))


def provision(setup, assignments, actor="admin", email="new@example.com"):
    _, _, people, _, _ = setup
    return asyncio.run(
        admin_request(
            "POST",
            access_token=people[actor][1],
            json_body={
                **create_payload(email=email, roles=["viewer"]),
                "product_assignments": assignments,
            },
        )
    )


def assert_not_created(factory):
    with factory() as session:
        assert session.scalar(select(User.id).where(User.email == "new@example.com")) is None
        assert session.scalar(select(ProductTeamEvent.id)) is None


@pytest.mark.parametrize(
    "role", ["viewer", "translator", "product_manager_reviewer", "product_owner"]
)
def test_admin_assigns_independent_roles_and_audit_receipts_atomically(setup_team, role):
    factory, _, people, first, second = setup_team
    unassigned = uuid4()
    with factory.begin() as session:
        session.add(
            Product(id=unassigned, display_name="Unassigned", name_key="unassigned", is_active=True)
        )
    assignments = [
        {"product_id": str(first), "role": role},
        {"product_id": str(second), "role": "viewer"},
    ]
    response = provision(setup_team, assignments)
    assert response.status_code == 201, response.text
    assert response.headers["cache-control"] == "no-store"
    result = response.json()
    user_id = UUID(result["id"])
    password = result["temporary_password"]
    with factory() as session:
        user = session.get_one(User, user_id)
        assert user.must_change_password and user.is_active
        assert verify_password(password, user.hashed_password)
        assert [r.name for r in user.roles] == ["viewer"]
        members = list(
            session.scalars(select(ProductMember).where(ProductMember.user_id == user_id))
        )
        assert {member.product_id: member.role for member in members} == {
            first: role,
            second: "viewer",
        }
        assert all(member.active and member.version for member in members)
        events = list(
            session.scalars(select(ProductTeamEvent).where(ProductTeamEvent.subject_id == user_id))
        )
        assert {receipt.product_id: receipt.role for receipt in events} == {
            first: role,
            second: "viewer",
        }
        assert all(
            receipt.actor_id == people["admin"][0]
            and receipt.action == "member.added"
            and receipt.previous_role is None
            for receipt in events
        )
        assert password not in str([receipt.__dict__ for receipt in events])
        assert session.get(ProductMember, (unassigned, user_id)) is None

    # Use the real first-login flow to prove the new assignments become effective.
    login = request(
        "POST", "/auth/token", data={"username": "new@example.com", "password": password}
    )
    assert login.status_code == 200, login.text
    assert login.json()["must_change_password"] is True
    restricted = login.json()["access_token"]
    assert request("GET", "/users/me", restricted).status_code == 403
    chosen = "synthetic replacement password!"
    assert (
        request(
            "POST",
            "/auth/change-password",
            restricted,
            json={"current_password": password, "new_password": chosen},
        ).status_code
        == 204
    )
    login = request("POST", "/auth/token", data={"username": "new@example.com", "password": chosen})
    token = login.json()["access_token"]
    assert request("GET", f"/products/{first}/access", token).json()["role"] == role
    assert request("GET", f"/products/{second}/access", token).json()["role"] == "viewer"
    assert request("GET", f"/products/{unassigned}/access", token).json()["role"] is None
    me = request("GET", "/users/me", token).json()
    assert set(me["product_roles"]) == {str(first), str(second)}
    assert me["managed_product_ids"] == ([str(first)] if role == "product_owner" else [])


@pytest.mark.parametrize("state", ["missing", "inactive", "deleted"])
def test_unavailable_product_rejects_every_assignment_and_account(setup_team, state):
    factory, _, people, first, second = setup_team
    with factory.begin() as session:
        product = session.get_one(Product, second)
        if state == "missing":
            second = uuid4()
        else:
            product.is_active = False
            if state == "deleted":
                product.deleted_at = datetime.now(UTC)
                product.deleted_by = people["admin"][0]
    response = provision(
        setup_team,
        [
            {"product_id": str(first), "role": "translator"},
            {"product_id": str(second), "role": "viewer"},
        ],
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Selected products unavailable"
    assert "temporary_password" not in response.text
    assert_not_created(factory)


@pytest.mark.parametrize("invalid", ["duplicate", "role", "uuid", "extra", "too_many"])
def test_invalid_assignment_contract_has_no_side_effects(setup_team, invalid):
    factory, _, _, first, _ = setup_team
    assignment = {"product_id": str(first), "role": "translator"}
    assignments = [assignment]
    if invalid == "duplicate":
        assignments.append({**assignment, "role": "product_owner"})
    elif invalid == "role":
        assignment["role"] = "admin"
    elif invalid == "uuid":
        assignment["product_id"] = "invalid-uuid"
    elif invalid == "extra":
        assignment["unexpected"] = "value"
    else:
        assignments = [{"product_id": str(uuid4()), "role": "viewer"} for _ in range(101)]
    response = provision(setup_team, assignments)
    assert response.status_code == 422
    assert_not_created(factory)


@pytest.mark.parametrize("actor", ["owner", "reader"])
def test_product_owner_and_non_admin_cannot_use_bulk_provisioning(setup_team, actor):
    factory, _, _, first, _ = setup_team
    response = provision(setup_team, [{"product_id": str(first), "role": "product_owner"}], actor)
    assert response.status_code == 403
    assert_not_created(factory)


def test_duplicate_account_does_not_add_memberships_or_reset_password(setup_team):
    factory, _, people, first, _ = setup_team
    existing_id = people["other"][0]
    with factory() as session:
        password_hash = session.get_one(User, existing_id).hashed_password
    response = provision(
        setup_team, [{"product_id": str(first), "role": "product_owner"}], email="other@example.com"
    )
    assert response.status_code == 409
    with factory() as session:
        assert session.get(ProductMember, (first, existing_id)) is None
        assert session.get_one(User, existing_id).hashed_password == password_hash
        assert session.scalar(select(ProductTeamEvent.id)) is None


def test_membership_commit_failure_rolls_back_new_account(setup_team):
    factory, _, _, first, _ = setup_team

    def reject_membership(session, _context, _instances):
        if any(isinstance(item, ProductMember) for item in session.new):
            raise RuntimeError("Synthetic membership failure")

    event.listen(Session, "before_flush", reject_membership)
    try:
        response = provision(setup_team, [{"product_id": str(first), "role": "translator"}])
    finally:
        event.remove(Session, "before_flush", reject_membership)
    assert response.status_code == 500
    assert "temporary_password" not in response.text
    assert_not_created(factory)
