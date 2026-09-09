from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from verboflex.localization.importing.core import CanonicalParserInput
from verboflex.localization.importing.registry import parse_canonical_snapshot


FIXTURES = Path(__file__).parents[3] / "fixtures" / "localization" / "xliff"


def _input(name: str, *, content: bytes | None = None, layout: str | None = None):
    return CanonicalParserInput(
        format="xliff",  # type: ignore[arg-type]
        repository_side="direct",
        path=f"locales/{name}",
        content=content if content is not None else (FIXTURES / name).read_bytes(),
        layout_identity=layout or f"xliff:locales/{name}",
        layout_version=1,
        base_language="en",
    )


@pytest.mark.parametrize("name", ["valid_12.xlf", "valid_20.xliff", "valid_21.xliff"])
def test_xliff_versions_parse_to_canonical_values(name: str) -> None:
    expected = json.loads((FIXTURES / name.replace(Path(name).suffix, ".expected.json")).read_text())
    result = parse_canonical_snapshot(_input(name))
    assert result.issues == ()
    assert len(result.values) == 1
    value = result.values[0]
    assert value.logical_key == expected["logical_key"]
    assert value.language == expected["language"]
    assert value.source_text == expected["source_text"]
    assert value.translated_text == expected["translated_text"]
    assert value.display_text == expected["translated_text"]
    assert value.locator.format == "xliff"
    assert dict(value.selector.fields)["dialect"] == expected["dialect"]
    assert tuple(node.kind for node in value.structure)[0] == "xliff:document"


@pytest.mark.parametrize(
    ("content", "code"),
    [
        (b'<!DOCTYPE xliff [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><xliff/>', "malformed_file"),
        (b'<xliff xmlns="urn:wrong" version="1.2"/>', "unsupported_structure"),
        (b'<xliff xmlns="urn:oasis:names:tc:xliff:document:2.0" version="3.0"/>', "unsupported_structure"),
        (b'\xff\xfe\x00\x00', "malformed_file"),
    ],
)
def test_xliff_rejects_hostile_or_unsupported_documents_atomically(
    content: bytes, code: str
) -> None:
    result = parse_canonical_snapshot(_input("unsafe.xlf", content=content))
    assert result.values == ()
    assert [issue.code for issue in result.issues] == [code]


def test_xliff_duplicate_unit_id_is_not_silently_overwritten() -> None:
    content = b'''<xliff xmlns="urn:oasis:names:tc:xliff:document:2.0" version="2.0" srcLang="en" trgLang="it"><file id="f"><unit id="same"><segment><source>A</source><target>Uno</target></segment></unit><unit id="same"><segment><source>B</source><target>Due</target></segment></unit></file></xliff>'''
    result = parse_canonical_snapshot(_input("duplicate.xlf", content=content))
    assert result.values == ()
    assert [issue.code for issue in result.issues] == ["duplicate_key"]


def test_xliff_parse_is_deterministic_across_threads() -> None:
    parser_input = _input("valid_20.xliff")
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(parse_canonical_snapshot, [parser_input] * 16))
    assert all(result == results[0] for result in results)
