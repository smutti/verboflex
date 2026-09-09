"""Exact read-only XLIFF layout discovery backed by the canonical parser."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from verboflex.localization.importing.core import CanonicalParserInput
from verboflex.localization.importing.registry import parse_canonical_snapshot
from verboflex.localization.importing.xliff import (
    XLIFF_12_NAMESPACE,
    XLIFF_20_NAMESPACE,
    xliff_layout_identity,
)
from verboflex.localization.preview.core import (
    PreviewDetectionResult,
    RepositorySide,
    build_layout_candidate,
)
from verboflex.services.repository_discovery import SOURCE_DISCOVERY_BUDGET, RepositorySourceFile


@dataclass(frozen=True, slots=True)
class _XliffFile:
    path: str
    layout_identity: str
    language: str
    values: dict[str, str]


def _language_hint(content: bytes) -> tuple[str, str] | None:
    """Read only bounded root attributes; canonical parsing remains authoritative."""
    text = content[:8192].decode("utf-8", errors="ignore")
    if XLIFF_12_NAMESPACE in text and 'version="1.2"' in text:
        attribute = "target-language"
    elif XLIFF_20_NAMESPACE in text and ('version="2.0"' in text or 'version="2.1"' in text):
        attribute = "trgLang"
    else:
        return None
    marker = f'{attribute}="'
    start = text.find(marker)
    if start < 0:
        marker = f"{attribute}='"
        start = text.find(marker)
    if start < 0:
        return None
    quote = marker[-1]
    value_start = start + len(marker)
    end = text.find(quote, value_start)
    if end < 0:
        return None
    return attribute, text[value_start:end]


def _parse_file(file: RepositorySourceFile, repository_side: RepositorySide) -> _XliffFile | None:
    hint = _language_hint(file.content)
    if hint is None:
        return None
    from verboflex.localization.preview.core import normalize_preview_locale

    language = normalize_preview_locale(hint[1])
    if language is None:
        return None
    identity = xliff_layout_identity(file.path, language=language)
    parsed = parse_canonical_snapshot(
        CanonicalParserInput(
            format="xliff",
            repository_side=repository_side,
            path=file.path,
            content=file.content,
            layout_identity=identity,
            layout_version=1,
            base_language="en",
        )
    )
    if parsed.issues:
        return None
    values: dict[str, str] = {}
    for value in parsed.values:
        values.setdefault(value.logical_key, value.display_text)
    return _XliffFile(file.path, identity, language, values)


def detect_xliff_layouts(
    files: Iterable[RepositorySourceFile], *, repository_side: RepositorySide
) -> PreviewDetectionResult:
    grouped: dict[str, list[_XliffFile]] = defaultdict(list)
    total_bytes = 0
    seen: set[str] = set()
    for file in sorted(files, key=lambda item: item.path):
        if not file.path.endswith((".xlf", ".xliff")):
            continue
        total_bytes += len(file.content)
        if (
            file.path in seen
            or len(file.content) > SOURCE_DISCOVERY_BUDGET.max_file_bytes
            or total_bytes > SOURCE_DISCOVERY_BUDGET.max_total_bytes
        ):
            continue
        seen.add(file.path)
        parsed = _parse_file(file, repository_side)
        if parsed is not None:
            grouped[parsed.layout_identity].append(parsed)
    candidates = []
    for identity in sorted(grouped):
        sources = grouped[identity]
        values: dict[str, dict[str, str]] = {}
        for source in sources:
            values.setdefault(source.language, {}).update(source.values)
        try:
            candidates.append(
                build_layout_candidate(
                    repository_side=repository_side,
                    format="xliff",
                    layout_identity=identity,
                    files=(source.path for source in sources),
                    values=values,
                )
            )
        except ValueError:
            continue
    return PreviewDetectionResult(candidates=tuple(candidates))
