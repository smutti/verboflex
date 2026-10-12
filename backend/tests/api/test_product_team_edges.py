"""Adversarial account, delivery, and stale-form product-team boundaries."""
# ruff: noqa: F401, F811

from uuid import uuid4

import pytest
from sqlalchemy import select

from tests.api.test_product_team import (
    PASSWORD,
    admin_session_factory,
    clean_admin_users_database,
    request,
    setup_team,
)
from verboflex.auth.product_access import current_product_role, membership_stamp
from verboflex.auth.rate_limits import get_redis_client
from verboflex.main import app
from verboflex.models.product_member import ProductMember, ProductTeamEvent
from verboflex.models.user import User
from verboflex.services import product_team as service


def test_member_removal_is_local_versioned_and_idempotence_never_restores_it(setup_team):
    factory, _, people, product, _ = setup_team
    path = f"/products/{product}/team"
    member = next(
        m
        for m in request("GET", path, people["owner"][1]).json()["members"]
        if m["role"] == "viewer"
    )
    data = {"email": member["email"], "role": "viewer", "expected_version": member["version"]}
    assert request("PUT", path + "/members", people["owner"][1], json=data).status_code == 204
    with factory() as session:
        assert (
            session.scalar(
                select(ProductTeamEvent.id).where(ProductTeamEvent.product_id == product)
            )
            is None
        )
    url = path + "/members/" + member["user_id"]
    assert (
        request(
            "DELETE", url, people["owner"][1], params={"expected_version": str(uuid4())}
        ).status_code
        == 409
    )
    assert (
        request(
            "DELETE", url, people["owner"][1], params={"expected_version": member["version"]}
        ).status_code
        == 204
    )
    assert (
        request(
            "DELETE", url, people["owner"][1], params={"expected_version": member["version"]}
        ).status_code
        == 404
    )
    with factory() as session:
        assert membership_stamp(session, people["reader"][0], product) == "unavailable"
        session.get_one(User, people["reader"][0]).is_active = False
        assert current_product_role(session, people["reader"][0], product) is None


@pytest.mark.parametrize(
    "changes",
    [
        {"email": "not-an-email"},
        {"display_name": "   "},
        {"display_name": "a\x00b"},
        {"role": "product_owner"},
        {"role": "admin"},
        {"roles": ["admin"]},
        {"must_change_password": False},
        {"password": "attacker password!"},
    ],
)
def test_invalid_creation_rolls_back_without_account_or_member(setup_team, changes):
    from tests.api.test_product_team_credentials import provision

    factory, _, _, product, _ = setup_team
    result = provision(setup_team, **changes)
    assert result.status_code == 422, result.text
    with factory() as session:
        assert session.scalar(select(User.id).where(User.email == "new@example.com")) is None
        assert (
            session.scalar(
                select(ProductTeamEvent.id).where(ProductTeamEvent.product_id == product)
            )
            is None
        )


@pytest.mark.parametrize("actor", ["other", "reader"])
def test_unprivileged_actor_cannot_create_account(setup_team, actor):
    factory, _, people, product, _ = setup_team
    result = request(
        "POST",
        f"/products/{product}/team/members",
        people[actor][1],
        json={"email": "new@example.com", "display_name": "New", "role": "translator"},
    )
    assert result.status_code == 403
    with factory() as session:
        assert session.scalar(select(User.id).where(User.email == "new@example.com")) is None


@pytest.mark.parametrize(
    "state,expected",
    [
        ("disabled_account", 409),
        ("admin_account", 403),
        ("inactive", 403),
        ("deleted", 404),
        ("other_product", 403),
    ],
)
def test_unavailable_target_or_product_cannot_be_provisioned(setup_team, state, expected):
    from datetime import UTC, datetime

    from verboflex.models.product import Product

    factory, _, people, product, other_product = setup_team
    email = "new@example.com"
    with factory.begin() as session:
        if state == "disabled_account":
            session.get_one(User, people["other"][0]).is_active = False
            email = "other@example.com"
        elif state == "admin_account":
            email = "admin@example.com"
        elif state == "inactive":
            session.get_one(Product, product).is_active = False
        elif state == "deleted":
            deleted = session.get_one(Product, product)
            deleted.deleted_at = datetime.now(UTC)
            deleted.deleted_by = people["admin"][0]
            deleted.is_active = False
        else:
            product = other_product
    result = request(
        "POST",
        f"/products/{product}/team/members",
        people["owner"][1],
        json={"email": email, "display_name": "New", "role": "viewer"},
    )
    assert result.status_code == expected
    with factory() as session:
        assert session.scalar(select(User.id).where(User.email == "new@example.com")) is None


def test_admin_recovery_and_demoted_owner_loses_team_authority(setup_team):
    from verboflex.models.product import Product
    from verboflex.services.admin_users import deactivate_admin_user

    factory, _, people, product, _ = setup_team
    path = f"/products/{product}/team"
    with factory() as session:
        deactivate_admin_user(session, actor_id=people["admin"][0], target_id=people["owner"][0])
    assert request("GET", path, people["admin"][1]).json()["has_active_owner"] is False
    assert (
        request(
            "PUT",
            path + "/members",
            people["admin"][1],
            json={"email": "other@example.com", "role": "product_owner"},
        ).status_code
        == 204
    )
    members = request("GET", path, people["other"][1]).json()["members"]
    other = next(m for m in members if m["email"] == "other@example.com")
    assert (
        request(
            "PUT",
            path + "/members",
            people["admin"][1],
            json={
                "email": "other@example.com",
                "role": "viewer",
                "expected_version": other["version"],
            },
        ).status_code
        == 204
    )
    assert request("GET", path, people["other"][1]).status_code == 403
    with factory.begin() as session:
        session.get_one(Product, product).is_active = False
    assert request("GET", path, people["admin"][1]).status_code == 200
    response = request(
        "POST",
        path + "/members",
        people["admin"][1],
        json={"email": "new@example.com", "display_name": "New", "role": "viewer"},
    )
    assert response.status_code == 409


def test_missing_viewer_configuration_rolls_back_new_account(setup_team):
    from verboflex.models.role import Role

    factory, _, people, product, _ = setup_team
    with factory.begin() as session:
        role = session.scalar(select(Role).where(Role.name == "viewer"))
        role_id = role.id
        role.name = "temporarily-unconfigured"
    try:
        result = request(
            "POST",
            f"/products/{product}/team/members",
            people["admin"][1],
            json={"email": "new@example.com", "display_name": "New", "role": "translator"},
        )
        assert result.status_code == 503
        with factory() as session:
            assert session.scalar(select(User.id).where(User.email == "new@example.com")) is None
    finally:
        with factory.begin() as session:
            session.get_one(Role, role_id).name = "viewer"


def test_member_inputs_and_admin_targets_are_protected(setup_team):
    factory, _, people, product, _ = setup_team
    path = f"/products/{product}/team"
    with factory.begin() as session:
        row = ProductMember(product_id=product, user_id=people["admin"][0], role="viewer")
        session.add(row)
        session.flush()
        version = str(row.version)
    assert (
        request(
            "PUT",
            path + "/members",
            people["owner"][1],
            json={"email": "admin@example.com", "role": "translator", "expected_version": version},
        ).status_code
        == 403
    )
    assert (
        request(
            "PUT",
            path + "/members",
            people["admin"][1],
            json={"email": "missing@example.com", "role": "viewer"},
        ).status_code
        == 409
    )
    assert (
        request(
            "PUT",
            f"/products/{uuid4()}/team/members",
            people["admin"][1],
            json={"email": "reader@example.com", "role": "viewer"},
        ).status_code
        == 404
    )
    assert request("GET", f"/products/{uuid4()}/access", people["owner"][1]).json()["role"] is None


def test_service_rejects_privileged_role_even_without_http_validation(setup_team):
    from verboflex.schemas.product_team import AddMemberInput

    factory, _, people, product, _ = setup_team
    forged = AddMemberInput.model_construct(
        email="new@example.com", display_name="New", role="product_owner"
    )
    with pytest.raises(service.TeamError, match="Only administrators"), factory.begin() as session:
        service.add_member(session, product, people["owner"][0], forged)
    with factory() as session:
        assert session.scalar(select(User.id).where(User.email == "new@example.com")) is None


def test_admin_stamp_rotates_after_global_account_authority_change(setup_team):
    factory, _, people, product, _ = setup_team
    with factory.begin() as session:
        before = membership_stamp(session, people["admin"][0], product)
        session.get_one(User, people["admin"][0]).token_version += 1
    with factory() as session:
        assert membership_stamp(session, people["admin"][0], product) != before


def test_account_and_membership_rollback_if_team_receipt_cannot_commit(setup_team, monkeypatch):
    from tests.api.test_product_team_credentials import provision

    factory, _, _, product, _ = setup_team

    def unavailable(*args, **kwargs):
        raise RuntimeError("synthetic audit failure")

    monkeypatch.setattr(service, "_event", unavailable)
    with pytest.raises(RuntimeError, match="synthetic audit failure"):
        provision(setup_team)
    with factory() as session:
        assert session.scalar(select(User.id).where(User.email == "new@example.com")) is None
        assert (
            session.scalar(
                select(ProductTeamEvent.id).where(ProductTeamEvent.product_id == product)
            )
            is None
        )
