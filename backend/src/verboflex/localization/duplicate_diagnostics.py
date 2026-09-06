"""Bounded duplicate-source reports, separate from canonical import results."""

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass

from verboflex.integrations.bitbucket.urls import validate_repository_relative_path
from verboflex.localization.importing.core import (
    MAX_CANONICAL_AGGREGATE_BYTES,
    MAX_CANONICAL_FILES,
    MAX_CANONICAL_MAPPING_VALUES,
    CanonicalParserInput,
    canonical_selector_digest,
)
from verboflex.localization.importing.registry import inspect_duplicate_snapshot
from verboflex.localization.moko_layout import moko_layout

MAX_DIAGNOSTIC_BYTES = 16 * 1_048_576


@dataclass(frozen=True, slots=True)
class DuplicateOccurrence:
    path: str
    position: int


@dataclass(frozen=True, slots=True)
class DuplicateGroup:
    id: str
    repository_side: str
    language: str
    key_preview: str
    key_length: int
    occurrences: tuple[DuplicateOccurrence, ...]


@dataclass(frozen=True, slots=True)
class DuplicateReport:
    groups: tuple[DuplicateGroup, ...] = ()
    complete: bool = True
    issue_codes: tuple[str, ...] = ()

    @property
    def repeated_occurrences(self) -> int:
        return sum(len(group.occurrences) - 1 for group in self.groups)


def inspect_duplicate_keys(inputs: tuple[CanonicalParserInput, ...]) -> DuplicateReport:
    if type(inputs) is not tuple or not inputs or len(inputs) > MAX_CANONICAL_FILES:
        return DuplicateReport(complete=False, issue_codes=("unsupported_structure",))
    if any(
        type(source) is not CanonicalParserInput or type(source.content) is not bytes
        for source in inputs
    ):
        return DuplicateReport(complete=False, issue_codes=("malformed_file",))
    if sum(len(source.content) for source in inputs) > MAX_CANONICAL_AGGREGATE_BYTES:
        return DuplicateReport(complete=False, issue_codes=("unsupported_structure",))
    occurrences: dict[tuple[str, str, str, str, str], list[DuplicateOccurrence]] = defaultdict(list)
    issues: set[str] = set()
    count = 0
    size = 0
    seen_paths: set[tuple[str, str]] = set()
    for source in sorted(inputs, key=lambda item: (item.repository_side, item.path)):
        path_identity = (source.repository_side, source.path)
        if path_identity in seen_paths:
            issues.add("malformed_file")
            continue
        seen_paths.add(path_identity)
        try:
            validate_repository_relative_path(source.path)
            validate_repository_relative_path(source.layout_identity)
        except ValueError:
            issues.add("malformed_file")
            continue
        diagnostic_values, snapshot_issues = inspect_duplicate_snapshot(source)
        issues.update(issue.code for issue in snapshot_issues)
        for value in diagnostic_values:
            identity = (
                source.repository_side,
                source.layout_identity,
                "default"
                if source.base_language == "und"
                and moko_layout(source.path) == (source.layout_identity, "default")
                else value.language,
                value.logical_key,
                canonical_selector_digest(value.selector),
            )
            count += 1
            # Count full key/identity bytes before retaining them, including
            # nonduplicate entries needed to detect later cross-file repeats.
            size += len(
                json.dumps(
                    [identity, source.path, value.locator.position], ensure_ascii=True
                ).encode()
            )
            if count > MAX_CANONICAL_MAPPING_VALUES or size > MAX_DIAGNOSTIC_BYTES:
                return DuplicateReport(complete=False, issue_codes=("unsupported_structure",))
            occurrences[identity].append(DuplicateOccurrence(source.path, value.locator.position))
    groups = tuple(
        DuplicateGroup(
            id=hashlib.sha256(json.dumps(identity, ensure_ascii=True).encode()).hexdigest(),
            repository_side=identity[0],
            language=identity[2],
            key_preview=identity[3][:512],
            key_length=len(identity[3]),
            occurrences=tuple(members),
        )
        for identity, members in sorted(occurrences.items())
        if len(members) > 1
    )
    return DuplicateReport(groups=groups, complete=not issues, issue_codes=tuple(sorted(issues)))
