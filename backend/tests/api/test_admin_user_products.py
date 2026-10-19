"""Synthetic coverage for atomic account creation with initial product roles."""
# ruff: noqa: F401, F811

import asyncio
from concurrent.futures import ThreadPoolExecutor
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


def user_products(setup, *, actor="admin", user="owner", **params):
    _, _, people, _, _ = setup
    return request(
        "GET", f"/admin/users/{people[user][0]}/products", people[actor][1], params=params
    )


def edit_products(setup, changes=None, *, actor="admin", user="owner", **fields):
    _, _, people, _, _ = setup
    return request(
        "PATCH",
        f"/admin/users/{people[user][0]}",
        people[actor][1],
        json={
            "display_name": "Updated person",
            "roles": ["viewer"],
            **({"product_assignments": changes} if changes is not None else {}),
            **fields,
        },
    )


def change(item, role):
    return {"product_id": item["product_id"], "role": role, "expected_version": item["version"]}


def test_user_product_page_includes_current_roles_and_inactive_but_not_deleted_products(setup_team):
    factory, _, people, first, second = setup_team
    deleted_id, unassigned_id = uuid4(), uuid4()
    with factory.begin() as session:
        session.get_one(Product, second).is_active = False
        session.add_all(
            [
                Product(
                    id=deleted_id,
                    display_name="Deleted",
                    name_key="deleted",
                    is_active=False,
                    deleted_at=datetime.now(UTC),
                    deleted_by=people["admin"][0],
                ),
                Product(
                    id=unassigned_id,
                    display_name="Unassigned",
                    name_key="unassigned",
                    is_active=True,
                ),
            ]
        )
    items = []
    cursor = None
    while True:
        response = user_products(setup_team, limit=1, **({"cursor": cursor} if cursor else {}))
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "no-store"
        body = response.json()
        items.extend(body["items"])
        cursor = body["next_cursor"]
        if cursor is None:
            break
    assert [item["product_id"] for item in items] == [str(first), str(second), str(unassigned_id)]
    assert [item["role"] for item in items] == ["product_owner", "viewer", None]
    assert items[0]["version"] and items[1]["version"] and items[2]["version"] is None
    assert items[1]["is_active"] is False
    assert all(
        set(item) == {"product_id", "name", "is_active", "role", "version"} for item in items
    )


def test_admin_edits_adds_and_removes_memberships_with_profile_in_one_save(setup_team):
    factory, _, people, first, second = setup_team
    extra = uuid4()
    with factory.begin() as session:
        session.add(Product(id=extra, display_name="Extra", name_key="extra", is_active=True))
        prior_token_version = session.get_one(User, people["owner"][0]).token_version
    items = {item["product_id"]: item for item in user_products(setup_team).json()["items"]}
    response = edit_products(
        setup_team,
        [
            change(items[str(first)], "translator"),
            change(items[str(second)], None),
            change(items[str(extra)], "product_owner"),
        ],
    )
    assert response.status_code == 200, response.text
    assert response.json()["display_name"] == "Updated person"
    assert "temporary_password" not in response.text
    with factory() as session:
        user_id = people["owner"][0]
        assert session.get_one(User, user_id).token_version == prior_token_version
        assert session.get_one(ProductMember, (first, user_id)).role == "translator"
        assert session.get_one(ProductMember, (first, user_id)).version != UUID(
            items[str(first)]["version"]
        )
        assert not session.get_one(ProductMember, (second, user_id)).active
        assert session.get_one(ProductMember, (extra, user_id)).role == "product_owner"
        receipts = list(
            session.scalars(select(ProductTeamEvent).where(ProductTeamEvent.subject_id == user_id))
        )
        assert len(receipts) == 3
        assert all(receipt.actor_id == people["admin"][0] for receipt in receipts)
        removed = next(receipt for receipt in receipts if receipt.product_id == second)
        assert (
            removed.action == "member.removed"
            and removed.previous_role == "viewer"
            and removed.role is None
        )
    # Current product access changes immediately without requiring a new login.
    token = people["owner"][1]
    assert request("GET", f"/products/{first}/access", token).json()["role"] == "translator"
    assert request("GET", f"/products/{second}/access", token).json()["role"] is None
    assert request("GET", f"/products/{extra}/access", token).json()["role"] == "product_owner"


def test_edit_preserves_unloaded_products_and_omitted_assignments(setup_team):
    factory, _, people, _, second = setup_team
    first_page = user_products(setup_team, limit=1).json()
    assert first_page["next_cursor"] is not None
    assert (
        edit_products(setup_team, [change(first_page["items"][0], "translator")]).status_code == 200
    )
    before = user_products(setup_team).json()
    assert edit_products(setup_team, display_name="Profile only").status_code == 200
    assert user_products(setup_team).json() == before
    assert (
        next(item for item in before["items"] if item["product_id"] == str(second))["role"]
        == "viewer"
    )
    with factory() as session:
        assert session.get_one(User, people["owner"][0]).display_name == "Profile only"


@pytest.mark.parametrize("conflict", ["stale", "removed", "deleted", "new_membership"])
def test_stale_product_edit_rolls_back_profile_roles_and_all_assignments(setup_team, conflict):
    factory, _, people, _, _ = setup_team
    items = sorted(user_products(setup_team).json()["items"], key=lambda item: item["product_id"])
    target = people["owner"][0]
    affected = UUID(items[1]["product_id"])
    changes = [change(items[0], "translator"), change(items[1], "translator")]
    with factory.begin() as session:
        member = session.get_one(ProductMember, (affected, target))
        if conflict == "removed":
            member.active = False
            member.version = uuid4()
        elif conflict == "deleted":
            product = session.get_one(Product, affected)
            product.is_active = False
            product.deleted_at = datetime.now(UTC)
            product.deleted_by = people["admin"][0]
        elif conflict == "new_membership":
            changes[1]["expected_version"] = None
        else:
            member.version = uuid4()
        original_name = session.get_one(User, target).display_name
        original_token = session.get_one(User, target).token_version
    response = edit_products(setup_team, changes, roles=["translator"])
    assert response.status_code == 409, response.text
    assert response.json()["detail"] == "Product access changed or unavailable"
    with factory() as session:
        user = session.get_one(User, target)
        assert user.display_name == original_name and user.token_version == original_token
        assert [role.name for role in user.roles] == ["viewer"]
        first_member = session.get_one(ProductMember, (UUID(items[0]["product_id"]), target))
        assert (
            first_member.role == items[0]["role"]
            and str(first_member.version) == items[0]["version"]
        )
        assert session.scalar(select(ProductTeamEvent.id)) is None


@pytest.mark.parametrize("actor", ["owner", "reader"])
def test_only_admins_can_read_or_edit_an_accounts_product_roles(setup_team, actor):
    items = user_products(setup_team).json()["items"]
    assert user_products(setup_team, actor=actor).status_code == 403
    assert (
        edit_products(setup_team, [change(items[0], "translator")], actor=actor).status_code == 403
    )
    assert user_products(setup_team).json()["items"] == items


@pytest.mark.parametrize(
    "invalid", ["duplicate", "role", "no_version", "unversioned_removal", "too_many"]
)
def test_update_membership_contract_rejects_invalid_changes(setup_team, invalid):
    items = user_products(setup_team).json()["items"]
    changes = [change(items[0], "translator")]
    if invalid == "duplicate":
        changes.append(dict(changes[0]))
    elif invalid == "role":
        changes[0]["role"] = "admin"
    elif invalid == "no_version":
        del changes[0]["expected_version"]
    elif invalid == "unversioned_removal":
        changes[0].update(role=None, expected_version=None)
    else:
        changes = [
            {"product_id": str(uuid4()), "role": "viewer", "expected_version": None}
            for _ in range(101)
        ]
    assert edit_products(setup_team, changes).status_code == 422
    assert user_products(setup_team).json()["items"] == items


def test_inactive_accounts_can_lose_access_but_cannot_receive_roles(setup_team):
    factory, _, people, _, _ = setup_team
    items = user_products(setup_team).json()["items"]
    with factory.begin() as session:
        session.get_one(User, people["owner"][0]).is_active = False
    assert edit_products(setup_team, [change(items[0], "translator")]).status_code == 409
    assert edit_products(setup_team, [change(items[0], None)]).status_code == 200
    assert user_products(setup_team).json()["items"][0]["role"] is None


def test_user_products_rejects_unknown_users_invalid_cursors_and_unbounded_pages(setup_team):
    _, _, people, _, _ = setup_team
    assert request("GET", f"/admin/users/{uuid4()}/products", people["admin"][1]).status_code == 404
    assert user_products(setup_team, cursor="invalid").status_code == 422
    assert user_products(setup_team, cursor="").status_code == 422
    assert user_products(setup_team, limit=101).status_code == 422
    assert request("GET", f"/admin/users/{people['owner'][0]}/products").status_code == 401


def test_user_edit_and_team_edit_cannot_overwrite_the_same_membership(setup_team):
    factory, _, people, first, _ = setup_team
    item = user_products(setup_team).json()["items"][0]

    def edit_from_team():
        return request(
            "PUT",
            f"/products/{first}/team/members",
            people["admin"][1],
            json={
                "email": "owner@example.com",
                "role": "viewer",
                "expected_version": item["version"],
            },
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        profile = pool.submit(edit_products, setup_team, [change(item, "translator")])
        team = pool.submit(edit_from_team)
        responses = [profile.result(), team.result()]
    assert sum(response.status_code in {200, 204} for response in responses) == 1
    assert sum(response.status_code == 409 for response in responses) == 1
    with factory() as session:
        receipts = list(session.scalars(select(ProductTeamEvent)))
        assert len(receipts) == 1
        member = session.get_one(ProductMember, (first, people["owner"][0]))
        assert member.role == ("translator" if responses[0].status_code == 200 else "viewer")
