"""Strict, duplicate-aware JSON localization preview detection."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import cast

from verboflex.localization.preview.core import (
    PreviewDetectionResult,
    PreviewLayoutCandidate,
    RepositorySide,
    build_layout_candidate,
    extract_preview_locale_path,
    normalize_preview_locale,
)
from verboflex.services.repository_discovery import (
    SOURCE_DISCOVERY_BUDGET,
    RepositorySourceFile,
)

_UTF8_BOM = b"\xef\xbb\xbf"


@dataclass(frozen=True, slots=True)
class _JsonFile:
    path: str
    layout_identity: str
    values: dict[str, dict[str, str]]


def _decode_json(content: bytes) -> str:
    if content.startswith((b"\x00\x00\xfe\xff", b"\xff\xfe\x00\x00", b"\xff\xfe", b"\xfe\xff")):
        raise ValueError("unsupported JSON encoding")
    raw = content[len(_UTF8_BOM) :] if content.startswith(_UTF8_BOM) else content
    if not raw or b"\x00" in raw:
        raise ValueError("unsupported JSON encoding")
    try:
        return raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise ValueError("unsupported JSON encoding") from error


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON object name")
        value[key] = item
    return value


def _unsupported_constant(token: str) -> object:
    raise ValueError(f"unsupported JSON constant: {token}")


def _load_json(content: bytes) -> dict[str, object]:
    try:
        value = json.loads(
            _decode_json(content),
            object_pairs_hook=_unique_object,
            parse_constant=_unsupported_constant,
        )
    except (json.JSONDecodeError, ValueError) as error:
        raise ValueError("unsupported JSON") from error
    if not isinstance(value, dict) or not value:
        raise ValueError("unsupported JSON")
    return cast(dict[str, object], value)


def _nonempty_string_map(value: object) -> dict[str, str]:
    if not isinstance(value, dict) or not value:
        raise ValueError("unsupported JSON shape")
    result: dict[str, str] = {}
    for key, translation in value.items():
        if (
            not isinstance(key, str)
            or not key
            or "\x00" in key
            or not isinstance(translation, str)
            or "\x00" in translation
        ):
            raise ValueError("unsupported JSON shape")
        result[key] = translation
    return result


def _classify_json_file(file: RepositorySourceFile) -> _JsonFile:
    value = _load_json(file.content)
    if all(isinstance(item, str) for item in value.values()):
        path_layout = extract_preview_locale_path(file.path, suffix=".json")
        if path_layout is None:
            raise ValueError("ambiguous JSON path locale")
        translations = _nonempty_string_map(value)
        return _JsonFile(
            path=file.path,
            layout_identity=f"json:flat-per-locale:{path_layout[1]}",
            values={path_layout[0]: translations},
        )
    if not all(isinstance(item, dict) for item in value.values()):
        raise ValueError("unsupported JSON shape")

    locales: dict[str, dict[str, str]] = {}
    for raw_locale, translations in value.items():
        locale = normalize_preview_locale(raw_locale)
        if locale is None or locale in locales:
            raise ValueError("unsupported JSON locale")
        locales[locale] = _nonempty_string_map(translations)
    return _JsonFile(
        path=file.path,
        layout_identity=f"json:locale-rooted:{file.path}",
        values=locales,
    )


def _candidate_for_layout(
    *,
    layout_identity: str,
    sources: list[_JsonFile],
    repository_side: RepositorySide,
) -> PreviewLayoutCandidate | None:
    values: dict[str, dict[str, str]] = {}
    for source in sources:
        for language, translations in source.values.items():
            if language in values:
                return None
            values[language] = translations
    try:
        return build_layout_candidate(
            repository_side=repository_side,
            format="json",
            layout_identity=layout_identity,
            files=(source.path for source in sources),
            values=values,
        )
    except ValueError:
        return None


def detect_json_layouts(
    files: Iterable[RepositorySourceFile],
    *,
    repository_side: RepositorySide,
) -> PreviewDetectionResult:
    """Return independent exact flat-per-locale and locale-rooted candidates."""
    grouped: dict[str, list[_JsonFile]] = defaultdict(list)
    invalid_layouts: set[str] = set()
    seen_paths: set[str] = set()
    total_bytes = 0
    for file in sorted(files, key=lambda item: item.path):
        if not file.path.endswith(".json"):
            continue
        path_layout = extract_preview_locale_path(file.path, suffix=".json")
        hinted_identity = (
            f"json:flat-per-locale:{path_layout[1]}" if path_layout is not None else None
        )
        total_bytes += len(file.content)
        if (
            len(file.content) > SOURCE_DISCOVERY_BUDGET.max_file_bytes
            or total_bytes > SOURCE_DISCOVERY_BUDGET.max_total_bytes
            or file.path in seen_paths
        ):
            if hinted_identity is not None:
                invalid_layouts.add(hinted_identity)
            continue
        seen_paths.add(file.path)
        try:
            source = _classify_json_file(file)
        except ValueError:
            if hinted_identity is not None:
                invalid_layouts.add(hinted_identity)
            continue
        grouped[source.layout_identity].append(source)

    candidates: list[PreviewLayoutCandidate] = []
    for layout_identity in sorted(grouped):
        if layout_identity in invalid_layouts:
            continue
        candidate = _candidate_for_layout(
            layout_identity=layout_identity,
            sources=grouped[layout_identity],
            repository_side=repository_side,
        )
        if candidate is not None:
            candidates.append(candidate)
    return PreviewDetectionResult(candidates=tuple(candidates))
