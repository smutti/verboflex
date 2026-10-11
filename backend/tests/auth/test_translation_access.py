"""Closed role and resource-privacy contract for translation-group access."""

from __future__ import annotations

import ast
import importlib
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import ANY, Mock
from uuid import UUID, uuid4

import pytest

from verboflex.auth.principal import Principal
from verboflex.schemas.users import RoleName
from verboflex.services.translation_search import TranslationGroupUnavailable


@pytest.fixture
def access_module() -> ModuleType:
    """Import lazily so the RED suite collects before the module exists."""
    return importlib.import_module("verboflex.auth.translation_access")


@pytest.fixture
def product_id() -> UUID:
    return uuid4()


@pytest.fixture
def group_id() -> UUID:
    return uuid4()


@pytest.fixture
def available_group(group_id: UUID, product_id: UUID) -> SimpleNamespace:
    return SimpleNamespace(id=group_id, product_id=product_id, is_deleted=False)


def principal_with(role: RoleName) -> Principal:
    """Build the same immutable authority projection returned from durable state."""
    return Principal(
        user_id=uuid4(),
        email="person@example.com",
        display_name="Person Example",
        roles=(role,),
        must_change_password=False,
    )


ROLE_ACTION_MATRIX = (
    (RoleName.ADMIN, "read", True),
    (RoleName.ADMIN, "propose", True),
    (RoleName.ADMIN, "comment", True),
    (RoleName.ADMIN, "review", True),
    (RoleName.ADMIN, "delete_comment", True),
    (RoleName.PRODUCT_MANAGER_REVIEWER, "read", True),
    (RoleName.PRODUCT_MANAGER_REVIEWER, "propose", True),
    (RoleName.PRODUCT_MANAGER_REVIEWER, "comment", True),
    (RoleName.PRODUCT_MANAGER_REVIEWER, "review", True),
    (RoleName.PRODUCT_MANAGER_REVIEWER, "delete_comment", False),
    (RoleName.TRANSLATOR, "read", True),
    (RoleName.TRANSLATOR, "propose", True),
    (RoleName.TRANSLATOR, "comment", True),
    (RoleName.TRANSLATOR, "review", False),
    (RoleName.TRANSLATOR, "delete_comment", False),
    (RoleName.VIEWER, "read", True),
    (RoleName.VIEWER, "propose", False),
    (RoleName.VIEWER, "comment", False),
    (RoleName.VIEWER, "review", False),
    (RoleName.VIEWER, "delete_comment", False),
)


@pytest.mark.parametrize(
    ("role", "mode_value", "allowed"),
    ROLE_ACTION_MATRIX,
    ids=lambda value: value.value if isinstance(value, RoleName) else str(value),
)
def test_closed_role_action_matrix(
    access_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    available_group: SimpleNamespace,
    group_id: UUID,
    product_id: UUID,
    role: RoleName,
    mode_value: str,
    allowed: bool,
) -> None:
    lookup = Mock(return_value=available_group)
    monkeypatch.setattr(access_module, "get_translation_group", lookup)
    mode = access_module.TranslationGroupAccessMode(mode_value)

    if allowed:
        result = access_module.resolve_translation_group_access(
            Mock(),
            principal=principal_with(role),
            translation_group_id=group_id,
            mode=mode,
        )
        assert result.group is available_group
        assert result.product_id == product_id
        with pytest.raises(FrozenInstanceError):
            result.product_id = uuid4()
    else:
        with pytest.raises(
            access_module.TranslationGroupActionDenied,
            match=r"^translation action denied$",
        ):
            access_module.resolve_translation_group_access(
                Mock(),
                principal=principal_with(role),
                translation_group_id=group_id,
                mode=mode,
            )

    lookup.assert_called_once_with(ANY, group_id=group_id)


def test_mode_vocabulary_and_exception_contract_are_closed(access_module: ModuleType) -> None:
    assert [mode.value for mode in access_module.TranslationGroupAccessMode] == [
        "read",
        "propose",
        "comment",
        "review",
        "delete_comment",
    ]
    assert issubclass(access_module.TranslationGroupAccessUnavailable, LookupError)
    assert issubclass(access_module.TranslationGroupActionDenied, PermissionError)


def test_retained_deleted_group_remains_readable(
    access_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    available_group: SimpleNamespace,
    group_id: UUID,
) -> None:
    available_group.is_deleted = True
    monkeypatch.setattr(access_module, "get_translation_group", Mock(return_value=available_group))

    result = access_module.resolve_translation_group_access(
        Mock(),
        principal=principal_with(RoleName.VIEWER),
        translation_group_id=group_id,
        mode=access_module.TranslationGroupAccessMode.READ,
    )

    assert result.group is available_group
    assert result.group.is_deleted is True


@pytest.mark.parametrize(
    ("condition", "lookup_result"),
    (
        ("absent", TranslationGroupUnavailable("missing group")),
        ("inactive-product", TranslationGroupUnavailable("inactive product")),
        ("stale-dataset", TranslationGroupUnavailable("stale dataset")),
        ("foreign-product-scope", TranslationGroupUnavailable("foreign product scope")),
        ("malformed-result", None),
    ),
)
def test_all_inaccessible_group_conditions_are_indistinguishable(
    access_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    group_id: UUID,
    condition: str,
    lookup_result: object,
) -> None:
    del condition
    lookup = Mock()
    if isinstance(lookup_result, Exception):
        lookup.side_effect = lookup_result
    else:
        lookup.return_value = lookup_result
    monkeypatch.setattr(access_module, "get_translation_group", lookup)
    subordinate_lookup = Mock()

    with pytest.raises(
        access_module.TranslationGroupAccessUnavailable,
        match=r"^translation unavailable$",
    ) as unavailable:
        access = access_module.resolve_translation_group_access(
            Mock(),
            principal=principal_with(RoleName.VIEWER),
            translation_group_id=group_id,
            mode=access_module.TranslationGroupAccessMode.DELETE_COMMENT,
        )
        subordinate_lookup(access.group)

    assert str(unavailable.value) == "translation unavailable"
    lookup.assert_called_once_with(ANY, group_id=group_id)
    subordinate_lookup.assert_not_called()


def test_group_authority_is_resolved_before_action_denial(
    access_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    available_group: SimpleNamespace,
    group_id: UUID,
) -> None:
    lookup = Mock(return_value=available_group)
    monkeypatch.setattr(access_module, "get_translation_group", lookup)

    with pytest.raises(access_module.TranslationGroupActionDenied):
        access_module.resolve_translation_group_access(
            Mock(),
            principal=principal_with(RoleName.VIEWER),
            translation_group_id=group_id,
            mode=access_module.TranslationGroupAccessMode.COMMENT,
        )

    lookup.assert_called_once()


def test_unknown_runtime_mode_fails_closed_after_group_authority(
    access_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    available_group: SimpleNamespace,
    group_id: UUID,
) -> None:
    lookup = Mock(return_value=available_group)
    monkeypatch.setattr(access_module, "get_translation_group", lookup)

    with pytest.raises(
        access_module.TranslationGroupActionDenied,
        match=r"^translation action denied$",
    ):
        access_module.resolve_translation_group_access(
            Mock(),
            principal=principal_with(RoleName.ADMIN),
            translation_group_id=group_id,
            mode="export",
        )

    lookup.assert_called_once()


def test_translation_access_resolver_has_one_definition_and_no_service_bypass(
    access_module: ModuleType,
) -> None:
    del access_module
    source_root = Path(__file__).parents[2] / "src" / "verboflex"
    resolver_definitions: list[Path] = []
    for path in source_root.rglob("*.py"):
        tree = ast.parse(path.read_text())
        if any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "resolve_translation_group_access"
            for node in ast.walk(tree)
        ):
            resolver_definitions.append(path.relative_to(source_root))

    assert resolver_definitions == [Path("auth/translation_access.py")]

    for service_name in ("translation_reviews.py", "translation_comments.py", "notifications.py"):
        service_path = source_root / "services" / service_name
        if not service_path.exists():
            continue
        source = service_path.read_text()
        assert "verboflex.auth.translation_access" in source
        assert "get_translation_group" not in source
