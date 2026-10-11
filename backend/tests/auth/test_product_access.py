"""Closed delegation policy: product owners cannot appoint or remove owners."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from verboflex.auth.product_access import may_manage_member


@pytest.mark.parametrize("current", [None, "viewer", "translator", "product_manager_reviewer"])
@pytest.mark.parametrize("requested", [None, "viewer", "translator", "product_manager_reviewer"])
def test_owner_can_manage_operational_members(current, requested):
    assert may_manage_member("product_owner", current, requested)


@pytest.mark.parametrize("actor", ["viewer", "translator", "product_manager_reviewer", "unknown"])
def test_operational_roles_cannot_manage_team(actor):
    assert not may_manage_member(actor, "viewer", "translator")


@pytest.mark.parametrize(
    "current,requested",
    [
        ("product_owner", None),
        ("product_owner", "viewer"),
        (None, "product_owner"),
        ("viewer", "admin"),
        ("admin", None),
    ],
)
def test_owner_cannot_modify_privileged_roles(current, requested):
    assert not may_manage_member("product_owner", current, requested)


@given(
    st.sampled_from([None, "viewer", "translator", "product_manager_reviewer", "product_owner"]),
    st.sampled_from([None, "viewer", "translator", "product_manager_reviewer", "product_owner"]),
)
def test_property_admin_can_manage_all_product_roles(current, requested):
    assert may_manage_member("admin", current, requested)


@given(
    st.text().filter(
        lambda value: (
            value not in {"viewer", "translator", "product_manager_reviewer", "product_owner"}
        )
    )
)
def test_property_unknown_roles_fail_closed(requested):
    assert not may_manage_member("admin", None, requested)


@given(
    st.one_of(
        st.none(),
        st.sampled_from(
            ["viewer", "translator", "product_manager_reviewer", "product_owner", "admin"]
        ),
        st.text(),
    ),
    st.one_of(
        st.none(),
        st.sampled_from(
            ["viewer", "translator", "product_manager_reviewer", "product_owner", "admin"]
        ),
        st.text(),
    ),
)
def test_property_owner_delegation_is_exactly_the_operational_role_set(current, requested):
    operational = {None, "viewer", "translator", "product_manager_reviewer"}
    assert may_manage_member("product_owner", current, requested) == (
        current in operational and requested in operational
    )


@given(st.text().filter(lambda actor: actor not in {"admin", "product_owner"}))
def test_property_unknown_actor_never_manages_members(actor):
    assert not may_manage_member(actor, "viewer", "translator")
