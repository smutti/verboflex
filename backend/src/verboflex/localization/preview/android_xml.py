"""Strict, read-only Android XML localization preview detection."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from defusedxml import ElementTree  # type: ignore[import-untyped]
from defusedxml.common import DefusedXmlException  # type: ignore[import-untyped]

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
    r"\A(?:(?P<prefix>.+)/)?res/values(?:-(?P<language>[A-Za-z]{2,3}))?/"
    r"(?P<filename>[^/]+\.xml)\Z"
)
_ANDROID_RESOURCE_XML_PATH = re.compile(
    r"\A(?:(?P<prefix>.+)/)?res/values[^/]*/[^/]+\.xml\Z"
)


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
        if (
            child.tag != "string"
            or set(child.attrib) != {"name"}
            or len(child) != 0
            or (child.tail or "").strip()
        ):
            raise ValueError("unsupported Android XML")
        key = child.attrib["name"]
        if not key or "\x00" in key or key in values:
            raise ValueError("unsupported Android XML")
        translation = child.text or ""
        if "\x00" in translation:
            raise ValueError("unsupported Android XML")
        values[key] = translation
    if not values:
        raise ValueError("unsupported Android XML")
    return values


def _classify(file: RepositorySourceFile) -> _AndroidFile | None:
    match = _ANDROID_PATH.fullmatch(file.path)
    if match is None:
        return None
    prefix = match.group("prefix")
    layout_identity = f"{prefix}/res" if prefix else "res"
    language = (match.group("language") or "default").lower()
    return _AndroidFile(
        path=file.path,
        layout_identity=layout_identity,
        language=language,
        values=_plain_strings(file.content),
    )


def _layout_identity(path_match: re.Match[str]) -> str:
    prefix = path_match.group("prefix")
    return f"{prefix}/res" if prefix else "res"


def detect_android_layouts(
    files: Iterable[RepositorySourceFile],
    *,
    repository_side: RepositorySide,
) -> PreviewDetectionResult:
    """Return separate exact Android resource-root candidates without guessing."""
    grouped: dict[str, list[_AndroidFile]] = defaultdict(list)
    invalid_layouts: set[str] = set()
    seen_paths: set[str] = set()
    total_bytes = 0
    for file in sorted(files, key=lambda item: item.path):
        resource_match = _ANDROID_RESOURCE_XML_PATH.fullmatch(file.path)
        if resource_match is None:
            continue
        layout_identity = _layout_identity(resource_match)
        total_bytes += len(file.content)
        if total_bytes > SOURCE_DISCOVERY_BUDGET.max_total_bytes:
            return PreviewDetectionResult(candidates=())
        if (
            len(file.content) > SOURCE_DISCOVERY_BUDGET.max_file_bytes
            or file.path in seen_paths
        ):
            invalid_layouts.add(layout_identity)
            continue
        seen_paths.add(file.path)

        path_match = _ANDROID_PATH.fullmatch(file.path)
        if path_match is None:
            invalid_layouts.add(layout_identity)
            continue
        try:
            classified = _classify(file)
        except ValueError:
            invalid_layouts.add(layout_identity)
            continue
        if classified is not None:
            grouped[layout_identity].append(classified)

    candidates: list[PreviewLayoutCandidate] = []
    for layout_identity in sorted(grouped):
        if layout_identity in invalid_layouts:
            continue
        language_values: dict[str, dict[str, str]] = {}
        valid = True
        for source in grouped[layout_identity]:
            values = language_values.setdefault(source.language, {})
            if set(values).intersection(source.values):
                valid = False
                break
            values.update(source.values)
        if not valid:
            continue
        try:
            candidate = build_layout_candidate(
                repository_side=repository_side,
                format="android_xml",
                layout_identity=layout_identity,
                files=(source.path for source in grouped[layout_identity]),
                values=language_values,
            )
        except ValueError:
            continue
        candidates.append(candidate)
    return PreviewDetectionResult(candidates=tuple(candidates))
