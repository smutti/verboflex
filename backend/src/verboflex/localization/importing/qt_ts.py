"""Complete, bounded Qt TS canonical parser adapter."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import cast
from unicodedata import category
from xml.etree import ElementTree as StandardElementTree
from xml.etree.ElementTree import Element

from defusedxml import ElementTree  # type: ignore[import-untyped]
from defusedxml.common import DefusedXmlException  # type: ignore[import-untyped]

from verboflex.localization.importing.core import (
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
    canonical_issue_order,
    canonical_selector_digest,
    canonical_value_order,
)
from verboflex.localization.preview.core import (
    extract_preview_locale_path,
    normalize_preview_locale,
)

MAX_CANONICAL_FILE_BYTES = 1_048_576
MAX_QT_AGGREGATE_BYTES = 20_971_520
MAX_QT_FILES = 500
MAX_QT_ISSUES = 5
MAX_QT_MESSAGES = 5_000
MAX_QT_VALUES = 5_000
MAX_QT_XML_DEPTH = 6
MAX_QT_LOCATIONS_PER_MESSAGE = 256
MAX_QT_VARIANTS_PER_MESSAGE = 256

_UTF8_BOM = b"\xef\xbb\xbf"
_XML_DECLARATION = re.compile(
    r"\A<\?xml\s+version\s*=\s*(['\"])1\.0\1"
    r"(?:\s+encoding\s*=\s*(['\"])(?P<encoding>[^'\"]+)\2)?"
    r"(?:\s+standalone\s*=\s*(['\"])(?:yes|no)\3)?\s*\?>",
    re.IGNORECASE,
)
_LOCATION_LINE = re.compile(r"(?:[1-9][0-9]*|[+-][1-9][0-9]*)\Z")
_POSITIVE_INTEGER = re.compile(r"[1-9][0-9]*\Z")
_ROOT_ATTRIBUTES = {"version", "language", "sourcelanguage"}
_MESSAGE_ATTRIBUTES = {"id", "numerus"}
_MESSAGE_METADATA = (
    "oldsource",
    "comment",
    "oldcomment",
    "extracomment",
    "translatorcomment",
    "userdata",
)
_TRANSLATION_STATUSES = {"unfinished", "obsolete", "vanished"}


class _MalformedQtTs(ValueError):
    def __init__(self, *, line: int | None = None, column: int | None = None) -> None:
        super().__init__("malformed Qt TS")
        self.line = line
        self.column = column


class _UnsupportedQtTs(ValueError):
    pass


class _AmbiguousQtTs(ValueError):
    pass


class _DuplicateQtIdentity(ValueError):
    pass


class _BaseLanguageRequired(ValueError):
    pass


class _QtTreeTarget:
    """ElementTree target that makes otherwise discarded node kinds observable."""

    def __init__(self) -> None:
        self._builder = StandardElementTree.TreeBuilder(insert_comments=True, insert_pis=True)
        self.namespace_uris: set[str] = set()
        self.saw_comment = False
        self.saw_processing_instruction = False

    def start(self, tag: str, attributes: dict[str, str]) -> Element:
        return self._builder.start(tag, attributes)

    def end(self, tag: str) -> Element:
        return self._builder.end(tag)

    def data(self, value: str) -> None:
        self._builder.data(value)

    def comment(self, value: str) -> Element:
        self.saw_comment = True
        return self._builder.comment(value)

    def pi(self, target: str, value: str | None) -> Element:
        self.saw_processing_instruction = True
        return self._builder.pi(target, value)

    def start_namespace(self, _prefix: str | None, uri: str) -> None:
        self.namespace_uris.add(uri)

    def close(self) -> Element:
        return self._builder.close()


@dataclass(slots=True)
class _ParseState:
    previous_filename: str | None = None
    message_count: int = 0
    value_count: int = 0
    seen_ids: set[str] = field(default_factory=set)
    allow_duplicates: bool = False


def parse_qt_ts(parser_input: CanonicalParserInput) -> CanonicalParseResult:
    """Parse one complete Qt TS document or return one closed failure."""
    result = _parse_qt_ts(parser_input, allow_duplicates=False)
    if type(result) is not CanonicalParseResult:
        raise AssertionError("canonical Qt TS parse returned diagnostic output")
    return result


def inspect_qt_ts(
    parser_input: CanonicalParserInput,
) -> CanonicalDiagnosticResult | CanonicalParseResult:
    """Parse valid Qt TS while retaining duplicate identities for diagnostics only."""
    return _parse_qt_ts(parser_input, allow_duplicates=True)


def _parse_qt_ts(
    parser_input: CanonicalParserInput, *, allow_duplicates: bool
) -> CanonicalDiagnosticResult | CanonicalParseResult:
    if type(parser_input) is not CanonicalParserInput:
        return _invalid_input_failure()
    try:
        _require_input_authority(parser_input)
        root = _parse_root(parser_input.content)
        language, source_language = _document_languages(root, parser_input)
        values = _document_values(
            root=root,
            parser_input=parser_input,
            language=language,
            source_language=source_language,
            allow_duplicates=allow_duplicates,
        )
        if not allow_duplicates:
            _require_unique_values(values)
        sorted_values = tuple(sorted(values, key=canonical_value_order))
        if allow_duplicates:
            return CanonicalDiagnosticResult(values=sorted_values)
        return CanonicalParseResult(values=sorted_values)
    except _MalformedQtTs as error:
        return _failure(
            parser_input,
            code="malformed_file",
            line=error.line,
            column=error.column,
        )
    except _DuplicateQtIdentity:
        return _failure(parser_input, code="duplicate_key")
    except _AmbiguousQtTs:
        return _failure(parser_input, code="ambiguous_structure")
    except _BaseLanguageRequired:
        return _failure(parser_input, code="base_language_required")
    except _UnsupportedQtTs, ValueError:
        return _failure(parser_input, code="unsupported_structure")


def parse_qt_ts_files(
    parser_inputs: tuple[CanonicalParserInput, ...],
) -> CanonicalParseResult:
    """Combine bounded Qt peer files atomically in deterministic order."""
    if type(parser_inputs) is not tuple or not parser_inputs:
        return _invalid_batch_failure()
    if any(type(item) is not CanonicalParserInput for item in parser_inputs):
        return _invalid_batch_failure()
    if any(not isinstance(item.content, bytes) for item in parser_inputs):
        return _invalid_batch_failure()
    if len(parser_inputs) > MAX_QT_FILES:
        return _failure(parser_inputs[0], code="unsupported_structure")
    if sum(len(item.content) for item in parser_inputs) > MAX_QT_AGGREGATE_BYTES:
        return _failure(parser_inputs[0], code="unsupported_structure")

    values = CanonicalValueBuffer(source_bytes=sum(len(item.content) for item in parser_inputs))
    issues: list[CanonicalIssue] = []
    ordered_inputs = sorted(
        parser_inputs,
        key=lambda item: (item.repository_side, item.path),
    )
    for parser_input in ordered_inputs:
        result = parse_qt_ts(parser_input)
        if result.issues:
            issues.extend(result.issues)
        else:
            try:
                values.extend(result.values)
            except CanonicalOutputLimitExceeded:
                return _failure(parser_input, code="unsupported_structure")
        if len(values) > MAX_QT_VALUES:
            return _failure(parser_input, code="unsupported_structure")
    if issues:
        return CanonicalParseResult(
            issues=tuple(sorted(set(issues), key=canonical_issue_order)[:MAX_QT_ISSUES])
        )
    try:
        _require_unique_values(tuple(values))
    except _DuplicateQtIdentity:
        return _failure(ordered_inputs[0], code="duplicate_key")
    return CanonicalParseResult(values=tuple(sorted(values, key=canonical_value_order)))


def _require_input_authority(parser_input: CanonicalParserInput) -> None:
    if (
        parser_input.format != "qt_ts"
        or parser_input.repository_side not in {"direct", "keys", "translations"}
        or not _is_safe_relative_path(parser_input.path)
        or not isinstance(parser_input.content, bytes)
    ):
        raise _UnsupportedQtTs
    if parser_input.layout_version != 1 or not _is_safe_layout_identity(
        parser_input.layout_identity
    ):
        raise _AmbiguousQtTs
    if normalize_preview_locale(parser_input.base_language) is None:
        raise _BaseLanguageRequired


def _decode_xml(content: bytes) -> str:
    if len(content) > MAX_CANONICAL_FILE_BYTES:
        raise _MalformedQtTs
    if content.startswith((b"\x00\x00\xfe\xff", b"\xff\xfe\x00\x00", b"\xff\xfe", b"\xfe\xff")):
        raise _MalformedQtTs
    raw = content[len(_UTF8_BOM) :] if content.startswith(_UTF8_BOM) else content
    if not raw or b"\x00" in raw:
        raise _MalformedQtTs
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise _MalformedQtTs from error
    if text.startswith("<?xml"):
        declaration = _XML_DECLARATION.match(text)
        if declaration is None:
            raise _MalformedQtTs
        encoding = declaration.group("encoding")
        if encoding is not None and encoding.casefold() != "utf-8":
            raise _MalformedQtTs
    if "\ufeff" in text or _contains_forbidden_control(text):
        raise _MalformedQtTs
    return text


def _parse_root(content: bytes) -> Element:
    target = _QtTreeTarget()
    parser = ElementTree.DefusedXMLParser(
        target=target,
        forbid_dtd=True,
        forbid_entities=True,
        forbid_external=True,
    )
    parser.parser.StartNamespaceDeclHandler = target.start_namespace
    try:
        root = StandardElementTree.fromstring(_decode_xml(content), parser=parser)
    except ElementTree.ParseError as error:
        line, zero_based_column = getattr(error, "position", (None, None))
        column = zero_based_column + 1 if isinstance(zero_based_column, int) else None
        raise _MalformedQtTs(line=line, column=column) from error
    except DefusedXmlException as error:
        raise _MalformedQtTs from error
    if target.namespace_uris or target.saw_comment or target.saw_processing_instruction:
        raise _UnsupportedQtTs
    _require_bounded_depth(root)
    return root


def _document_languages(
    root: Element,
    parser_input: CanonicalParserInput,
) -> tuple[str, str | None]:
    names = set(root.attrib)
    if (
        root.tag != "TS"
        or "version" not in names
        or not names.issubset(_ROOT_ATTRIBUTES)
        or root.attrib["version"] not in {"2.0", "2.1"}
        or (root.text or "").strip()
        or (root.tail or "").strip()
    ):
        raise _UnsupportedQtTs
    if "language" not in names:
        raise _AmbiguousQtTs
    language = normalize_preview_locale(root.attrib["language"])
    if language is None:
        raise _AmbiguousQtTs
    source_language_raw = root.attrib.get("sourcelanguage")
    source_language = (
        normalize_preview_locale(source_language_raw) if source_language_raw is not None else None
    )
    if source_language_raw is not None and source_language is None:
        raise _AmbiguousQtTs
    if parser_input.layout_identity != _qt_layout_identity(parser_input.path, language=language):
        raise _AmbiguousQtTs
    return language, source_language


def _qt_layout_identity(path: str, *, language: str) -> str:
    path_layout = extract_preview_locale_path(
        path,
        suffix=".ts",
        allow_prefixed_stem=True,
        expected_locale=language,
    )
    return f"qt-ts:{path_layout[1]}" if path_layout is not None else f"qt-ts:{path}"


def _document_values(
    *,
    root: Element,
    parser_input: CanonicalParserInput,
    language: str,
    source_language: str | None,
    allow_duplicates: bool = False,
) -> tuple[CanonicalValue, ...]:
    document_fields: list[tuple[str, str]] = [
        ("version", root.attrib["version"]),
        ("language", language),
    ]
    if source_language is not None:
        document_fields.append(("source_language", source_language))
    prefix: list[CanonicalStructureNode] = [
        CanonicalStructureNode(kind="qt_ts:document", fields=tuple(document_fields))
    ]
    state = _ParseState(allow_duplicates=allow_duplicates)
    values = CanonicalValueBuffer(source_bytes=len(parser_input.content))
    saw_defaultcodec = False
    saw_dependencies = False
    saw_context = False
    context_index = 0
    for child in root:
        _require_whitespace_tail(child)
        if (
            child.tag == "defaultcodec"
            and not saw_defaultcodec
            and not saw_dependencies
            and not saw_context
        ):
            prefix.append(
                CanonicalStructureNode(
                    kind="qt_ts:defaultcodec",
                    fields=(("value", _text_only(child)),),
                )
            )
            saw_defaultcodec = True
            continue
        if child.tag == "dependencies" and not saw_dependencies and not saw_context:
            prefix.extend(_dependency_nodes(child))
            saw_dependencies = True
            continue
        if child.tag != "context":
            raise _UnsupportedQtTs
        saw_context = True
        context_values = _context_values(
            child=child,
            context_index=context_index,
            prefix=tuple(prefix),
            parser_input=parser_input,
            language=language,
            state=state,
        )
        values.extend(context_values)
        context_index += 1
    return tuple(values)


def _require_unique_values(values: tuple[CanonicalValue, ...]) -> None:
    identities: set[tuple[str, str, str, str]] = set()
    for value in values:
        identity = (
            value.locator.repository_side,
            value.language,
            value.logical_key,
            canonical_selector_digest(value.selector),
        )
        if identity in identities:
            raise _DuplicateQtIdentity
        identities.add(identity)


def _dependency_nodes(element: Element) -> tuple[CanonicalStructureNode, ...]:
    if element.attrib or (element.text or "").strip() or not len(element):
        raise _UnsupportedQtTs
    nodes: list[CanonicalStructureNode] = [
        CanonicalStructureNode(kind="qt_ts:dependencies", fields=())
    ]
    for dependency in element:
        if (
            dependency.tag != "dependency"
            or len(dependency)
            or (dependency.text or "").strip()
            or (dependency.tail or "").strip()
            or not set(dependency.attrib).issubset({"catalog"})
        ):
            raise _UnsupportedQtTs
        catalog = dependency.attrib.get("catalog")
        if catalog is not None:
            _require_nonempty_text(catalog)
        fields = (("catalog", catalog),) if catalog is not None else ()
        nodes.append(CanonicalStructureNode(kind="qt_ts:dependency", fields=fields))
    return tuple(nodes)


def _context_values(
    *,
    child: Element,
    context_index: int,
    prefix: tuple[CanonicalStructureNode, ...],
    parser_input: CanonicalParserInput,
    language: str,
    state: _ParseState,
) -> tuple[CanonicalValue, ...]:
    if child.attrib or (child.text or "").strip():
        raise _UnsupportedQtTs
    children = list(child)
    if not children or children[0].tag != "name":
        raise _UnsupportedQtTs
    context_name = _text_only(children[0])
    _require_nonempty_text(context_name)
    context_prefix = prefix + (
        CanonicalStructureNode(kind="qt_ts:context", fields=(("name", context_name),)),
    )
    index = 1
    comments: list[CanonicalStructureNode] = []
    while index < len(children) and children[index].tag == "comment":
        comments.append(
            CanonicalStructureNode(
                kind="qt_ts:comment",
                fields=(("scope", "context"), ("value", _text_only(children[index]))),
            )
        )
        index += 1
    values = CanonicalValueBuffer(source_bytes=len(parser_input.content))
    for message_index, message in enumerate(children[index:]):
        if message.tag != "message":
            raise _UnsupportedQtTs
        if state.message_count >= MAX_QT_MESSAGES:
            raise _UnsupportedQtTs
        message_values = _message_values(
            message=message,
            context_name=context_name,
            context_index=context_index,
            message_index=message_index,
            position=state.message_count,
            prefix=context_prefix + tuple(comments),
            parser_input=parser_input,
            language=language,
            state=state,
        )
        state.message_count += 1
        state.value_count += len(message_values)
        if state.value_count > MAX_QT_VALUES:
            raise _UnsupportedQtTs
        values.extend(message_values)
    return tuple(values)


def _message_values(
    *,
    message: Element,
    context_name: str,
    context_index: int,
    message_index: int,
    position: int,
    prefix: tuple[CanonicalStructureNode, ...],
    parser_input: CanonicalParserInput,
    language: str,
    state: _ParseState,
) -> tuple[CanonicalValue, ...]:
    if (
        not set(message.attrib).issubset(_MESSAGE_ATTRIBUTES)
        or (message.text or "").strip()
        or (message.tail or "").strip()
    ):
        raise _UnsupportedQtTs
    identifier = message.attrib.get("id")
    if identifier is not None:
        _require_nonempty_text(identifier)
        if identifier in state.seen_ids and not state.allow_duplicates:
            raise _DuplicateQtIdentity
        state.seen_ids.add(identifier)
    numerus_raw = message.attrib.get("numerus", "no")
    if numerus_raw not in {"yes", "no"}:
        raise _UnsupportedQtTs
    is_numerus = numerus_raw == "yes"

    children = list(message)
    index = 0
    locations: list[CanonicalStructureNode] = []
    while index < len(children) and children[index].tag == "location":
        if len(locations) >= MAX_QT_LOCATIONS_PER_MESSAGE:
            raise _UnsupportedQtTs
        locations.append(_location_node(children[index], state=state))
        index += 1
    if index >= len(children) or children[index].tag != "source":
        raise _UnsupportedQtTs
    source = _text_only(children[index])
    index += 1

    metadata: list[CanonicalStructureNode] = []
    disambiguation: str | None = None
    for tag in _MESSAGE_METADATA:
        if index >= len(children) or children[index].tag != tag:
            continue
        value = _text_only(children[index])
        fields: tuple[tuple[str, str], ...]
        if tag == "comment":
            disambiguation = value
            fields = (("scope", "message"), ("value", value))
        else:
            fields = (("value", value),)
        metadata.append(
            CanonicalStructureNode(kind=cast(StructureKind, f"qt_ts:{tag}"), fields=fields)
        )
        index += 1
    if index >= len(children) or children[index].tag != "translation" or index + 1 != len(children):
        raise _UnsupportedQtTs

    logical_key = identifier if identifier is not None else source
    _require_nonempty_text(logical_key)
    identity_fields: list[tuple[str, str]] = [
        ("identity_kind", "id" if identifier is not None else "source")
    ]
    if identifier is None:
        identity_fields.append(("context", context_name))
        if disambiguation is not None:
            identity_fields.append(("disambiguation", disambiguation))

    message_fields: list[tuple[str, str | bool]] = [
        ("identity_kind", "id" if identifier is not None else "source"),
        ("numerus", is_numerus),
    ]
    if identifier is not None:
        message_fields.insert(1, ("id", identifier))
    message_prefix = (
        prefix
        + (CanonicalStructureNode(kind="qt_ts:message", fields=tuple(message_fields)),)
        + tuple(locations)
        + (CanonicalStructureNode(kind="qt_ts:source", fields=(("value", source),)),)
        + tuple(metadata)
    )
    return _translation_values(
        translation=children[index],
        logical_key=logical_key,
        source=source,
        identity_fields=tuple(identity_fields),
        is_numerus=is_numerus,
        prefix=message_prefix,
        parser_input=parser_input,
        language=language,
        position=position,
        structural_address=("TS", "context", context_index, "message", message_index),
    )


def _location_node(element: Element, *, state: _ParseState) -> CanonicalStructureNode:
    if (
        len(element)
        or (element.text or "").strip()
        or (element.tail or "").strip()
        or not set(element.attrib).issubset({"filename", "line"})
    ):
        raise _UnsupportedQtTs
    explicit_filename = element.attrib.get("filename")
    if explicit_filename is not None:
        _require_nonempty_text(explicit_filename)
        state.previous_filename = explicit_filename
    if state.previous_filename is None:
        raise _AmbiguousQtTs
    line = element.attrib.get("line")
    if line is not None and (
        _LOCATION_LINE.fullmatch(line) is None or abs(int(line)) > 2_147_483_647
    ):
        raise _UnsupportedQtTs
    fields: list[tuple[str, str | bool]] = [
        ("filename", state.previous_filename),
        ("filename_explicit", explicit_filename is not None),
    ]
    if line is not None:
        fields.append(("line", line))
    return CanonicalStructureNode(kind="qt_ts:location", fields=tuple(fields))


def _translation_values(
    *,
    translation: Element,
    logical_key: str,
    source: str,
    identity_fields: tuple[tuple[str, str], ...],
    is_numerus: bool,
    prefix: tuple[CanonicalStructureNode, ...],
    parser_input: CanonicalParserInput,
    language: str,
    position: int,
    structural_address: tuple[str | int, ...],
) -> tuple[CanonicalValue, ...]:
    if (
        not set(translation.attrib).issubset({"type", "variants"})
        or (translation.tail or "").strip()
    ):
        raise _UnsupportedQtTs
    status = translation.attrib.get("type", "active")
    if status != "active" and status not in _TRANSLATION_STATUSES:
        raise _UnsupportedQtTs
    variants_raw = translation.attrib.get("variants")
    if variants_raw is not None and variants_raw != "yes":
        raise _UnsupportedQtTs
    has_variants = variants_raw == "yes"
    deleted = status in {"obsolete", "vanished"}
    translation_node = CanonicalStructureNode(
        kind="qt_ts:translation",
        fields=(
            ("status", status),
            ("review_state", "draft"),
            ("deleted", deleted),
            ("variants", has_variants),
        ),
    )
    children = list(translation)
    if not children:
        if is_numerus or has_variants:
            raise _UnsupportedQtTs
        text = _element_text(translation)
        return (
            _canonical_value(
                logical_key=logical_key,
                source=source,
                translated=text,
                selector=CanonicalSelector(kind="scalar", fields=identity_fields),
                structure=prefix + (translation_node, _text_node(text)),
                parser_input=parser_input,
                language=language,
                position=position,
                structural_address=structural_address,
            ),
        )
    if (translation.text or "").strip() or any((child.tail or "").strip() for child in children):
        raise _UnsupportedQtTs
    if len(children) > MAX_QT_VARIANTS_PER_MESSAGE:
        raise _UnsupportedQtTs
    if all(child.tag == "numerusform" for child in children):
        if not is_numerus or has_variants:
            raise _UnsupportedQtTs
        return _numerus_values(
            forms=children,
            logical_key=logical_key,
            source=source,
            identity_fields=identity_fields,
            prefix=prefix + (translation_node,),
            parser_input=parser_input,
            language=language,
            position=position,
            structural_address=structural_address,
        )
    if all(child.tag == "lengthvariant" for child in children):
        if is_numerus or not has_variants:
            raise _UnsupportedQtTs
        return _length_variant_values(
            variants=children,
            logical_key=logical_key,
            source=source,
            identity_fields=identity_fields,
            prefix=prefix + (translation_node,),
            parser_input=parser_input,
            language=language,
            position=position,
            structural_address=structural_address,
            form_index=None,
        )
    raise _UnsupportedQtTs


def _numerus_values(
    *,
    forms: list[Element],
    logical_key: str,
    source: str,
    identity_fields: tuple[tuple[str, str], ...],
    prefix: tuple[CanonicalStructureNode, ...],
    parser_input: CanonicalParserInput,
    language: str,
    position: int,
    structural_address: tuple[str | int, ...],
) -> tuple[CanonicalValue, ...]:
    nested_shapes = {bool(len(form)) for form in forms}
    if len(nested_shapes) != 1:
        raise _UnsupportedQtTs
    values = CanonicalValueBuffer(source_bytes=len(parser_input.content))
    for form_index, form in enumerate(forms):
        if not len(form):
            if form.attrib:
                raise _UnsupportedQtTs
            text = _element_text(form)
            values.append(
                _canonical_value(
                    logical_key=logical_key,
                    source=source,
                    translated=text,
                    selector=CanonicalSelector(
                        kind="qt_numerus",
                        fields=identity_fields + (("form_index", form_index),),
                    ),
                    structure=prefix
                    + (
                        CanonicalStructureNode(
                            kind="qt_ts:numerusform",
                            fields=(("form_index", form_index), ("variants", False)),
                        ),
                        _text_node(text),
                    ),
                    parser_input=parser_input,
                    language=language,
                    position=position,
                    structural_address=structural_address + ("numerusform", form_index),
                )
            )
            continue
        if set(form.attrib) != {"variants"} or form.attrib["variants"] != "yes":
            raise _UnsupportedQtTs
        if (form.text or "").strip() or any((child.tail or "").strip() for child in form):
            raise _UnsupportedQtTs
        children = list(form)
        if (
            not children
            or len(children) > MAX_QT_VARIANTS_PER_MESSAGE
            or any(child.tag != "lengthvariant" for child in children)
        ):
            raise _UnsupportedQtTs
        form_prefix = prefix + (
            CanonicalStructureNode(
                kind="qt_ts:numerusform",
                fields=(("form_index", form_index), ("variants", True)),
            ),
        )
        values.extend(
            _length_variant_values(
                variants=children,
                logical_key=logical_key,
                source=source,
                identity_fields=identity_fields,
                prefix=form_prefix,
                parser_input=parser_input,
                language=language,
                position=position,
                structural_address=structural_address + ("numerusform", form_index),
                form_index=form_index,
            )
        )
    return tuple(values)


def _length_variant_values(
    *,
    variants: list[Element],
    logical_key: str,
    source: str,
    identity_fields: tuple[tuple[str, str], ...],
    prefix: tuple[CanonicalStructureNode, ...],
    parser_input: CanonicalParserInput,
    language: str,
    position: int,
    structural_address: tuple[str | int, ...],
    form_index: int | None,
) -> tuple[CanonicalValue, ...]:
    priorities: set[int] = set()
    values = CanonicalValueBuffer(source_bytes=len(parser_input.content))
    for variant in variants:
        if set(variant.attrib) != {"priority"} or len(variant):
            raise _UnsupportedQtTs
        priority_token = variant.attrib["priority"]
        if _POSITIVE_INTEGER.fullmatch(priority_token) is None:
            raise _UnsupportedQtTs
        priority = int(priority_token)
        if priority > 2_147_483_647:
            raise _UnsupportedQtTs
        if priority in priorities:
            raise _DuplicateQtIdentity
        priorities.add(priority)
        text = _element_text(variant)
        selector_fields: tuple[tuple[str, str | int], ...] = identity_fields
        address = structural_address
        variant_fields: list[tuple[str, int]] = []
        if form_index is not None:
            selector_fields += (("form_index", form_index),)
            address += ("lengthvariant", priority)
            variant_fields.append(("form_index", form_index))
        else:
            address += ("lengthvariant", priority)
        selector_fields += (("priority", priority),)
        variant_fields.append(("priority", priority))
        values.append(
            _canonical_value(
                logical_key=logical_key,
                source=source,
                translated=text,
                selector=CanonicalSelector(kind="qt_length_variant", fields=selector_fields),
                structure=prefix
                + (
                    CanonicalStructureNode(
                        kind="qt_ts:lengthvariant",
                        fields=tuple(variant_fields),
                    ),
                    _text_node(text),
                ),
                parser_input=parser_input,
                language=language,
                position=position,
                structural_address=address,
            )
        )
    return tuple(values)


def _canonical_value(
    *,
    logical_key: str,
    source: str,
    translated: str,
    selector: CanonicalSelector,
    structure: tuple[CanonicalStructureNode, ...],
    parser_input: CanonicalParserInput,
    language: str,
    position: int,
    structural_address: tuple[str | int, ...],
) -> CanonicalValue:
    is_keys_side = parser_input.repository_side == "keys"
    return CanonicalValue(
        logical_key=logical_key,
        language=language,
        selector=selector,
        source_text=source,
        translated_text=None if is_keys_side else translated,
        display_text=source if is_keys_side else translated,
        structure=structure,
        locator=CanonicalLocator(
            format="qt_ts",
            repository_side=parser_input.repository_side,
            path=parser_input.path,
            position=position,
            structural_address=structural_address,
        ),
    )


def _text_node(value: str) -> CanonicalStructureNode:
    return CanonicalStructureNode(kind="qt_ts:text", fields=(("value", value),))


def _text_only(element: Element) -> str:
    if element.attrib or len(element) or (element.tail or "").strip():
        raise _UnsupportedQtTs
    return _validated_text(element.text or "")


def _element_text(element: Element) -> str:
    if len(element) or (element.tail or "").strip():
        raise _UnsupportedQtTs
    return _validated_text(element.text or "")


def _validated_text(value: str) -> str:
    if _contains_forbidden_control(value):
        raise _UnsupportedQtTs
    return value


def _require_nonempty_text(value: str) -> None:
    if not value or _contains_forbidden_control(value):
        raise _UnsupportedQtTs


def _require_whitespace_tail(element: Element) -> None:
    if (element.tail or "").strip():
        raise _UnsupportedQtTs


def _contains_forbidden_control(value: str) -> bool:
    return any(
        category(character) == "Cc" and character not in {"\t", "\n", "\r"} for character in value
    )


def _require_bounded_depth(root: Element) -> None:
    stack: list[tuple[Element, int]] = [(root, 1)]
    while stack:
        element, depth = stack.pop()
        if depth > MAX_QT_XML_DEPTH:
            raise _UnsupportedQtTs
        stack.extend((child, depth + 1) for child in element)


def _is_safe_relative_path(value: object) -> bool:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 4_096
        or value.startswith("/")
        or "//" in value
        or "\x00" in value
        or _contains_forbidden_control(value)
    ):
        return False
    return all(component not in {"", ".", ".."} for component in value.split("/"))


def _is_safe_layout_identity(value: object) -> bool:
    return isinstance(value, str) and bool(value) and len(value) <= 4_096 and "\x00" not in value


def _failure(
    parser_input: CanonicalParserInput,
    *,
    code: IssueCode,
    line: int | None = None,
    column: int | None = None,
) -> CanonicalParseResult:
    messages = {
        "malformed_file": "Malformed Qt TS file.",
        "ambiguous_structure": "Ambiguous Qt TS structure.",
        "unsupported_structure": "Unsupported Qt TS structure.",
        "duplicate_key": "Duplicate Qt message identity.",
        "base_language_required": "Base language is required.",
    }
    side = (
        parser_input.repository_side
        if parser_input.repository_side in {"direct", "keys", "translations"}
        else "direct"
    )
    path = parser_input.path if _is_safe_relative_path(parser_input.path) else "<input>"
    return CanonicalParseResult(
        issues=(
            CanonicalIssue(
                code=code,
                repository_side=side,
                path=path,
                message=messages[code],
                line=line,
                column=column,
            ),
        )
    )


def _invalid_input_failure() -> CanonicalParseResult:
    return CanonicalParseResult(
        issues=(
            CanonicalIssue(
                code="malformed_file",
                repository_side="direct",
                path="<input>",
                message="Malformed Qt TS parser input.",
            ),
        )
    )


def _invalid_batch_failure() -> CanonicalParseResult:
    return CanonicalParseResult(
        issues=(
            CanonicalIssue(
                code="malformed_file",
                repository_side="direct",
                path="<input>",
                message="Malformed Qt TS parser input batch.",
            ),
        )
    )
