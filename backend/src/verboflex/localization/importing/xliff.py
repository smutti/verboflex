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
_XML_NAMESPACE = "http://www.w3.org/XML/1998/namespace"
_XSI_NAMESPACE = "http://www.w3.org/2001/XMLSchema-instance"
_XML_LANG = f"{{{_XML_NAMESPACE}}}lang"
_XML_SPACE = f"{{{_XML_NAMESPACE}}}space"
_XSI_SCHEMA_LOCATION = f"{{{_XSI_NAMESPACE}}}schemaLocation"

_XML_DECLARATION = re.compile(
    r"\A<\?xml\s+version\s*=\s*(['\"])1\.0\1"
    r"(?:\s+encoding\s*=\s*(['\"])(?P<encoding>[^'\"]+)\2)?"
    r"(?:\s+standalone\s*=\s*(['\"])(?:yes|no)\3)?\s*\?>",
    re.IGNORECASE,
)
_INLINE_12 = {"g", "x", "ph", "bx", "ex", "bpt", "ept", "it", "mrk"}
_INLINE_2X = {"cp", "ph", "pc", "sc", "ec", "mrk", "sm", "em"}
_CODE_BASE_2X = {"ph", "pc", "sc", "ec"}
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


@dataclass(frozen=True, slots=True)
class _InlineRecord:
    element: Element
    local: str
    identifier: str | None
    parent_identifier: str | None
    position: int


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
    _require_attrs_unqualified(root, allow_xsi_schema_location=True)
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
    _require_attrs_unqualified(root, allow_xsi_schema_location=True)
    source_language = normalize_preview_locale(root.attrib.get("srcLang", ""))
    target_language = normalize_preview_locale(root.attrib.get("trgLang", ""))
    if source_language is None or target_language is None:
        raise _AmbiguousXliff
    _require_layout(parser_input, target_language)
    root_xml_space = _effective_xml_space(root, "default")
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
        file_xml_space = _effective_xml_space(file_node, root_xml_space)
        children = list(file_node)
        skeletons = [child for child in children if _local(child, namespace) == "skeleton"]
        if (
            len(skeletons) > 1
            or (skeletons and children[0] is not skeletons[0])
            or any(
                _local(child, namespace) not in {"skeleton", "group", "unit"} for child in children
            )
        ):
            raise _UnsupportedXliff
        for skeleton in skeletons:
            _validate_skeleton(skeleton)
        prefix = (
            _node("xliff:document", root, extra=(("dialect", dialect), ("namespace", namespace))),
            _node("xliff:file", file_node, extra=(("file_index", file_index),)),
        ) + tuple(_metadata_tree(skeleton, namespace) for skeleton in skeletons)
        output.extend(
            _walk_2x(
                file_node,
                parser_input,
                namespace,
                dialect,
                file_identity,
                source_language,
                target_language,
                file_xml_space,
                prefix,
                state,
                ("xliff", file_index),
                allow_skeleton=True,
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
    source_language: str,
    target_language: str,
    inherited_xml_space: str,
    prefix: tuple[CanonicalStructureNode, ...],
    state: _State,
    address: tuple[str | int, ...],
    *,
    allow_skeleton: bool = False,
) -> tuple[CanonicalValue, ...]:
    values = CanonicalValueBuffer(source_bytes=len(parser_input.content))
    for index, child in enumerate(parent):
        local = _local(child, namespace)
        if local == "group":
            _require_attrs_unqualified(child)
            group_xml_space = _effective_xml_space(child, inherited_xml_space)
            values.extend(
                _walk_2x(
                    child,
                    parser_input,
                    namespace,
                    dialect,
                    file_identity,
                    source_language,
                    target_language,
                    group_xml_space,
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
                    source_language,
                    target_language,
                    inherited_xml_space,
                    prefix,
                    state,
                    address + ("unit", index),
                )
            )
        elif local == "skeleton" and allow_skeleton:
            continue
        else:
            raise _UnsupportedXliff
    return tuple(values)


def _unit_2x(
    unit: Element,
    parser_input: CanonicalParserInput,
    namespace: str,
    dialect: str,
    file_identity: str,
    source_language: str,
    target_language: str,
    inherited_xml_space: str,
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
    unit_xml_space = _effective_xml_space(unit, inherited_xml_space)
    _validate_2x_unit_semantics(
        segments,
        namespace,
        source_language=source_language,
        target_language=target_language,
        inherited_xml_space=unit_xml_space,
    )
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
                language=target_language,
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
    _require_attrs_unqualified(element, allow_xml_lang=True)
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


def _validate_2x_unit_semantics(
    segments: list[Element],
    namespace: str,
    *,
    source_language: str,
    target_language: str,
    inherited_xml_space: str,
) -> None:
    """Validate core relationships that XML well-formedness cannot express."""
    orders: set[int] = set()
    sources: list[Element] = []
    targets: list[Element] = []
    resource_count = len(segments)
    for resource_index, segment in enumerate(segments, start=1):
        _require_attrs_unqualified(segment)
        segment_xml_space = _effective_xml_space(segment, inherited_xml_space)
        segment_children = list(segment)
        segment_sources = [
            child for child in segment_children if _local(child, namespace) == "source"
        ]
        segment_targets = [
            child for child in segment_children if _local(child, namespace) == "target"
        ]
        if len(segment_sources) != 1 or len(segment_targets) != 1:
            raise _AmbiguousXliff
        source = segment_sources[0]
        target = segment_targets[0]
        _require_attrs_unqualified(source, allow_xml_lang=True)
        _require_attrs_unqualified(target, allow_xml_lang=True)
        source_override = source.attrib.get(_XML_LANG)
        target_override = target.attrib.get(_XML_LANG)
        if (
            source_override is not None
            and normalize_preview_locale(source_override) != source_language
        ) or (
            target_override is not None
            and normalize_preview_locale(target_override) != target_language
        ):
            raise _UnsupportedXliff
        if _effective_xml_space(source, segment_xml_space) != _effective_xml_space(
            target, segment_xml_space
        ):
            raise _UnsupportedXliff
        raw_order = target.attrib.get("order")
        if raw_order is None:
            order = resource_index
        else:
            if not raw_order.isascii() or not raw_order.isdigit():
                raise _UnsupportedXliff
            order = int(raw_order)
            if order < 1 or order > resource_count:
                raise _UnsupportedXliff
        if order in orders:
            raise _UnsupportedXliff
        orders.add(order)
        sources.extend(segment_sources)
        targets.extend(segment_targets)

    source_records = _inline_records(sources, namespace)
    target_records = _inline_records(targets, namespace)
    source_identifiers = {
        record.identifier for record in source_records if record.identifier is not None
    }
    target_identifiers = {
        record.identifier for record in target_records if record.identifier is not None
    }
    _validate_spanning_codes(source_records, reference_identifiers=source_identifiers)
    _validate_spanning_codes(
        target_records,
        reference_identifiers=source_identifiers | target_identifiers,
    )
    if _editing_sequences(source_records) != _editing_sequences(target_records):
        raise _UnsupportedXliff


def _validate_skeleton(element: Element) -> None:
    _require_attrs_unqualified(element)
    if list(element):
        raise _UnsupportedXliff
    href = element.attrib.get("href")
    content = element.text or ""
    if href is None:
        if not content.strip():
            raise _UnsupportedXliff
    elif not href.strip() or content.strip():
        raise _UnsupportedXliff


def _effective_xml_space(element: Element, inherited: str) -> str:
    value = element.attrib.get(_XML_SPACE, inherited)
    if value not in {"default", "preserve"}:
        raise _UnsupportedXliff
    return value


def _inline_records(boundaries: list[Element], namespace: str) -> tuple[_InlineRecord, ...]:
    records: list[_InlineRecord] = []
    seen: set[str] = set()

    def visit(parent: Element, parent_identifier: str | None) -> None:
        for child in parent:
            local = _local(child, namespace)
            if local not in _INLINE_2X:
                raise _UnsupportedXliff
            _require_attrs_unqualified(child)
            identifier = child.attrib.get("id")
            if local in {"ph", "pc", "sc"} and not identifier:
                raise _UnsupportedXliff
            if identifier is not None:
                if not identifier or identifier in seen:
                    raise _UnsupportedXliff
                seen.add(identifier)
            records.append(
                _InlineRecord(
                    element=child,
                    local=local,
                    identifier=identifier,
                    parent_identifier=parent_identifier,
                    position=len(records),
                )
            )
            visit(
                child,
                identifier
                if local in _CODE_BASE_2X and identifier is not None
                else parent_identifier,
            )

    for boundary in boundaries:
        visit(boundary, None)
    return tuple(records)


def _code_reorder(record: _InlineRecord) -> str:
    value = record.element.attrib.get("canReorder", "yes")
    if value not in {"yes", "no", "firstNo"}:
        raise _UnsupportedXliff
    if record.local == "ec" and value == "firstNo":
        raise _UnsupportedXliff
    for name in ("canCopy", "canDelete"):
        flag = record.element.attrib.get(name, "yes")
        if flag not in {"yes", "no"}:
            raise _UnsupportedXliff
        if value != "yes" and flag != "no":
            raise _UnsupportedXliff
    return value


def _validate_spanning_codes(
    records: tuple[_InlineRecord, ...], *, reference_identifiers: set[str]
) -> None:
    starts: dict[str, _InlineRecord] = {}
    referenced: set[str] = set()
    for record in records:
        if record.local in _CODE_BASE_2X:
            _code_reorder(record)
        copy_of = record.element.attrib.get("copyOf")
        if copy_of is not None and (not copy_of or copy_of not in reference_identifiers):
            raise _UnsupportedXliff
        if record.local == "sc":
            assert record.identifier is not None
            starts[record.identifier] = record
        elif record.local == "ec":
            start_ref = record.element.attrib.get("startRef")
            isolated = record.element.attrib.get("isolated", "no")
            if isolated not in {"yes", "no"}:
                raise _UnsupportedXliff
            if start_ref is None:
                if isolated != "yes" or not record.identifier:
                    raise _UnsupportedXliff
                continue
            if isolated == "yes" or start_ref in referenced:
                raise _UnsupportedXliff
            start = starts.get(start_ref)
            if start is None or start.position >= record.position:
                raise _UnsupportedXliff
            if start.element.attrib.get("isolated", "no") != "no":
                raise _UnsupportedXliff
            if start.element.attrib.get("copyOf") != record.element.attrib.get("copyOf"):
                raise _UnsupportedXliff
            for name in ("canCopy", "canDelete"):
                if start.element.attrib.get(name, "yes") != record.element.attrib.get(name, "yes"):
                    raise _UnsupportedXliff
            start_reorder = _code_reorder(start)
            end_reorder = _code_reorder(record)
            expected_end_reorder = "yes" if start_reorder == "yes" else "no"
            if end_reorder != expected_end_reorder:
                raise _UnsupportedXliff
            referenced.add(start_ref)
    if any(
        identifier not in referenced and start.element.attrib.get("isolated", "no") != "yes"
        for identifier, start in starts.items()
    ):
        raise _UnsupportedXliff


def _editing_sequences(
    records: tuple[_InlineRecord, ...],
) -> dict[str, tuple[tuple[str, str, str | None], ...]]:
    sequences: dict[str, tuple[tuple[str, str, str | None], ...]] = {}
    current: list[_InlineRecord] = []

    def finish() -> None:
        if len(current) < 2:
            return
        first = current[0].identifier
        if first is None or first in sequences:
            raise _UnsupportedXliff
        sequences[first] = tuple(
            (item.local, cast(str, item.identifier), item.parent_identifier) for item in current
        )

    for record in records:
        if record.local not in _CODE_BASE_2X:
            continue
        reorder = _code_reorder(record)
        if reorder == "firstNo":
            finish()
            current = [record]
        elif reorder == "no":
            if not current:
                raise _UnsupportedXliff
            current.append(record)
        else:
            finish()
            current = []
    finish()
    return sequences


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
    elif local == "skeleton" or local in _METADATA_12:
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


def _require_attrs_unqualified(
    element: Element,
    *,
    allow_xml_lang: bool = False,
    allow_xsi_schema_location: bool = False,
) -> None:
    if len(element.attrib) > 128 or any(not name for name in element.attrib):
        raise _UnsupportedXliff
    for name, value in element.attrib.items():
        if "}" not in name:
            continue
        if name == _XML_SPACE and value in {"default", "preserve"}:
            continue
        if allow_xml_lang and name == _XML_LANG and normalize_preview_locale(value) is not None:
            continue
        if allow_xsi_schema_location and name == _XSI_SCHEMA_LOCATION and value.strip():
            continue
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
