"""Pure future pull-request grouping by exact repository and target branch."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class PullRequestGroupKey:
    """The complete and only identity of one future pull-request group."""

    repository_id: UUID
    target_branch: str


@dataclass(frozen=True, slots=True)
class PullRequestGroupingPreview:
    """Configuration-only metadata for exact allowed and default group keys."""

    repository_id: UUID
    allowed_target_branches: tuple[str, ...]
    default_target_branch: str

    def __post_init__(self) -> None:
        allowed = self.allowed_target_branches
        if (
            not allowed
            or any(not isinstance(branch, str) or not branch for branch in allowed)
            or len(set(allowed)) != len(allowed)
        ):
            raise ValueError("allowed target branches must be a nonempty exact set")
        if self.default_target_branch not in allowed:
            raise ValueError("default target must be allowed")

    @property
    def default_key(self) -> PullRequestGroupKey:
        """Return the configured default repository/target identity."""
        return self.key_for_target(self.default_target_branch)

    def key_for_target(self, target_branch: str) -> PullRequestGroupKey:
        """Return an exact allowed group identity without normalizing the branch."""
        if target_branch not in self.allowed_target_branches:
            raise ValueError("target branch is not allowed")
        return PullRequestGroupKey(
            repository_id=self.repository_id,
            target_branch=target_branch,
        )


@dataclass(frozen=True, slots=True)
class PullRequestChange:
    """One compatible future change carrying non-key grouping metadata."""

    repository_id: UUID
    target_branch: str
    mapping_id: UUID
    file_path: str
    language: str


@dataclass(frozen=True, slots=True)
class PullRequestGroup:
    """One deterministic group whose key never includes mapping, file, or language."""

    repository_id: UUID
    target_branch: str
    changes: tuple[PullRequestChange, ...]


def group_pull_request_changes(
    changes: Iterable[PullRequestChange],
) -> tuple[PullRequestGroup, ...]:
    """Group changes solely by exact repository UUID and target branch."""
    grouped: dict[PullRequestGroupKey, list[PullRequestChange]] = defaultdict(list)
    for change in changes:
        if not isinstance(change, PullRequestChange):
            raise TypeError("changes must be PullRequestChange values")
        grouped[
            PullRequestGroupKey(
                repository_id=change.repository_id,
                target_branch=change.target_branch,
            )
        ].append(change)

    return tuple(
        PullRequestGroup(
            repository_id=key.repository_id,
            target_branch=key.target_branch,
            changes=tuple(
                sorted(
                    grouped[key],
                    key=lambda change: (
                        change.mapping_id.int,
                        change.file_path,
                        change.language,
                    ),
                )
            ),
        )
        for key in sorted(
            grouped,
            key=lambda group_key: (
                group_key.repository_id.int,
                group_key.target_branch,
            ),
        )
    )
