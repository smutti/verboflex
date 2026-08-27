"""Strict read-only iOS strings preview detection (TDD seam)."""

from __future__ import annotations

from collections.abc import Iterable

from verboflex.localization.preview.core import PreviewDetectionResult, RepositorySide
from verboflex.services.repository_discovery import RepositorySourceFile


def parse_ios_strings(content: bytes) -> object:
    """Parse one bounded strings document without providing serialization."""
    del content
    raise NotImplementedError


def detect_ios_strings_layouts(
    files: Iterable[RepositorySourceFile],
    *,
    repository_side: RepositorySide,
) -> PreviewDetectionResult:
    """Return separate exact iOS strings path-layout candidates."""
    del files, repository_side
    raise NotImplementedError
