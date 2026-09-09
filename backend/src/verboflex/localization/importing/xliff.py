"""Strict, bounded canonical parser for OASIS XLIFF 1.2 and 2.x."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import cast
from unicodedata import category
from xml.etree.ElementTree import Element

from defusedxml import ElementTree  # type: ignore[import-untyped]
from defusedxml.common import DefusedXmlException  # type: ignore[import-untyped]

from verboflex.localization.importing.core import (
    MAX_CANONICAL_DEPTH,
    MAX_CANONICAL_FILE_BYTES,
    MAX_CANONICAL_STRUCTURE_NODES,
    MAX_CANONICAL_VALUES,
    CanonicalDiagnosticResult,
    CanonicalIssue,
    CanonicalLocator,
    CanonicalOutputLimitExceeded,
    CanonicalParseResult,
    CanonicalParserInput,
    CanonicalSelector,
    CanonicalStructureNode,
    CanonicalValue,
    CanonicalValueBuffer,
    IssueCode,
    StructureKind,
    canonical_value_order,
)
from verboflex.localization.preview.core import (
    extract_preview_locale_path,
    normalize_preview_locale,
)

XLIFF_12_NAMESPACE = "urn:oasis:names:tc:xliff:document:1.2"
XLIFF_20_NAMESPACE = "urn:oasis:names:tc:xliff:document:2.0"

_XML_DECLARATION = re.compile(
    r"\A<\?xml\s+version\s*=\s*(['\"])1\.0\1"
    r"(?:\s+encoding\s*=\s*(['\"])(?P<encoding>[^'\"]+)\2)?"
    r"(?:\s+standalone\s*=\s*(['\"])(?:yes|no)\3)?\s*\?>",
    re.IGNORECASE,
)
_INLINE_12 = {"g", "x", "ph", "bx", "ex", "bpt", "ept", "it", "mrk"}
_INLINE_2X = {"cp", "ph", "pc", "sc", "ec", "mrk", "sm", "em"}
_METADATA_12 = {
    "header",
    "skl",
    "external-file",
    "internal-file",
    "glossary",
    "reference",
    "tool",
    "phase-group",
    "phase",
    "count-group",
    "count",
    "context-group",
    "context",
    "prop-group",
    "prop",
}


class _MalformedXliff(ValueError):
    pass


class _UnsupportedXliff(ValueError):
    pass


class _AmbiguousXliff(ValueError):
    pass


class _DuplicateXliff(ValueError):
    pass


@dataclass(slots=True)
class _State:
    allow_duplicates: bool
    position: int = 0
    seen: set[tuple[str, str, str]] = field(default_factory=set)


def parse_xliff(parser_input: CanonicalParserInput) -> CanonicalParseResult:
    result = _parse_xliff(parser_input, allow_duplicates=False)
    if type(result) is not CanonicalParseResult:
        raise AssertionError("canonical XLIFF parse returned diagnostic output")
    return result


def inspect_xliff(
    parser_input: CanonicalParserInput,
) -> CanonicalDiagnosticResult | CanonicalParseResult:
    """Retain duplicate occurrences only for the bounded diagnostic boundary."""
    return _parse_xliff(parser_input, allow_duplicates=True)


def _parse_xliff(
    parser_input: CanonicalParserInput, *, allow_duplicates: bool
) -> CanonicalDiagnosticResult | CanonicalParseResult:
    if type(parser_input) is not CanonicalParserInput:
        return _invalid_input_failure()
    try:
        _require_authority(parser_input)
        root = _parse_root(parser_input.content)
        namespace, dialect = _dialect(root)
        values = (
            _values_12(root, parser_input, namespace, dialect, allow_duplicates)
            if dialect == "1.2"
            else _values_2x(root, parser_input, namespace, dialect, allow_duplicates)
        )
        ordered = tuple(sorted(values, key=canonical_value_order))
        if allow_duplicates:
            return CanonicalDiagnosticResult(values=ordered)
        return CanonicalParseResult(values=ordered)
    except _MalformedXliff:
        return _failure(parser_input, "malformed_file")
    except _DuplicateXliff:
        return _failure(parser_input, "duplicate_key")
    except _AmbiguousXliff:
        return _failure(parser_input, "ambiguous_structure")
    except CanonicalOutputLimitExceeded, _UnsupportedXliff, ValueError:
        return _failure(parser_input, "unsupported_structure")


def _require_authority(parser_input: CanonicalParserInput) -> None:
    if (
        parser_input.format != "xliff"
        or parser_input.repository_side not in {"direct", "keys", "translations"}
        or not _safe_path(parser_input.path)
        or not isinstance(parser_input.content, bytes)
    ):
        raise _UnsupportedXliff
    if parser_input.layout_version != 1 or not _safe_path(
        parser_input.layout_identity.removeprefix("xliff:")
    ):
        raise _AmbiguousXliff
    if not parser_input.layout_identity.startswith("xliff:"):
        raise _AmbiguousXliff
    if normalize_preview_locale(parser_input.base_language) is None:
        raise _AmbiguousXliff


def _decode(content: bytes) -> str:
    if not content or len(content) > MAX_CANONICAL_FILE_BYTES:
        raise _MalformedXliff
    if content.startswith((b"\x00\x00\xfe\xff", b"\xff\xfe\x00\x00", b"\xff\xfe", b"\xfe\xff")):
        raise _MalformedXliff
    raw = content[3:] if content.startswith(b"\xef\xbb\xbf") else content
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise _MalformedXliff from error
    declaration = _XML_DECLARATION.match(text) if text.startswith("<?xml") else None
    if text.startswith("<?xml") and declaration is None:
        raise _MalformedXliff
    if declaration is not None:
        encoding = declaration.group("encoding")
        if encoding is not None and encoding.casefold() != "utf-8":
            raise _MalformedXliff
        remainder = text[declaration.end() :]
    else:
        remainder = text
    if "<?" in remainder or "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
        raise _MalformedXliff
    if "<!--" in text or _forbidden_control(text):
        raise _UnsupportedXliff
    return text


def _parse_root(content: bytes) -> Element:
    try:
        root = ElementTree.fromstring(
            _decode(content), forbid_dtd=True, forbid_entities=True, forbid_external=True
        )
    except (DefusedXmlException, ElementTree.ParseError) as error:
        raise _MalformedXliff from error
    _require_bounds(cast(Element, root))
    return cast(Element, root)


def _dialect(root: Element) -> tuple[str, str]:
    namespace, local = _split(root.tag)
    version = root.attrib.get("version")
    if local != "xliff":
        raise _UnsupportedXliff
    if namespace == XLIFF_12_NAMESPACE and version == "1.2":
        return namespace, version
    if namespace == XLIFF_20_NAMESPACE and version in {"2.0", "2.1"}:
        return namespace, version
    raise _UnsupportedXliff


def _values_12(
    root: Element,
    parser_input: CanonicalParserInput,
    namespace: str,
    dialect: str,
    allow_duplicates: bool,
) -> tuple[CanonicalValue, ...]:
    _require_attrs_unqualified(root)
    files = list(root)
    if not files or any(_local(child, namespace) != "file" for child in files):
        raise _UnsupportedXliff
    pair: tuple[str, str] | None = None
    output = CanonicalValueBuffer(source_bytes=len(parser_input.content))
    state = _State(allow_duplicates=allow_duplicates)
    for file_index, file_node in enumerate(files):
        _require_attrs_unqualified(file_node)
        source_language = normalize_preview_locale(file_node.attrib.get("source-language", ""))
        target_language = normalize_preview_locale(file_node.attrib.get("target-language", ""))
        file_identity = file_node.attrib.get("original")
        if source_language is None or target_language is None or not file_identity:
            raise _AmbiguousXliff
        current_pair = (source_language, target_language)
        if pair is not None and pair != current_pair:
            raise _AmbiguousXliff
        pair = current_pair
        _require_layout(parser_input, target_language)
        prefix = (
            _node("xliff:document", root, extra=(("dialect", dialect), ("namespace", namespace))),
            _node("xliff:file", file_node, extra=(("file_index", file_index),)),
        )
        bodies = [child for child in file_node if _local(child, namespace) == "body"]
        metadata = [child for child in file_node if _local(child, namespace) in _METADATA_12]
        if len(bodies) != 1 or len(bodies) + len(metadata) != len(file_node):
            raise _UnsupportedXliff
        metadata_nodes = tuple(_metadata_tree(child, namespace) for child in metadata)
        output.extend(
            _walk_12(
                bodies[0],
                parser_input,
                namespace,
                dialect,
                file_identity,
                target_language,
                prefix + metadata_nodes,
                state,
                ("xliff", file_index, "body"),
            )
        )
    if not len(output):
        raise _UnsupportedXliff
    return tuple(output)


def _walk_12(
    parent: Element,
    parser_input: CanonicalParserInput,
    namespace: str,
    dialect: str,
    file_identity: str,
    language: str,
    prefix: tuple[CanonicalStructureNode, ...],
    state: _State,
    address: tuple[str | int, ...],
) -> tuple[CanonicalValue, ...]:
    _require_attrs_unqualified(parent)
    values = CanonicalValueBuffer(source_bytes=len(parser_input.content))
    for index, child in enumerate(parent):
        local = _local(child, namespace)
        if local == "group":
            values.extend(
                _walk_12(
                    child,
                    parser_input,
                    namespace,
                    dialect,
                    file_identity,
                    language,
                    prefix + (_node("xliff:group", child),),
                    state,
                    address + ("group", index),
                )
            )
        elif local == "trans-unit":
            values.append(
                _unit_12(
                    child,
                    parser_input,
                    namespace,
                    dialect,
                    file_identity,
                    language,
                    prefix,
                    state,
                    address + ("trans-unit", index),
                )
            )
        else:
            raise _UnsupportedXliff
    return tuple(values)


def _unit_12(
    unit: Element,
    parser_input: CanonicalParserInput,
    namespace: str,
    dialect: str,
    file_identity: str,
    language: str,
    prefix: tuple[CanonicalStructureNode, ...],
    state: _State,
    address: tuple[str | int, ...],
) -> CanonicalValue:
    _require_attrs_unqualified(unit)
    unit_id = unit.attrib.get("id")
    if not unit_id:
        raise _AmbiguousXliff
    logical_key = unit.attrib.get("resname") or unit_id
    children = list(unit)
    sources = [child for child in children if _local(child, namespace) == "source"]
    targets = [child for child in children if _local(child, namespace) == "target"]
    notes = [child for child in children if _local(child, namespace) == "note"]
    allowed = {"source", "target", "note", "context-group", "prop-group"}
    if (
        len(sources) != 1
        or len(targets) != 1
        or any(_local(child, namespace) not in allowed for child in children)
    ):
        raise _AmbiguousXliff
    identity = (file_identity, unit_id, "")
    _claim(identity, state)
    selector = CanonicalSelector(
        kind="scalar",
        fields=(("dialect", dialect), ("file_identity", file_identity), ("unit_id", unit_id)),
    )
    source_nodes, source_text = _content_nodes(sources[0], namespace, _INLINE_12, "source")
    target_nodes, target_text = _content_nodes(targets[0], namespace, _INLINE_12, "target")
    metadata = tuple(
        _metadata_tree(child, namespace)
        for child in children
        if _local(child, namespace) in {"context-group", "prop-group"}
    )
    note_nodes = tuple(
        _node("xliff:note", note, extra=(("text", _visible(note)),)) for note in notes
    )
    value = CanonicalValue(
        logical_key=logical_key,
        language=language,
        selector=selector,
        source_text=source_text,
        translated_text=None if parser_input.repository_side == "keys" else target_text,
        display_text=source_text if parser_input.repository_side == "keys" else target_text,
        structure=prefix
        + (_node("xliff:unit", unit),)
        + source_nodes
        + target_nodes
        + metadata
        + note_nodes,
        locator=CanonicalLocator(
            format="xliff",
            repository_side=parser_input.repository_side,
            path=parser_input.path,
            position=state.position,
            structural_address=address,
        ),
    )
    state.position += 1
    return value


def _values_2x(
    root: Element,
    parser_input: CanonicalParserInput,
    namespace: str,
    dialect: str,
    allow_duplicates: bool,
) -> tuple[CanonicalValue, ...]:
    _require_attrs_unqualified(root)
    source_language = normalize_preview_locale(root.attrib.get("srcLang", ""))
    target_language = normalize_preview_locale(root.attrib.get("trgLang", ""))
    if source_language is None or target_language is None:
        raise _AmbiguousXliff
    _require_layout(parser_input, target_language)
    files = list(root)
    if not files or any(_local(child, namespace) != "file" for child in files):
        raise _UnsupportedXliff
    state = _State(allow_duplicates=allow_duplicates)
    output = CanonicalValueBuffer(source_bytes=len(parser_input.content))
    for file_index, file_node in enumerate(files):
        _require_attrs_unqualified(file_node)
        file_identity = file_node.attrib.get("id")
        if not file_identity:
            raise _AmbiguousXliff
        prefix = (
            _node("xliff:document", root, extra=(("dialect", dialect), ("namespace", namespace))),
            _node("xliff:file", file_node, extra=(("file_index", file_index),)),
        )
        output.extend(
            _walk_2x(
                file_node,
                parser_input,
                namespace,
                dialect,
                file_identity,
                target_language,
                prefix,
                state,
                ("xliff", file_index),
            )
        )
    if not len(output):
        raise _UnsupportedXliff
    return tuple(output)


def _walk_2x(
    parent: Element,
    parser_input: CanonicalParserInput,
    namespace: str,
    dialect: str,
    file_identity: str,
    language: str,
    prefix: tuple[CanonicalStructureNode, ...],
    state: _State,
    address: tuple[str | int, ...],
) -> tuple[CanonicalValue, ...]:
    values = CanonicalValueBuffer(source_bytes=len(parser_input.content))
    for index, child in enumerate(parent):
        local = _local(child, namespace)
        if local == "group":
            values.extend(
                _walk_2x(
                    child,
                    parser_input,
                    namespace,
                    dialect,
                    file_identity,
                    language,
                    prefix + (_node("xliff:group", child),),
                    state,
                    address + ("group", index),
                )
            )
        elif local == "unit":
            values.extend(
                _unit_2x(
                    child,
                    parser_input,
                    namespace,
                    dialect,
                    file_identity,
                    language,
                    prefix,
                    state,
                    address + ("unit", index),
                )
            )
        else:
            raise _UnsupportedXliff
    return tuple(values)


def _unit_2x(
    unit: Element,
    parser_input: CanonicalParserInput,
    namespace: str,
    dialect: str,
    file_identity: str,
    language: str,
    prefix: tuple[CanonicalStructureNode, ...],
    state: _State,
    address: tuple[str | int, ...],
) -> tuple[CanonicalValue, ...]:
    _require_attrs_unqualified(unit)
    unit_id = unit.attrib.get("id")
    if not unit_id:
        raise _AmbiguousXliff
    logical_key = unit.attrib.get("name") or unit_id
    children = list(unit)
    segments = [child for child in children if _local(child, namespace) == "segment"]
    allowed = {"segment", "notes", "originalData"}
    if not segments or any(_local(child, namespace) not in allowed for child in children):
        raise _UnsupportedXliff
    shared = (
        prefix
        + (_node("xliff:unit", unit),)
        + tuple(
            _metadata_tree(child, namespace)
            for child in children
            if _local(child, namespace) != "segment"
        )
    )
    values = CanonicalValueBuffer(source_bytes=len(parser_input.content))
    for segment_index, segment in enumerate(segments):
        _require_attrs_unqualified(segment)
        segment_id = segment.attrib.get("id") or str(segment_index)
        identity = (file_identity, unit_id, segment_id)
        _claim(identity, state)
        segment_children = list(segment)
        sources = [child for child in segment_children if _local(child, namespace) == "source"]
        targets = [child for child in segment_children if _local(child, namespace) == "target"]
        if len(sources) != 1 or len(targets) != 1 or len(segment_children) != 2:
            raise _AmbiguousXliff
        source_nodes, source_text = _content_nodes(sources[0], namespace, _INLINE_2X, "source")
        target_nodes, target_text = _content_nodes(targets[0], namespace, _INLINE_2X, "target")
        selector = CanonicalSelector(
            kind="scalar",
            fields=(
                ("dialect", dialect),
                ("file_identity", file_identity),
                ("unit_id", unit_id),
                ("segment_id", segment_id),
            ),
        )
        values.append(
            CanonicalValue(
                logical_key=logical_key,
                language=language,
                selector=selector,
                source_text=source_text,
                translated_text=None if parser_input.repository_side == "keys" else target_text,
                display_text=source_text if parser_input.repository_side == "keys" else target_text,
                structure=shared
                + (_node("xliff:segment", segment, extra=(("segment_index", segment_index),)),)
                + source_nodes
                + target_nodes,
                locator=CanonicalLocator(
                    format="xliff",
                    repository_side=parser_input.repository_side,
                    path=parser_input.path,
                    position=state.position,
                    structural_address=address + ("segment", segment_index),
                ),
            )
        )
        state.position += 1
    return tuple(values)


def _content_nodes(
    element: Element, namespace: str, inline_vocabulary: set[str], boundary: str
) -> tuple[tuple[CanonicalStructureNode, ...], str]:
    if _local(element, namespace) != boundary:
        raise _UnsupportedXliff
    _require_attrs_unqualified(element)
    nodes: list[CanonicalStructureNode] = [_node(cast(StructureKind, f"xliff:{boundary}"), element)]
    if element.text is not None:
        nodes.append(
            CanonicalStructureNode(
                kind="xliff:text", fields=(("context", boundary), ("value", element.text))
            )
        )
    stack = list(element)
    while stack:
        inline = stack.pop(0)
        local = _local(inline, namespace)
        if local not in inline_vocabulary:
            raise _UnsupportedXliff
        _require_attrs_unqualified(inline)
        nodes.append(_node("xliff:inline", inline, extra=(("name", local),)))
        if inline.text is not None:
            nodes.append(
                CanonicalStructureNode(
                    kind="xliff:text", fields=(("context", local), ("value", inline.text))
                )
            )
        stack[0:0] = list(inline)
        if inline.tail is not None:
            nodes.append(
                CanonicalStructureNode(
                    kind="xliff:tail", fields=(("context", local), ("value", inline.tail))
                )
            )
    return tuple(nodes), _visible(element)


def _metadata_tree(element: Element, namespace: str) -> CanonicalStructureNode:
    local = _local(element, namespace)
    _require_attrs_unqualified(element)
    if local == "notes":
        kind = "xliff:notes"
    elif local == "note":
        kind = "xliff:note"
    elif local == "originalData":
        kind = "xliff:original_data"
    elif local == "data":
        kind = "xliff:data"
    elif local in _METADATA_12:
        kind = "xliff:metadata"
    else:
        raise _UnsupportedXliff
    for child in element:
        _metadata_tree(child, namespace)
    return _node(
        cast(StructureKind, kind), element, extra=(("name", local), ("text", _visible(element)))
    )


def _node(
    kind: StructureKind, element: Element, *, extra: tuple[tuple[str, str | int], ...] = ()
) -> CanonicalStructureNode:
    names = tuple(element.attrib)
    values = tuple(element.attrib.values())
    return CanonicalStructureNode(
        kind=kind, fields=extra + (("attribute_names", names), ("attribute_values", values))
    )


def _claim(identity: tuple[str, str, str], state: _State) -> None:
    if identity in state.seen and not state.allow_duplicates:
        raise _DuplicateXliff
    state.seen.add(identity)


def _require_layout(parser_input: CanonicalParserInput, language: str) -> None:
    if parser_input.layout_identity != xliff_layout_identity(parser_input.path, language=language):
        raise _AmbiguousXliff


def xliff_layout_identity(path: str, *, language: str) -> str:
    suffix = ".xliff" if path.endswith(".xliff") else ".xlf"
    path_layout = extract_preview_locale_path(
        path, suffix=suffix, allow_prefixed_stem=True, expected_locale=language
    )
    return f"xliff:{path_layout[1] if path_layout is not None else path}"


def _local(element: Element, namespace: str) -> str:
    actual_namespace, local = _split(element.tag)
    if actual_namespace != namespace:
        raise _UnsupportedXliff
    return local


def _split(tag: object) -> tuple[str, str]:
    if not isinstance(tag, str) or not tag.startswith("{") or "}" not in tag:
        raise _UnsupportedXliff
    namespace, local = tag[1:].split("}", 1)
    if not namespace or not local:
        raise _UnsupportedXliff
    return namespace, local


def _visible(element: Element) -> str:
    value = "".join(element.itertext())
    if _forbidden_control(value):
        raise _UnsupportedXliff
    return value


def _require_attrs_unqualified(element: Element) -> None:
    if len(element.attrib) > 128 or any("}" in name or not name for name in element.attrib):
        raise _UnsupportedXliff
    if any(
        _forbidden_control(name) or _forbidden_control(value)
        for name, value in element.attrib.items()
    ):
        raise _UnsupportedXliff


def _require_bounds(root: Element) -> None:
    count = 0
    stack = [(root, 1)]
    while stack:
        element, depth = stack.pop()
        count += 1
        if (
            depth > MAX_CANONICAL_DEPTH
            or count > MAX_CANONICAL_STRUCTURE_NODES
            or count > MAX_CANONICAL_VALUES * 16
        ):
            raise _UnsupportedXliff
        stack.extend((child, depth + 1) for child in element)


def _forbidden_control(value: str) -> bool:
    return any(
        category(character) == "Cc" and character not in {"\t", "\n", "\r"} for character in value
    )


def _safe_path(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and len(value) <= 4096
        and not value.startswith("/")
        and "//" not in value
        and "\x00" not in value
        and all(part not in {"", ".", ".."} for part in value.split("/"))
    )


def _failure(parser_input: CanonicalParserInput, code: IssueCode) -> CanonicalParseResult:
    messages = {
        "malformed_file": "Malformed XLIFF file.",
        "ambiguous_structure": "Ambiguous XLIFF structure.",
        "unsupported_structure": "Unsupported XLIFF structure.",
        "duplicate_key": "Duplicate XLIFF unit identity.",
        "base_language_required": "Base language is required.",
    }
    side = (
        parser_input.repository_side
        if parser_input.repository_side in {"direct", "keys", "translations"}
        else "direct"
    )
    path = parser_input.path if _safe_path(parser_input.path) else "<input>"
    return CanonicalParseResult(
        issues=(CanonicalIssue(code=code, repository_side=side, path=path, message=messages[code]),)
    )


def _invalid_input_failure() -> CanonicalParseResult:
    return CanonicalParseResult(
        issues=(
            CanonicalIssue(
                code="malformed_file",
                repository_side="direct",
                path="<input>",
                message="Malformed XLIFF file.",
            ),
        )
    )
