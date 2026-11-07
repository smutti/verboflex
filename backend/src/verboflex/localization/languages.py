"""Initialize locale peers with bounded lexical edits, never tree serialization."""

import json
import re
from collections.abc import Iterator
from dataclasses import dataclass, replace
from pathlib import PurePosixPath

from verboflex.integrations.bitbucket.urls import validate_repository_relative_path
from verboflex.localization.html import html_path
from verboflex.localization.importing.core import MAX_CANONICAL_FILE_BYTES, CanonicalParserInput
from verboflex.localization.moko_layout import moko_layout
from verboflex.localization.plural_forms import plural_forms
from verboflex.localization.preview.core import normalize_preview_locale
from verboflex.localization.writing.core import ByteEdit, apply_byte_edits
from verboflex.localization.writing.parsing import inspect_writeback_snapshot
from verboflex.localization.writing.xml_spans import XmlElementSpan, index_xml


@dataclass(frozen=True)
class LanguageFile:
    path: str
    content: bytes
    new_file: bool = True


def destination(parser: CanonicalParserInput, language: str) -> str:
    if normalize_preview_locale(language) != language:
        raise ValueError("invalid_language")
    layout, path = parser.layout_identity, parser.path
    if parser.format == "html":
        identity = html_path(path)
        if identity is None:
            raise ValueError("unsupported_shape")
        result = identity[1] + identity[2] + language.upper() + PurePosixPath(path).suffix
        if html_path(result) is None:
            raise ValueError("unsupported_language")
    elif parser.format == "android_xml":
        if moko_layout(path):
            result = str(PurePosixPath(path).parent.parent / language / "strings.xml")
        else:
            qualifier = (
                language.replace("-", "-r")
                if re.fullmatch(r"[a-z]{2,3}(?:-[A-Z]{2})?", language)
                else "b+" + language.replace("-", "+")
            )
            result = f"{layout}/values-{qualifier}/{PurePosixPath(path).name}"
    elif parser.format == "json" and layout.startswith("json:locale-rooted:"):
        result = path
    else:
        prefix = {
            "json": "json:flat-per-locale:",
            "qt_ts": "qt-ts:",
            "ios_strings": "ios-strings:",
            "xliff": "xliff:",
        }[parser.format]
        template = layout.removeprefix(prefix)
        if "{locale}" not in template:
            raise ValueError("ambiguous_language_path")
        result = template.replace("{locale}", language)
    validate_repository_relative_path(result)
    if result == path and not layout.startswith("json:locale-rooted:"):
        raise ValueError("language_exists")
    return result


def _attribute(content: bytes, node: XmlElementSpan, name: str, value: str) -> ByteEdit:
    tag = content[node.start : node.start_tag_end]
    pattern = rb"(?<![\w:.-])" + re.escape(name.encode()) + rb"\s*=\s*(['\"])(.*?)\1"
    match = re.search(pattern, tag, re.S)
    if match:
        return ByteEdit(node.start + match.start(2), node.start + match.end(2), value.encode())
    offset = node.start_tag_end - (2 if node.self_closing else 1)
    return ByteEdit(offset, offset, b" " + name.encode() + b'="' + value.encode() + b'"')


def _inner(content: bytes, node: XmlElementSpan, value: bytes) -> ByteEdit:
    if node.self_closing:
        return ByteEdit(
            node.start_tag_end - 2, node.end, b">" + value + b"</" + node.name.encode() + b">"
        )
    return ByteEdit(node.start_tag_end, node.end_tag_start, value)


def _walk(node: XmlElementSpan) -> Iterator[XmlElementSpan]:
    yield node
    for child in node.children:
        yield from _walk(child)


def _qt(content: bytes, language: str) -> bytes:
    root = index_xml(content, allow_ts_doctype=True)
    edits = [_attribute(content, root, "language", language.replace("-", "_"))]
    for message in (node for node in _walk(root) if node.name == "message"):
        source = next(node for node in message.children if node.name == "source")
        target = next(node for node in message.children if node.name == "translation")
        if dict(target.attributes).get("type") in {"obsolete", "vanished"}:
            continue
        # Translation status is independent from copied source wording.
        if not target.self_closing:
            edits.append(_attribute(content, target, "type", "unfinished"))
        forms = [node for node in target.children if node.name == "numerusform"]
        if dict(message.attributes).get("numerus") == "yes":
            required = len(plural_forms("qt_ts", language))
            if not forms:
                raise ValueError("unsupported_shape")
            for form in forms[required:]:
                edits.append(ByteEdit(form.start, form.end, b""))
            if len(forms) < required:
                sample = content[forms[-1].start : forms[-1].end]
                edits.append(
                    ByteEdit(
                        target.end_tag_start, target.end_tag_start, sample * (required - len(forms))
                    )
                )
        elif not content[target.start_tag_end : target.end_tag_start].strip():
            edits.append(
                _inner(content, target, content[source.start_tag_end : source.end_tag_start])
            )
    return apply_byte_edits(content, tuple(edits))


def _android(content: bytes, language: str) -> bytes:
    root = index_xml(content)
    edits = []
    for node in root.children:
        if node.name != "plurals":
            continue
        items = {dict(child.attributes).get("quantity"): child for child in node.children}
        sample = items.get("other")
        if sample is None:
            raise ValueError("unsupported_shape")
        extra = []
        for quantity, _ in plural_forms("android_xml", language):
            if quantity not in items:
                raw = content[sample.start : sample.end]
                local = index_xml(raw)
                extra.append(apply_byte_edits(raw, (_attribute(raw, local, "quantity", quantity),)))
        if extra:
            edits.append(ByteEdit(node.end_tag_start, node.end_tag_start, b"".join(extra)))
    return apply_byte_edits(content, tuple(edits))


def _xliff(content: bytes, language: str) -> bytes:
    root = index_xml(content)
    edits = []

    def local(node: XmlElementSpan) -> str:
        return node.name.split(":")[-1]

    dialect = dict(root.attributes)["version"]
    if dialect != "1.2":
        edits.append(_attribute(content, root, "trgLang", language))
    for node in _walk(root):
        if dialect == "1.2" and local(node) == "file":
            edits.append(_attribute(content, node, "target-language", language))
        if local(node) not in {"trans-unit", "segment", "ignorable"}:
            continue
        source = next((child for child in node.children if local(child) == "source"), None)
        target = next((child for child in node.children if local(child) == "target"), None)
        if source is None or target is None:
            raise ValueError("unsupported_shape")
        if "xml:lang" in dict(target.attributes):
            edits.append(_attribute(content, target, "xml:lang", language))
        if local(node) == "segment":
            edits.append(_attribute(content, node, "state", "initial"))
        elif dialect == "1.2" and not target.self_closing:
            edits.append(_attribute(content, target, "state", "needs-translation"))
        edits.append(_inner(content, target, content[source.start_tag_end : source.end_tag_start]))
    return apply_byte_edits(content, tuple(edits))


def _whitespace_end(text: str, position: int) -> int:
    match = re.compile(r"\s*").match(text, position)
    assert match is not None
    return match.end()


def _rooted_json(content: bytes, base: str, language: str) -> bytes:
    text = content.decode("utf-8")
    decoder = json.JSONDecoder()
    position = text.index("{") + 1
    source = None
    while True:
        position = _whitespace_end(text, position)
        if text[position] == "}":
            break
        key, position = decoder.raw_decode(text, position)
        position = text.index(":", position) + 1
        position = _whitespace_end(text, position)
        start = position
        _, position = decoder.raw_decode(text, position)
        if normalize_preview_locale(key) == language:
            raise ValueError("language_exists")
        if normalize_preview_locale(key) == base:
            source = text[start:position]
        position = _whitespace_end(text, position)
        if text[position] == ",":
            position += 1
    if source is None:
        raise ValueError("missing_source_language")
    addition = ",\n  " + json.dumps(language) + ": " + source + "\n"
    return (text[:position] + addition + text[position:]).encode("utf-8")


def initialize_language(parser: CanonicalParserInput, language: str) -> LanguageFile:
    """Copy one source catalog; reparse the complete result before returning bytes."""
    parsed = inspect_writeback_snapshot(parser)
    if parsed.issues or not parsed.values:
        raise ValueError("unsupported_shape")
    if any(value.language == language for value in parsed.values):
        raise ValueError("language_exists")
    target = destination(parser, language)
    rooted = parser.layout_identity.startswith("json:locale-rooted:")
    if (
        not rooted
        and parser.format != "xliff"
        and {v.language for v in parsed.values} != {parser.base_language}
    ):
        raise ValueError("missing_source_language")
    content = parser.content
    if rooted:
        content = _rooted_json(content, parser.base_language, language)
    elif parser.format == "qt_ts":
        content = _qt(content, language)
    elif parser.format == "android_xml":
        content = _android(content, language)
    elif parser.format == "xliff":
        content = _xliff(content, language)
    if len(content) > MAX_CANONICAL_FILE_BYTES:
        raise ValueError("limit_exceeded")
    result = inspect_writeback_snapshot(replace(parser, path=target, content=content))
    expected = {
        v.logical_key
        for v in parsed.values
        if v.language == parser.base_language or parser.format == "xliff"
    }
    if (
        result.issues
        or {v.logical_key for v in result.values if v.language == language} != expected
    ):
        raise ValueError("invalid_language_output")
    return LanguageFile(target, content, not rooted)
