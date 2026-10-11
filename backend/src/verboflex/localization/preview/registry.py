"""Fail-closed registry for separate exact preview layout candidates."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from verboflex.localization.preview.android_xml import detect_android_layouts
from verboflex.localization.preview.core import (
    PreviewDetectionResult,
    PreviewLayoutCandidate,
    RepositorySide,
)
from verboflex.localization.preview.ios_strings import detect_ios_strings_layouts
from verboflex.localization.preview.json import detect_json_layouts
from verboflex.localization.preview.moko_xml import detect_moko_layouts
from verboflex.localization.preview.qt_ts import detect_qt_ts_layouts
from verboflex.localization.preview.xliff import detect_xliff_layouts
from verboflex.services.repository_discovery import RepositorySourceFile


def detect_preview_layouts(
    files: Iterable[RepositorySourceFile],
    *,
    repository_side: RepositorySide,
) -> PreviewDetectionResult:
    """Run every detector and discard overlapping or duplicate interpretations."""
    bounded_files = tuple(files)
    detected = (
        *detect_android_layouts(bounded_files, repository_side=repository_side).candidates,
        *detect_moko_layouts(bounded_files, repository_side=repository_side).candidates,
        *detect_qt_ts_layouts(bounded_files, repository_side=repository_side).candidates,
        *detect_json_layouts(bounded_files, repository_side=repository_side).candidates,
        *detect_ios_strings_layouts(bounded_files, repository_side=repository_side).candidates,
        *detect_xliff_layouts(bounded_files, repository_side=repository_side).candidates,
    )
    file_claims = Counter(path for candidate in detected for path in candidate.files)
    candidate_ids = Counter(candidate.id for candidate in detected)
    candidates = tuple(
        sorted(
            (
                candidate
                for candidate in detected
                if candidate_ids[candidate.id] == 1
                and all(file_claims[path] == 1 for path in candidate.files)
            ),
            key=_candidate_order,
        )
    )
    return PreviewDetectionResult(candidates=candidates)


def _candidate_order(candidate: PreviewLayoutCandidate) -> tuple[str, str, str, str]:
    return (
        candidate.repository_side,
        candidate.format,
        candidate.layout_identity,
        str(candidate.id),
    )
