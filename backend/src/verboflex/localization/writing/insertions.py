"""Insert new resources into verified existing files without tree reserialization."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import replace
from xml.sax.saxutils import escape, quoteattr

from verboflex.localization.importing.core import (
    CanonicalParserInput,
    CanonicalValue,
    canonical_selector_bytes,
)
from verboflex.localization.importing.ios_strings import _decode_document
from verboflex.localization.importing.registry import parse_canonical_snapshot
from verboflex.localization.moko_layout import moko_layout
from verboflex.localization.preview.core import normalize_preview_locale
from verboflex.localization.writing import android_xml, ios_strings, qt_ts
from verboflex.localization.writing.core import (
    ByteEdit,
    WritebackReason,
    WritebackRejected,
    WriteInsert,
    apply_byte_edits,
)
from verboflex.localization.writing.json import _TokenIndex
from verboflex.localization.writing.json import encode_text as json_text
from verboflex.localization.writing.xml_spans import XmlElementSpan, index_xml


def _reject() -> WritebackRejected:
    return WritebackRejected(WritebackReason.UNSUPPORTED_SHAPE)


def _append_xml(node: XmlElementSpan, content: bytes, fragment: bytes) -> ByteEdit:
    if node.self_closing:
        return ByteEdit(
            node.start_tag_end - 2,
            node.start_tag_end,
            b">" + fragment + b"</" + node.name.encode() + b">",
        )
    return ByteEdit(node.end_tag_start, node.end_tag_start, fragment)


def _android(parser: CanonicalParserInput, additions: tuple[WriteInsert, ...]) -> bytes:
    root = index_xml(parser.content)
    if root.name != "resources":
        raise _reject()
    moko = moko_layout(parser.path)
    is_moko = moko is not None and moko[0] == parser.layout_identity
    groups: dict[str, list[WriteInsert]] = defaultdict(list)
    for item in additions:
        if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_.]*", item.logical_key):
            raise WritebackRejected(WritebackReason.INVALID_REPLACEMENT)
        groups[item.logical_key].append(item)
    appends = []
    patches = []
    for key, values in sorted(groups.items()):
        existing = [n for n in root.children if dict(n.attributes).get("name") == key]
        if values[0].selector.kind == "scalar":
            if len(values) != 1 or existing or values[0].selector.fields:
                raise _reject()
            body = android_xml.encode_text(values[0].replacement_text, cdata=False, moko=is_moko)
            appends.append(
                b"\n    <string name=" + quoteattr(key).encode() + b">" + body + b"</string>"
            )
        else:
            quantities = []
            for item in values:
                fields = dict(item.selector.fields)
                quantity = fields.get("quantity")
                if (
                    item.selector.kind != "android_quantity"
                    or set(fields) != {"quantity"}
                    or quantity not in {"zero", "one", "two", "few", "many", "other"}
                ):
                    raise _reject()
                body = android_xml.encode_text(item.replacement_text, cdata=False, moko=is_moko)
                quantities.append(
                    b"\n        <item quantity="
                    + quoteattr(str(quantity)).encode()
                    + b">"
                    + body
                    + b"</item>"
                )
            fragment = b"".join(quantities) + b"\n    "
            if existing:
                if len(existing) != 1 or existing[0].name != "plurals":
                    raise _reject()
                patches.append(_append_xml(existing[0], parser.content, fragment))
            else:
                appends.append(
                    b"\n    <plurals name="
                    + quoteattr(key).encode()
                    + b">"
                    + fragment
                    + b"</plurals>"
                )
    if appends:
        patches.append(_append_xml(root, parser.content, b"".join(appends) + b"\n"))
    return apply_byte_edits(parser.content, tuple(patches))


def _json(parser: CanonicalParserInput, additions: tuple[WriteInsert, ...]) -> bytes:
    index = _TokenIndex(parser.content)
    index.object(("document",), depth=1)
    root = json.loads(parser.content)
    grouped: dict[tuple[str | int, ...], list[bytes]] = defaultdict(list)
    for item in additions:
        fields = dict(item.selector.fields)
        parents = fields.get("parents")
        if (
            item.selector.kind != "json_path"
            or set(fields) != {"parents"}
            or not isinstance(parents, tuple)
            or any(type(p) is not str for p in parents)
        ):
            raise _reject()
        address: tuple[str | int, ...] = parents
        if parser.layout_identity == f"json:locale-rooted:{parser.path}":
            locales = [key for key in root if normalize_preview_locale(key) == item.language]
            if len(locales) != 1:
                raise _reject()
            address = (locales[0], *address)
        if address not in index.objects:
            raise _reject()
        current = root
        for parent in address:
            current = current[parent]
        if item.logical_key in current:
            raise _reject()
        grouped[address].append(
            json_text(item.logical_key) + b": " + json_text(item.replacement_text)
        )
    patches = []
    for address, entries in sorted(grouped.items()):
        position, count = index.objects[address]
        fragment = (b"," if count else b"") + b"\n  " + b",\n  ".join(entries) + b"\n"
        patches.append(ByteEdit(position, position, fragment))
    return apply_byte_edits(parser.content, tuple(patches))


def _ios(parser: CanonicalParserInput, additions: tuple[WriteInsert, ...]) -> bytes:
    decoded = _decode_document(parser.content)
    lines = []
    for item in additions:
        if item.selector.kind != "scalar" or item.selector.fields:
            raise _reject()
        lines.append(
            ios_strings.encode_text(item.logical_key, encoding=decoded.encoding)
            + " = ".encode(decoded.encoding)
            + ios_strings.encode_text(item.replacement_text, encoding=decoded.encoding)
            + ";\n".encode(decoded.encoding)
        )
    return apply_byte_edits(
        parser.content,
        (
            ByteEdit(
                len(parser.content),
                len(parser.content),
                "\n".encode(decoded.encoding) + b"".join(lines),
            ),
        ),
    )


def _form_index(item: WriteInsert) -> int:
    index = dict(item.selector.fields).get("form_index")
    if type(index) is not int:
        raise _reject()
    return index


def _qt(parser: CanonicalParserInput, additions: tuple[WriteInsert, ...]) -> bytes:
    from defusedxml import ElementTree  # type: ignore[import-untyped]

    root = index_xml(parser.content, allow_ts_doctype=True)
    tree = ElementTree.fromstring(parser.content)
    contexts = [child for child in root.children if child.name == "context"]
    names = [child.findtext("name") for child in tree.findall("context")]
    grouped: dict[tuple[str, str, str, str], list[WriteInsert]] = defaultdict(list)
    for item in additions:
        fields = dict(item.selector.fields)
        identity = fields.get("identity_kind")
        context = str(fields.get("context", item.context))
        if identity not in {"source", "id"} or not context or not item.source_text:
            raise _reject()
        if identity == "source" and item.logical_key != item.source_text:
            raise _reject()
        if set(fields) - {"identity_kind", "context", "disambiguation", "form_index"}:
            raise _reject()
        grouped[
            (context, item.logical_key, item.source_text, str(fields.get("disambiguation", "")))
        ].append(item)
    additions_by_context: dict[str, list[bytes]] = defaultdict(list)
    patches = []
    for (context, key, source, comment), values in sorted(grouped.items()):
        is_plural = values[0].selector.kind == "qt_numerus"
        fields = dict(values[0].selector.fields)
        matches = [node for node, name in zip(contexts, names, strict=True) if name == context]
        if len(matches) > 1:
            raise _reject()
        if is_plural:
            ordered = sorted(values, key=lambda i: _form_index(i))
            if any(i.selector.kind != "qt_numerus" for i in ordered):
                raise _reject()
            body = b"".join(
                b"<numerusform>"
                + qt_ts.encode_text(i.replacement_text, cdata=False)
                + b"</numerusform>"
                for i in ordered
            )
        else:
            if len(values) != 1 or values[0].selector.kind != "scalar":
                raise _reject()
            body = qt_ts.encode_text(values[0].replacement_text, cdata=False)
        # Existing message additions are only contiguous plural suffix forms.
        existing = []
        if matches:
            from verboflex.localization.importing.registry import parse_canonical_snapshot

            current = [
                v
                for v in parse_canonical_snapshot(parser).values
                if v.logical_key == key
                and dict(v.selector.fields).get("identity_kind") == fields["identity_kind"]
                and (
                    fields["identity_kind"] == "id"
                    or dict(v.selector.fields).get("context") == context
                )
                and dict(v.selector.fields).get("disambiguation", "") == comment
            ]
            existing = current
        if existing:
            if not is_plural or any(v.selector.kind != "qt_numerus" for v in existing):
                raise _reject()
            indices = sorted(dict(v.selector.fields)["form_index"] for v in existing)
            new_indices = [dict(v.selector.fields)["form_index"] for v in ordered]
            if indices != list(range(len(indices))) or new_indices != list(
                range(len(indices), len(indices) + len(ordered))
            ):
                raise _reject()
            message_index = existing[0].locator.structural_address[4]
            message_nodes = [n for n in matches[0].children if n.name == "message"]
            node = message_nodes[int(message_index)]
            translations = [n for n in node.children if n.name == "translation"]
            if len(translations) != 1:
                raise _reject()
            patches.append(_append_xml(translations[0], parser.content, body))
            continue
        if is_plural and [dict(v.selector.fields)["form_index"] for v in ordered] != list(
            range(len(ordered))
        ):
            raise _reject()
        attr = (" id=" + quoteattr(key)) if fields["identity_kind"] == "id" else ""
        if is_plural:
            attr += ' numerus="yes"'
        message = (
            (
                "\n    <message"
                + attr
                + "><source>"
                + escape(source)
                + "</source>"
                + ("<comment>" + escape(comment) + "</comment>" if comment else "")
                + "<translation>"
            ).encode()
            + body
            + b"</translation></message>"
        )
        additions_by_context[context].append(message)
    new_contexts = []
    for context, messages in sorted(additions_by_context.items()):
        matches = [node for node, name in zip(contexts, names, strict=True) if name == context]
        if matches:
            patches.append(_append_xml(matches[0], parser.content, b"".join(messages) + b"\n"))
        else:
            new_contexts.append(
                ("\n<context><name>" + escape(context) + "</name>").encode()
                + b"".join(messages)
                + b"\n</context>"
            )
    if new_contexts:
        patches.append(_append_xml(root, parser.content, b"".join(new_contexts) + b"\n"))
    return apply_byte_edits(parser.content, tuple(patches))


def render_insertions(parser: CanonicalParserInput, additions: tuple[WriteInsert, ...]) -> bytes:
    parsed = parse_canonical_snapshot(parser)
    if parsed.issues:
        raise _reject()

    def identity(v: CanonicalValue | WriteInsert) -> tuple[str, str, bytes]:
        return (v.logical_key, v.language, canonical_selector_bytes(v.selector))

    originals = {identity(v): v for v in parsed.values}
    requested = {identity(v): v for v in additions}
    if len(requested) != len(additions) or set(originals) & set(requested):
        raise WritebackRejected(WritebackReason.AMBIGUOUS_LOCATOR)
    for item in additions:
        item.__post_init__()
    adapters = {"android_xml": _android, "json": _json, "ios_strings": _ios, "qt_ts": _qt}
    adapter = adapters.get(parser.format)
    if adapter is None:
        raise WritebackRejected(WritebackReason.UNSUPPORTED_FORMAT)
    try:
        content = adapter(parser, additions)
    except ValueError, KeyError, IndexError, TypeError, UnicodeError:
        raise _reject() from None
    result = parse_canonical_snapshot(replace(parser, content=content))
    actual = {identity(v): v for v in result.values}
    if result.issues or set(actual) != set(originals) | set(requested):
        raise WritebackRejected(WritebackReason.INVALID_OUTPUT)
    for key, old in originals.items():
        value = actual[key]
        if (value.source_text, value.translated_text, value.display_text) != (
            old.source_text,
            old.translated_text,
            old.display_text,
        ):
            raise WritebackRejected(WritebackReason.INVALID_OUTPUT)
    if any(actual[key].display_text != item.replacement_text for key, item in requested.items()):
        raise WritebackRejected(WritebackReason.INVALID_OUTPUT)
    if parser.format == "qt_ts" and any(
        actual[key].source_text != item.source_text for key, item in requested.items()
    ):
        raise WritebackRejected(WritebackReason.INVALID_OUTPUT)
    return content
