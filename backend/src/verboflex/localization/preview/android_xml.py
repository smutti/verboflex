"""Strict, read-only Android XML localization preview detection."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from xml.etree.ElementTree import Element

from defusedxml import ElementTree  # type: ignore[import-untyped]
from defusedxml.common import DefusedXmlException  # type: ignore[import-untyped]

from verboflex.localization.importing.core import CanonicalParserInput
from verboflex.localization.importing.registry import parse_canonical_snapshot
from verboflex.localization.preview.core import (
    PreviewDetectionResult,
    PreviewLayoutCandidate,
    RepositorySide,
    build_layout_candidate,
)
from verboflex.services.repository_discovery import (
    SOURCE_DISCOVERY_BUDGET,
    RepositorySourceFile,
)

_UTF8_BOM = b"\xef\xbb\xbf"
_XML_DECLARATION = re.compile(
    r"\A<\?xml\s+version\s*=\s*(['\"])1\.0\1"
    r"(?:\s+encoding\s*=\s*(['\"])(?P<encoding>[^'\"]+)\2)?"
    r"(?:\s+standalone\s*=\s*(['\"])(?:yes|no)\3)?\s*\?>",
    re.IGNORECASE,
)
_ANDROID_PATH = re.compile(
    r"\A(?:(?P<prefix>.+)/)?res/values(?:-(?P<language>[A-Za-z]{2,3})"
    r"(?:-r(?P<region>[A-Za-z]{2}|[0-9]{3}))?)?/"
    r"(?P<filename>[^/]+\.xml)\Z"
)
_ANDROID_RESOURCE_XML_PATH = re.compile(r"\A(?:(?P<prefix>.+)/)?res/values[^/]*/[^/]+\.xml\Z")
_LOCALIZABLE_RESOURCE_TAGS = frozenset({"string", "plurals", "string-array"})


@dataclass(frozen=True, slots=True)
class _AndroidFile:
    path: str
    layout_identity: str
    language: str
    values: dict[str, str]


def _decode_xml(content: bytes) -> str:
    if content.startswith((b"\x00\x00\xfe\xff", b"\xff\xfe\x00\x00", b"\xff\xfe", b"\xfe\xff")):
        raise ValueError("unsupported Android XML encoding")
    raw = content[len(_UTF8_BOM) :] if content.startswith(_UTF8_BOM) else content
    if not raw or b"\x00" in raw:
        raise ValueError("unsupported Android XML encoding")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise ValueError("unsupported Android XML encoding") from error
    if text.startswith("<?xml"):
        declaration = _XML_DECLARATION.match(text)
        if declaration is None:
            raise ValueError("unsupported Android XML declaration")
        encoding = declaration.group("encoding")
        if encoding is not None and encoding.casefold() != "utf-8":
            raise ValueError("unsupported Android XML declaration")
    return text


def _plain_strings(content: bytes) -> dict[str, str]:
    text = _decode_xml(content)
    try:
        root = ElementTree.fromstring(
            text,
            forbid_dtd=True,
            forbid_entities=True,
            forbid_external=True,
        )
    except (DefusedXmlException, ElementTree.ParseError) as error:
        raise ValueError("unsupported Android XML") from error
    if root.tag != "resources" or root.attrib or (root.text or "").strip():
        raise ValueError("unsupported Android XML")
    values: dict[str, str] = {}
    for child in root:
        key, translation = _plain_string(child)
        if key in values:
            raise ValueError("unsupported Android XML")
        values[key] = translation
    if not values:
        raise ValueError("unsupported Android XML")
    return values


def _plain_string(child: Element) -> tuple[str, str]:
    if (
        child.tag != "string"
        or set(child.attrib) != {"name"}
        or len(child) != 0
        or (child.tail or "").strip()
    ):
        raise ValueError("unsupported Android XML")
    key = child.attrib["name"]
    translation = child.text or ""
    if not key or "\x00" in key or "\x00" in translation:
        raise ValueError("unsupported Android XML")
    return key, translation


def _classify(file: RepositorySourceFile) -> _AndroidFile | None:
    match = _ANDROID_PATH.fullmatch(file.path)
    if match is None:
        return None
    prefix = match.group("prefix")
    layout_identity = f"{prefix}/res" if prefix else "res"
    raw_language = match.group("language")
    region = match.group("region")
    language = (
        "default"
        if raw_language is None
        else f"{raw_language.lower()}-{region.upper()}"
        if region is not None
        else raw_language.lower()
    )
    try:
        values = _plain_strings(file.content)
    except ValueError:
        parsed = parse_canonical_snapshot(
            CanonicalParserInput(
                format="android_xml",
                repository_side="direct",
                path=file.path,
                content=file.content,
                layout_identity=layout_identity,
                layout_version=1,
                base_language=language if language != "default" else "en",
            )
        )
        if parsed.issues:
            raise ValueError("unsupported Android XML") from None
        values = {}
        for value in parsed.values:
            values.setdefault(value.logical_key, value.display_text)
    return _AndroidFile(
        path=file.path,
        layout_identity=layout_identity,
        language=language,
        values=values,
    )


def _layout_identity(path_match: re.Match[str]) -> str:
    prefix = path_match.group("prefix")
    return f"{prefix}/res" if prefix else "res"


def _classify_bounded_file(
    file: RepositorySourceFile,
    *,
    seen_paths: set[str],
) -> tuple[str, _AndroidFile | None, int, bool] | None:
    resource_match = _ANDROID_RESOURCE_XML_PATH.fullmatch(file.path)
    if resource_match is None:
        return None
    layout_identity = _layout_identity(resource_match)
    byte_count = len(file.content)
    if byte_count > SOURCE_DISCOVERY_BUDGET.max_file_bytes or file.path in seen_paths:
        return layout_identity, None, byte_count, False
    seen_paths.add(file.path)
    if _ANDROID_PATH.fullmatch(file.path) is None:
        return layout_identity, None, byte_count, False
    try:
        return layout_identity, _classify(file), byte_count, False
    except ValueError:
        return layout_identity, None, byte_count, _is_non_localization_resource(file.content)


def _is_non_localization_resource(content: bytes) -> bool:
    """Distinguish unrelated Android resources from malformed localization files."""
    try:
        root = ElementTree.fromstring(
            _decode_xml(content),
            forbid_dtd=True,
            forbid_entities=True,
            forbid_external=True,
        )
    except (DefusedXmlException, ElementTree.ParseError, ValueError):
        return False
    return (
        root.tag == "resources"
        and not any(
            isinstance(child.tag, str) and child.tag in _LOCALIZABLE_RESOURCE_TAGS
            for child in root
        )
    )


def _collect_android_files(
    files: Iterable[RepositorySourceFile],
) -> tuple[dict[str, list[_AndroidFile]], set[str]] | None:
    grouped: dict[str, list[_AndroidFile]] = defaultdict(list)
    invalid_layouts: set[str] = set()
    seen_paths: set[str] = set()
    total_bytes = 0
    for file in sorted(files, key=lambda item: item.path):
        classified = _classify_bounded_file(file, seen_paths=seen_paths)
        if classified is None:
            continue
        layout_identity, source, byte_count, ignored = classified
        total_bytes += byte_count
        if total_bytes > SOURCE_DISCOVERY_BUDGET.max_total_bytes:
            return None
        if source is None and not ignored:
            invalid_layouts.add(layout_identity)
        elif source is not None:
            grouped[layout_identity].append(source)
    return grouped, invalid_layouts


def _candidate_for_layout(
    *,
    layout_identity: str,
    sources: list[_AndroidFile],
    repository_side: RepositorySide,
) -> PreviewLayoutCandidate | None:
    language_values: dict[str, dict[str, str]] = {}
    for source in sources:
        values = language_values.setdefault(source.language, {})
        if set(values).intersection(source.values):
            return None
        values.update(source.values)
    try:
        return build_layout_candidate(
            repository_side=repository_side,
            format="android_xml",
            layout_identity=layout_identity,
            files=(source.path for source in sources),
            values=language_values,
        )
    except ValueError:
        return None


def detect_android_layouts(
    files: Iterable[RepositorySourceFile],
    *,
    repository_side: RepositorySide,
) -> PreviewDetectionResult:
    """Return separate exact Android resource-root candidates without guessing."""
    collected = _collect_android_files(files)
    if collected is None:
        return PreviewDetectionResult(candidates=())
    grouped, invalid_layouts = collected

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
