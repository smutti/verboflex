"""Synthetic HTTP and transactional checks for product-scoped delegation."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import text

from tests.api.test_admin_users import (  # noqa: F401
    admin_session_factory,
    configure_admin_dependencies,
    create_authority,
)
from verboflex.auth.product_access import membership_stamp
from verboflex.auth.rate_limits import get_redis_client
from verboflex.core.config import Settings, get_settings
from verboflex.main import app
from verboflex.models.product import Product
from verboflex.models.product_member import ProductMember
from verboflex.schemas.product_team import MemberInput
from verboflex.services import product_team as service

PASSWORD = "principal password phrase!"


@pytest.fixture(autouse=True)
def clean_admin_users_database(admin_session_factory):  # noqa: F811
    app.dependency_overrides.clear()
    with admin_session_factory.begin() as session:
        session.execute(text("TRUNCATE products, repositories, users CASCADE"))
    yield
    app.dependency_overrides.clear()
    with admin_session_factory.begin() as session:
        session.execute(text("TRUNCATE products, repositories, users CASCADE"))


@pytest.fixture
def setup_team(admin_session_factory):  # noqa: F811
    factory = admin_session_factory

    class RateRedis:
        def eval(self, *args):
            return [1, 60]

    app.dependency_overrides[get_redis_client] = lambda: RateRedis()
    configure_admin_dependencies(factory)
    settings = Settings(
        jwt_secret_key=SecretStr("0123456789abcdef" * 2),
    )
    app.dependency_overrides[get_settings] = lambda: settings
    people = {}
    for name, roles in [
        ("admin", ["admin"]),
        ("owner", ["viewer"]),
        ("other", ["viewer"]),
        ("reader", ["viewer"]),
    ]:
        people[name] = create_authority(factory, email=f"{name}@example.com", roles=roles)
    product_id, other_product = uuid4(), uuid4()
    with factory.begin() as session:
        session.add_all(
            [
                Product(
                    id=product_id,
                    display_name="Team Alpha",
                    name_key=f"alpha{product_id}",
                    is_active=True,
                ),
                Product(
                    id=other_product,
                    display_name="Team Beta",
                    name_key=f"beta{other_product}",
                    is_active=True,
                ),
            ]
        )
        session.flush()
        session.add_all(
            [
                ProductMember(
                    product_id=product_id, user_id=people["owner"][0], role="product_owner"
                ),
                ProductMember(product_id=other_product, user_id=people["owner"][0], role="viewer"),
                ProductMember(product_id=product_id, user_id=people["reader"][0], role="viewer"),
            ]
        )
    return factory, settings, people, product_id, other_product


def request(method, path, token=None, **kwargs):
    async def run():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.request(
                method,
                "/api/v1" + path,
                headers={"Authorization": f"Bearer {token}"} if token else {},
                **kwargs,
            )

    return asyncio.run(run())


def test_po_cannot_appoint_or_remove_owner_and_cannot_manage_other_product(setup_team):
    _, _, people, product_id, other_product = setup_team
    owner = people["owner"][1]
    prefix = f"/products/{product_id}/team"
    response = request("GET", prefix, owner)
    assert response.status_code == 200
    member = next(m for m in response.json()["members"] if m["role"] == "product_owner")
    for role in ("product_owner", "admin"):
        response = request(
            "PUT", prefix + "/members", owner, json={"email": "other@example.com", "role": role}
        )
        assert response.status_code in (403, 422)
    assert (
        request(
            "DELETE",
            prefix + f"/members/{member['user_id']}",
            owner,
            params={"expected_version": member["version"]},
        ).status_code
        == 403
    )
    assert request("GET", f"/products/{other_product}/team", owner).status_code == 403
    assert request("GET", f"/products/{other_product}/access", owner).json()["roles"] == ["viewer"]
    assert (
        request(
            "PATCH",
            "/admin/users/" + str(people["other"][0]),
            owner,
            json={"display_name": "Other", "roles": ["admin"]},
        ).status_code
        == 403
    )


def test_concurrent_role_changes_have_one_winner_and_old_stamp_stays_invalid(setup_team):
    factory, _, people, product_id, _ = setup_team
    with factory() as session:
        member = session.get_one(ProductMember, (product_id, people["reader"][0]))
        version = member.version
        old_stamp = membership_stamp(session, member.user_id, product_id)

    def change(role):
        try:
            with factory.begin() as session:
                service.set_member(
                    session,
                    product_id,
                    people["owner"][0],
                    MemberInput(email="reader@example.com", role=role, expected_version=version),
                )
            return "ok"
        except service.TeamError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(change, ["translator", "product_manager_reviewer"])) == [
            "conflict",
            "ok",
        ]
    with factory() as session:
        assert membership_stamp(session, people["reader"][0], product_id) != old_stamp


def test_reads_exclude_unassigned_products_and_user_directory(setup_team):
    _, _, people, product_id, other_product = setup_team
    token = people["reader"][1]
    products = request("GET", "/products/workspace", token)
    assert products.status_code == 200
    assert [p["id"] for p in products.json()["items"]] == [str(product_id)]
    options = request("GET", "/translations/options", token)
    assert options.status_code == 200
    assert str(other_product) not in options.text
    assert request("GET", f"/products/{other_product}/access", token).json()["role"] is None


def test_cross_product_content_and_membership_revocation(setup_team):
    from tests.api.test_translation_reviews import _payload, _seed_scalar_basis

    factory, _, people, _, _ = setup_team
    visible = _seed_scalar_basis(factory, name="Visible translations")
    hidden = _seed_scalar_basis(factory, name="Hidden translations")
    with factory.begin() as session:
        from verboflex.models.translation import TranslationValue

        a = session.get_one(TranslationValue, visible["group"]).key.product_id
        b = session.get_one(TranslationValue, hidden["group"]).key.product_id
        session.add(ProductMember(product_id=a, user_id=people["owner"][0], role="translator"))
        session.add(ProductMember(product_id=b, user_id=people["owner"][0], role="viewer"))
    token = people["owner"][1]
    assert (
        request(
            "PUT",
            f"/translations/{visible['group']}/proposal",
            token,
            json=_payload(visible, "Synthetic draft"),
        ).status_code
        == 200
    )
    assert (
        request(
            "PUT",
            f"/translations/{hidden['group']}/proposal",
            token,
            json=_payload(hidden, "Denied draft"),
        ).status_code
        == 403
    )
    with factory.begin() as session:
        member = session.get_one(ProductMember, (a, people["owner"][0]))
        service.remove_member(session, a, people["admin"][0], people["owner"][0], member.version)
    assert request("GET", f"/translations/{visible['group']}", token).status_code == 404
    assert request("GET", f"/translations/{hidden['group']}", token).status_code == 200
    assert (
        request(
            "PUT",
            f"/translations/{visible['group']}/proposal",
            token,
            json=_payload(visible, "Stale tab draft"),
        ).status_code
        == 404
    )
    for path in (
        "/translations",
        "/translations/keys",
        "/translations/options",
        "/dashboard",
        "/dashboard/project-updates",
    ):
        result = request("GET", path, token)
        assert result.status_code == 200, (path, result.text)
        assert str(a) not in result.text


def test_po_cannot_remove_global_administrator_membership(setup_team):
    factory, _, people, product_id, _ = setup_team
    with factory.begin() as session:
        member = ProductMember(product_id=product_id, user_id=people["admin"][0], role="viewer")
        session.add(member)
        session.flush()
        version = member.version
    response = request(
        "DELETE",
        f"/products/{product_id}/team/members/{people['admin'][0]}",
        people["owner"][1],
        params={"expected_version": str(version)},
    )
    assert response.status_code == 403
    with factory() as session:
        assert session.get_one(ProductMember, (product_id, people["admin"][0])).active
