"""Strict, read-only Qt TS localization preview detection."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from xml.etree.ElementTree import Element

from defusedxml import ElementTree  # type: ignore[import-untyped]
from defusedxml.common import DefusedXmlException  # type: ignore[import-untyped]

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
_XML_DECLARATION = re.compile(
    r"\A<\?xml\s+version\s*=\s*(['\"])1\.0\1"
    r"(?:\s+encoding\s*=\s*(['\"])(?P<encoding>[^'\"]+)\2)?"
    r"(?:\s+standalone\s*=\s*(['\"])(?:yes|no)\3)?\s*\?>",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class _QtFile:
    path: str
    layout_identity: str
    language: str
    values: dict[str, str]


def _decode_xml(content: bytes) -> str:
    if content.startswith((b"\x00\x00\xfe\xff", b"\xff\xfe\x00\x00", b"\xff\xfe", b"\xfe\xff")):
        raise ValueError("unsupported Qt TS encoding")
    raw = content[len(_UTF8_BOM) :] if content.startswith(_UTF8_BOM) else content
    if not raw or b"\x00" in raw:
        raise ValueError("unsupported Qt TS encoding")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise ValueError("unsupported Qt TS encoding") from error
    if text.startswith("<?xml"):
        declaration = _XML_DECLARATION.match(text)
        if declaration is None:
            raise ValueError("unsupported Qt TS declaration")
        encoding = declaration.group("encoding")
        if encoding is not None and encoding.casefold() != "utf-8":
            raise ValueError("unsupported Qt TS declaration")
    return text


def _plain_text(element: Element) -> str:
    if element.attrib or len(element) != 0 or (element.tail or "").strip():
        raise ValueError("unsupported Qt TS")
    value = element.text or ""
    if not value or "\x00" in value:
        raise ValueError("unsupported Qt TS")
    return value


def _message_values(context: Element) -> dict[str, str]:
    if context.attrib or (context.text or "").strip() or not len(context):
        raise ValueError("unsupported Qt TS")
    children = list(context)
    if children[0].tag != "name":
        raise ValueError("unsupported Qt TS")
    _plain_text(children[0])
    if len(children) == 1:
        raise ValueError("unsupported Qt TS")

    values: dict[str, str] = {}
    for message in children[1:]:
        if (
            message.tag != "message"
            or message.attrib
            or (message.text or "").strip()
            or (message.tail or "").strip()
        ):
            raise ValueError("unsupported Qt TS")
        message_children = list(message)
        if [child.tag for child in message_children] != ["source", "translation"]:
            raise ValueError("unsupported Qt TS")
        source = _plain_text(message_children[0])
        translation = _plain_text(message_children[1])
        if source in values:
            raise ValueError("unsupported Qt TS")
        values[source] = translation
    return values


def _parse_qt_file(file: RepositorySourceFile) -> _QtFile:
    text = _decode_xml(file.content)
    try:
        root = ElementTree.fromstring(
            text,
            forbid_dtd=True,
            forbid_entities=True,
            forbid_external=True,
        )
    except (DefusedXmlException, ElementTree.ParseError) as error:
        raise ValueError("unsupported Qt TS") from error
    if (
        root.tag != "TS"
        or set(root.attrib) != {"version", "language"}
        or root.attrib["version"] != "2.1"
        or (root.text or "").strip()
        or not len(root)
    ):
        raise ValueError("unsupported Qt TS")
    language = normalize_preview_locale(root.attrib["language"])
    if language is None:
        raise ValueError("unsupported Qt TS locale")

    path_layout = extract_preview_locale_path(
        file.path,
        suffix=".ts",
        allow_prefixed_stem=True,
        expected_locale=language,
    )
    layout_identity = (
        f"qt-ts:{path_layout[1]}" if path_layout is not None else f"qt-ts:{file.path}"
    )

    values: dict[str, str] = {}
    for context in root:
        if context.tag != "context" or (context.tail or "").strip():
            raise ValueError("unsupported Qt TS")
        context_values = _message_values(context)
        if set(values).intersection(context_values):
            raise ValueError("unsupported Qt TS")
        values.update(context_values)
    if not values:
        raise ValueError("unsupported Qt TS")
    return _QtFile(
        path=file.path,
        layout_identity=layout_identity,
        language=language,
        values=values,
    )


def _candidate_for_layout(
    *,
    layout_identity: str,
    sources: list[_QtFile],
    repository_side: RepositorySide,
) -> PreviewLayoutCandidate | None:
    values: dict[str, dict[str, str]] = {}
    for source in sources:
        if source.language in values:
            return None
        values[source.language] = source.values
    try:
        return build_layout_candidate(
            repository_side=repository_side,
            format="qt_ts",
            layout_identity=layout_identity,
            files=(source.path for source in sources),
            values=values,
        )
    except ValueError:
        return None


def detect_qt_ts_layouts(
    files: Iterable[RepositorySourceFile],
    *,
    repository_side: RepositorySide,
) -> PreviewDetectionResult:
    """Return separate exact Qt TS path-convention candidates without guessing."""
    grouped: dict[str, list[_QtFile]] = defaultdict(list)
    invalid_layouts: set[str] = set()
    seen_paths: set[str] = set()
    total_bytes = 0
    for file in sorted(files, key=lambda item: item.path):
        if not file.path.endswith(".ts"):
            continue
        path_hint = extract_preview_locale_path(
            file.path,
            suffix=".ts",
            allow_prefixed_stem=True,
        )
        hinted_identity = f"qt-ts:{path_hint[1]}" if path_hint is not None else None
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
            source = _parse_qt_file(file)
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
