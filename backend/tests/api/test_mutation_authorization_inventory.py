"""Exhaustive route inventory and direct HTTP denials with zero database writes."""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import event

from tests.api.test_admin_products import configure_dependencies, create_authority
from tests.api.test_admin_products import product_session_factory as _product_session_factory
from verboflex.main import app

POLICIES = json.loads((Path(__file__).parents[1] / "architecture/mutation_policy.json").read_text())


@pytest.fixture(scope="module")
def policy_factory():
    yield from _product_session_factory.__wrapped__()


def test_every_mutation_has_an_explicit_policy_and_audit_owner():
    actual = {
        op["operationId"]: (method.upper(), path)
        for path, methods in app.openapi()["paths"].items()
        for method, op in methods.items()
        if method in {"post", "patch", "put", "delete"}
    }
    assert actual == {name: (rule["method"], rule["path"]) for name, rule in POLICIES.items()}
    assert all(rule["audit"] and rule["boundary"] for rule in POLICIES.values())


def test_separately_mounted_oauth_protocol_has_a_closed_mutation_inventory():
    from verboflex.api.mcp_oauth import router

    # Protocol credentials/PKCE replace application role dependencies here.
    # Consent and grant revocation are already in the versioned API inventory.
    mutations = {
        (method, route.path)
        for route in router.routes
        for method in getattr(route, "methods", set()) & {"POST", "PUT", "PATCH", "DELETE"}
        if not getattr(route, "include_in_schema", True)
    }
    assert mutations == {
        ("POST", "/oauth/register"),
        ("POST", "/oauth/token"),
        ("POST", "/oauth/revoke"),
    }


@pytest.mark.parametrize(
    "role", ["anonymous", "viewer", "translator", "product_manager_reviewer", "revoked_admin"]
)
def test_direct_denials_never_write_or_reach_route_effects(policy_factory, role):
    factory = policy_factory
    configure_dependencies(factory)
    token = None
    if role != "anonymous":
        user_id, token = create_authority(
            factory,
            email=f"policy-{uuid4()}@example.com",
            roles=["admin" if role == "revoked_admin" else role],
        )
        if role == "revoked_admin":
            from verboflex.models.user import User

            with factory.begin() as session:
                session.get_one(User, user_id).token_version += 1
    writes = []

    def capture(_conn, _cursor, statement, _parameters, _context, _many):
        if statement.lstrip().split(None, 1)[0].upper() in {
            "INSERT",
            "UPDATE",
            "DELETE",
            "TRUNCATE",
        }:
            writes.append(statement.split(None, 1)[0])

    engine = factory.kw["bind"]
    event.listen(engine, "before_cursor_execute", capture)
    try:
        asyncio.run(_denied_requests(token, role))
    finally:
        event.remove(engine, "before_cursor_execute", capture)
        app.dependency_overrides.clear()
    assert writes == []


async def _denied_requests(token, role):
    checked = 0
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        for name, rule in POLICIES.items():
            if rule["boundary"] == "credential_protocol":
                continue
            if role in {"anonymous", "revoked_admin"}:
                expected = 401
            elif rule["boundary"] == "role_dependency" and role not in rule["roles"]:
                expected = 403
            else:
                # Active-resource/ownership matrices are exercised against valid seeded
                # resources in translation, submission, notification and MCP API tests.
                continue
            path = re.sub(r"\{[^}]+\}", str(uuid4()), rule["path"])
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            body = (
                {"current_password": "old password fixture", "new_password": "new password fixture"}
                if name == "change_password"
                else {}
            )
            result = await client.request(rule["method"], path, json=body, headers=headers)
            assert result.status_code == expected, (name, role, result.status_code)
            checked += 1
    assert checked >= 25
