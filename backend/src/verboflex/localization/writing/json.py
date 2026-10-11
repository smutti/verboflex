"""Original-byte JSON string tokens under complete canonical validation."""

from __future__ import annotations

import json
from unicodedata import category

from verboflex.localization.importing.core import CanonicalParserInput, CanonicalValue
from verboflex.localization.importing.json import MAX_JSON_DEPTH, MAX_JSON_MEMBERS
from verboflex.localization.writing.core import (
    ByteEdit,
    ByteEditBuffer,
    WritebackReason,
    WritebackRejected,
    WriteEdit,
)

type _Address = tuple[str | int, ...]


def encode_text(text: str) -> bytes:
    if any(category(char) == "Cc" and char not in "\t\r\n" for char in text):
        raise WritebackRejected(WritebackReason.INVALID_REPLACEMENT)
    try:
        return json.dumps(text, ensure_ascii=False).encode("utf-8")
    except UnicodeEncodeError:
        raise WritebackRejected(WritebackReason.INVALID_REPLACEMENT) from None


class _TokenIndex:
    """Index validated object/string syntax without serializing any parent object."""

    def __init__(self, content: bytes) -> None:
        self.content = content
        self.position = 0
        self.members = 0
        self.leaves: dict[_Address, tuple[int, int, int]] = {}
        self.objects: dict[tuple[str | int, ...], tuple[int, int]] = {}

    def whitespace(self) -> None:
        while self.position < len(self.content) and self.content[self.position] in b" \r\n\t":
            self.position += 1

    def expect(self, token: int) -> None:
        self.whitespace()
        if self.position >= len(self.content) or self.content[self.position] != token:
            raise WritebackRejected(WritebackReason.UNSUPPORTED_SHAPE)
        self.position += 1

    def quoted(self) -> tuple[str, int, int]:
        self.whitespace()
        start = self.position
        self.expect(ord('"'))
        while self.position < len(self.content):
            char = self.content[self.position]
            self.position += 1
            if char == ord("\\"):
                self.position += 1
            elif char == ord('"'):
                try:
                    value = json.loads(self.content[start : self.position])
                except ValueError, UnicodeDecodeError:
                    raise WritebackRejected(WritebackReason.UNSUPPORTED_SHAPE) from None
                if type(value) is not str:
                    raise WritebackRejected(WritebackReason.UNSUPPORTED_SHAPE)
                return value, start, self.position
        raise WritebackRejected(WritebackReason.UNSUPPORTED_SHAPE)

    def object(self, address: _Address, *, depth: int) -> None:
        if depth > MAX_JSON_DEPTH:
            raise WritebackRejected(WritebackReason.LIMIT_EXCEEDED)
        self.expect(ord("{"))
        self.whitespace()
        index = 0
        if self.content[self.position : self.position + 1] == b"}":
            self.objects[address[1::2]] = (self.position, 0)
            self.position += 1
            return
        while True:
            key, _, _ = self.quoted()
            self.members += 1
            if self.members > MAX_JSON_MEMBERS:
                raise WritebackRejected(WritebackReason.LIMIT_EXCEEDED)
            child_address = (*address, key, index)
            self.expect(ord(":"))
            self.whitespace()
            if self.content[self.position : self.position + 1] == b"{":
                self.object(child_address, depth=depth + 1)
            else:
                _, start, end = self.quoted()
                self.leaves[child_address] = (len(self.leaves), start, end)
            self.whitespace()
            if self.content[self.position : self.position + 1] == b"}":
                self.objects[address[1::2]] = (self.position, index + 1)
                self.position += 1
                return
            self.expect(ord(","))
            index += 1


def plan_edits(
    parser_input: CanonicalParserInput,
    changes: tuple[tuple[CanonicalValue, WriteEdit], ...],
) -> tuple[ByteEdit, ...]:
    index = _TokenIndex(parser_input.content)
    index.object(("document",), depth=1)
    index.whitespace()
    if index.position != len(parser_input.content):
        raise WritebackRejected(WritebackReason.UNSUPPORTED_SHAPE)
    edits = ByteEditBuffer()
    for value, change in changes:
        leaf = index.leaves.get(value.locator.structural_address)
        if leaf is None or leaf[0] != value.locator.position:
            raise WritebackRejected(WritebackReason.AMBIGUOUS_LOCATOR)
        _, start, end = leaf
        edits.append(ByteEdit(start, end, encode_text(change.replacement_text)))
    return edits.freeze()
