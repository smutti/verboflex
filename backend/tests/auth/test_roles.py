"""Contracts for reusable server-side role dependencies."""

from uuid import uuid4

import pytest
from fastapi import HTTPException

from verboflex.auth.principal import Principal, require_roles
from verboflex.schemas.users import RoleName


def principal_with(*roles: RoleName) -> Principal:
    """Build an already database-resolved safe principal."""
    return Principal(
        user_id=uuid4(),
        email="person@example.com",
        display_name="Person Example",
        roles=tuple(sorted(roles)),
        must_change_password=False,
    )


def test_role_dependency_allows_exact_database_role_and_denies_viewer() -> None:
    """Allow any configured accepted role and return exact 403 otherwise."""
    dependency = require_roles(RoleName.ADMIN, RoleName.PRODUCT_MANAGER_REVIEWER)
    admin = principal_with(RoleName.ADMIN)
    product_manager_reviewer = principal_with(RoleName.PRODUCT_MANAGER_REVIEWER)
    viewer = principal_with(RoleName.VIEWER)

    assert dependency(admin) is admin
    assert dependency(product_manager_reviewer) is product_manager_reviewer
    with pytest.raises(HTTPException) as denial:
        dependency(viewer)
    assert denial.value.status_code == 403
    assert denial.value.detail == "Insufficient permissions"


def test_role_dependency_requires_an_explicit_allowlist() -> None:
    """Fail configuration closed instead of creating a dependency that denies opaquely."""
    with pytest.raises(ValueError, match="at least one allowed role is required"):
        require_roles()
