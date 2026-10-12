"""Temporary credentials are returned once and never reset existing accounts."""
# ruff: noqa: F401, F811

from sqlalchemy import select

from tests.api.test_product_team import (
    admin_session_factory,
    clean_admin_users_database,
    request,
    setup_team,
)
from verboflex.auth.passwords import verify_password
from verboflex.models.product_member import ProductMember, ProductTeamEvent
from verboflex.models.user import User


def provision(setup, email="new@example.com", **changes):
    _, _, people, product, _ = setup
    return request(
        "POST",
        f"/products/{product}/team/members",
        people["owner"][1],
        json={"email": email, "display_name": "New Translator", "role": "translator", **changes},
    )


def test_new_account_returns_one_time_temporary_password_and_rejects_replay(setup_team):
    factory, _, people, product, other_product = setup_team
    response = provision(setup_team, " NEW@EXAMPLE.COM ")
    assert response.status_code == 201, response.text
    assert response.headers["cache-control"] == "no-store"
    result = response.json()
    password = result["temporary_password"]
    assert len(password) == 32
    assert result["account_created"] is True
    with factory() as session:
        user = session.scalar(select(User).where(User.email == "new@example.com"))
        assert verify_password(password, user.hashed_password)
        assert user.must_change_password and user.is_active
        assert [r.name for r in user.roles] == ["viewer"]
        assert session.get_one(ProductMember, (product, user.id)).role == "translator"
        assert session.get(ProductMember, (other_product, user.id)) is None
        assert password not in str([e.__dict__ for e in session.scalars(select(ProductTeamEvent))])
        password_hash = user.hashed_password
    assert provision(setup_team).status_code == 409
    with factory() as session:
        assert (
            session.scalar(select(User).where(User.email == "new@example.com")).hashed_password
            == password_hash
        )
    team = request("GET", f"/products/{product}/team", people["owner"][1])
    assert password not in team.text and "temporary_password" not in team.text


def test_existing_account_joins_without_changing_identity_password_or_sessions(setup_team):
    factory, _, people, product, _ = setup_team
    with factory() as session:
        user = session.get_one(User, people["other"][0])
        before = (
            user.hashed_password,
            user.display_name,
            user.token_version,
            user.must_change_password,
        )
    response = provision(setup_team, " OTHER@example.com ")
    assert response.status_code == 201, response.text
    assert response.json()["account_created"] is False
    assert response.json()["temporary_password"] is None
    with factory() as session:
        user = session.get_one(User, people["other"][0])
        assert (
            user.hashed_password,
            user.display_name,
            user.token_version,
            user.must_change_password,
        ) == before
        assert session.get_one(ProductMember, (product, user.id)).role == "translator"
    assert request("GET", "/users/me", people["other"][1]).status_code == 200


def test_first_login_requires_change_and_invalidates_temporary_password(setup_team):
    _, _, _, product, other_product = setup_team
    password = provision(setup_team).json()["temporary_password"]
    login = request(
        "POST", "/auth/token", data={"username": "new@example.com", "password": password}
    )
    assert login.status_code == 200, login.text
    assert login.json()["must_change_password"] is True
    assert "set-cookie" not in login.headers
    restricted = login.json()["access_token"]
    assert request("GET", "/users/me", restricted).status_code == 403
    assert request("GET", f"/products/{product}/access", restricted).status_code == 403
    unchanged = request(
        "POST",
        "/auth/change-password",
        restricted,
        json={"current_password": password, "new_password": password},
    )
    assert unchanged.status_code == 422
    changed = request(
        "POST",
        "/auth/change-password",
        restricted,
        json={"current_password": password, "new_password": "new synthetic chosen password!"},
    )
    assert changed.status_code == 204, changed.text
    assert (
        request(
            "POST", "/auth/token", data={"username": "new@example.com", "password": password}
        ).status_code
        == 401
    )
    login = request(
        "POST",
        "/auth/token",
        data={"username": "new@example.com", "password": "new synthetic chosen password!"},
    )
    assert login.status_code == 200 and login.json()["must_change_password"] is False
    token = login.json()["access_token"]
    assert request("GET", f"/products/{product}/access", token).json()["role"] == "translator"
    assert request("GET", f"/products/{other_product}/access", token).json()["role"] is None


def test_concurrent_provision_has_one_password_and_does_not_overwrite_role(setup_team):
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: provision(setup_team), range(2)))
    assert sorted(r.status_code for r in results) == [201, 409]
    assert sum("temporary_password" in r.json() for r in results) == 1
    assert provision(setup_team, role="viewer").status_code == 409
    factory, _, _, product, _ = setup_team
    with factory() as session:
        user = session.scalar(select(User).where(User.email == "new@example.com"))
        assert session.get_one(ProductMember, (product, user.id)).role == "translator"


def test_readding_removed_member_preserves_password_but_rotates_authority(setup_team):
    from verboflex.auth.product_access import membership_stamp
    from verboflex.services import product_team as service

    factory, _, people, product, other_product = setup_team
    with factory.begin() as session:
        session.add(
            ProductMember(
                product_id=other_product, user_id=people["other"][0], role="product_owner"
            )
        )
    assert provision(setup_team, "other@example.com").status_code == 201
    with factory.begin() as session:
        member = session.get_one(ProductMember, (product, people["other"][0]))
        stamp = membership_stamp(session, member.user_id, product)
        service.remove_member(session, product, people["owner"][0], member.user_id, member.version)
    assert request("GET", f"/products/{product}/access", people["other"][1]).json()["role"] is None
    assert (
        request("GET", f"/products/{other_product}/access", people["other"][1]).json()["role"]
        == "product_owner"
    )
    result = provision(setup_team, "other@example.com", role="viewer")
    assert result.status_code == 201 and result.json()["temporary_password"] is None
    with factory() as session:
        assert membership_stamp(session, people["other"][0], product) != stamp


def test_existing_account_awaiting_password_change_does_not_receive_new_password(setup_team):
    factory, _, people, _, _ = setup_team
    with factory.begin() as session:
        user = session.get_one(User, people["other"][0])
        user.must_change_password = True
        before = user.hashed_password
    result = provision(setup_team, "other@example.com")
    assert result.status_code == 201 and result.json()["temporary_password"] is None
    with factory() as session:
        user = session.get_one(User, people["other"][0])
        assert user.must_change_password and user.hashed_password == before
