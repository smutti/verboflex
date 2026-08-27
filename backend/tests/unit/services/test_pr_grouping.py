"""Pure repository and target-branch pull-request grouping contract."""

from __future__ import annotations

import ast
import importlib
import inspect
from itertools import chain
from pathlib import Path
from types import ModuleType
from uuid import UUID

import pytest
from hypothesis import given
from hypothesis import strategies as st

REPOSITORY_ALPHA = UUID("00000000-0000-0000-0000-000000000001")
REPOSITORY_BETA = UUID("00000000-0000-0000-0000-000000000002")
CHANGE_ROWS = (
    (REPOSITORY_ALPHA, "release/1", UUID(int=11), "res/values/strings.xml", "en"),
    (REPOSITORY_ALPHA, "release/1", UUID(int=12), "res/values-it/strings.xml", "it"),
    (REPOSITORY_ALPHA, "release/1", UUID(int=11), "res/values-fr/strings.xml", "fr"),
    (REPOSITORY_ALPHA, "Release/1", UUID(int=11), "res/values/strings.xml", "en"),
    (REPOSITORY_BETA, "release/1", UUID(int=11), "locales/en.json", "en"),
)


def _grouping_module() -> ModuleType:
    try:
        return importlib.import_module("verboflex.services.pr_grouping")
    except ModuleNotFoundError as error:
        pytest.fail(f"pure PR grouping service must exist: {error}")


def _changes(module: ModuleType, rows: object = CHANGE_ROWS) -> tuple[object, ...]:
    return tuple(
        module.PullRequestChange(
            repository_id=repository_id,
            target_branch=target_branch,
            mapping_id=mapping_id,
            file_path=file_path,
            language=language,
        )
        for repository_id, target_branch, mapping_id, file_path, language in rows
    )


def test_only_exact_repository_and_target_branch_determine_group_identity() -> None:
    """Files, languages, and mapping UUIDs share only their exact pair group."""
    module = _grouping_module()

    groups = module.group_pull_request_changes(_changes(module))

    assert tuple((group.repository_id, group.target_branch) for group in groups) == (
        (REPOSITORY_ALPHA, "Release/1"),
        (REPOSITORY_ALPHA, "release/1"),
        (REPOSITORY_BETA, "release/1"),
    )
    assert len(groups[1].changes) == 3
    assert {change.language for change in groups[1].changes} == {"en", "fr", "it"}
    assert {change.mapping_id for change in groups[1].changes} == {UUID(int=11), UUID(int=12)}
    assert {change.file_path for change in groups[1].changes} == {
        "res/values/strings.xml",
        "res/values-fr/strings.xml",
        "res/values-it/strings.xml",
    }


@given(st.permutations(CHANGE_ROWS))
def test_mapping_file_and_language_permutations_leave_groups_invariant(
    rows: list[tuple[UUID, str, UUID, str, str]],
) -> None:
    """Any input permutation yields the same deterministic groups and contents."""
    module = _grouping_module()
    expected = module.group_pull_request_changes(_changes(module))

    assert module.group_pull_request_changes(_changes(module, rows)) == expected


def test_different_repository_or_exact_target_branch_never_share_a_group() -> None:
    """No output group can cross either boundary, including branch casing."""
    module = _grouping_module()
    groups = module.group_pull_request_changes(_changes(module))

    flattened = tuple(chain.from_iterable(group.changes for group in groups))
    assert len(flattened) == len(CHANGE_ROWS)
    for group in groups:
        assert all(
            (change.repository_id, change.target_branch)
            == (group.repository_id, group.target_branch)
            for change in group.changes
        )


def test_empty_input_is_empty_and_grouping_has_no_provider_or_persistence_capability() -> None:
    """The contract is an in-memory transform with no provider, database, or PR job seam."""
    module = _grouping_module()

    assert module.group_pull_request_changes(()) == ()
    source_path = Path(inspect.getsourcefile(module) or "")
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported_roots = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        (node.module or "").split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert imported_roots <= {
        "__future__",
        "collections",
        "dataclasses",
        "typing",
        "uuid",
    }
    assert {
        "create_pull_request",
        "enqueue_pull_request",
        "persist_pull_request_job",
        "provider_client",
    }.isdisjoint(vars(module))


def test_grouping_preview_accepts_only_exact_configured_targets_and_default() -> None:
    """D-18 exposes keys only for the configured exact allowed/default branches."""
    module = _grouping_module()
    preview = module.PullRequestGroupingPreview(
        repository_id=REPOSITORY_ALPHA,
        allowed_target_branches=("release/1", "Release/1"),
        default_target_branch="release/1",
    )

    assert preview.default_key == module.PullRequestGroupKey(
        repository_id=REPOSITORY_ALPHA,
        target_branch="release/1",
    )
    assert preview.key_for_target("Release/1") == module.PullRequestGroupKey(
        repository_id=REPOSITORY_ALPHA,
        target_branch="Release/1",
    )
    with pytest.raises(ValueError, match="target branch is not allowed"):
        preview.key_for_target("release/2")

    with pytest.raises(ValueError, match="default target must be allowed"):
        module.PullRequestGroupingPreview(
            repository_id=REPOSITORY_ALPHA,
            allowed_target_branches=("release/1",),
            default_target_branch="release/2",
        )
