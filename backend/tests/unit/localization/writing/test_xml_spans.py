from __future__ import annotations

import importlib
from typing import Any

import pytest

from verboflex.localization.writing.core import WritebackRejected


def _xml() -> Any:
    try:
        return importlib.import_module("verboflex.localization.writing.xml_spans")
    except ModuleNotFoundError:
        pytest.fail("A bounded XML event index over the original bytes is not implemented")


def test_byte_offsets_preserve_bom_crlf_and_quoted_angle_brackets() -> None:
    content = b'\xef\xbb\xbf<resources>\r\n<!--first--><string name="a>b">old</string></resources>'
    root = _xml().index_xml(content)
    leaf = root.children[0]
    assert dict(leaf.attributes)["name"] == "a>b"
    assert content[leaf.start : leaf.start_tag_end] == b'<string name="a>b">'
    assert content[leaf.start_tag_end : leaf.end_tag_start] == b"old"
    assert content[leaf.end_tag_start : leaf.end] == b"</string>"


@pytest.mark.parametrize(
    "content",
    [
        b'<!DOCTYPE resources [<!ENTITY x "secret">]><resources>&x;</resources>',
        b'<!DOCTYPE resources SYSTEM "https://example.invalid/private"><resources/>',
        b"<resources>",
    ],
)
def test_index_never_expands_entities_or_accepts_malformed_xml(content: bytes) -> None:
    with pytest.raises(WritebackRejected):
        _xml().index_xml(content)
