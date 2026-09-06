"""Complete structures share one producer and consumer cardinality contract."""

from dataclasses import replace

import pytest

from verboflex.localization.importing.core import CanonicalParserInput
from verboflex.localization.importing.registry import (
    parse_canonical_mapping,
    parse_canonical_snapshot,
)

STRUCTURE_LIMIT = 16_384


def android_input(inline_count=44, comments=0):
    content = (
        '<resources><string name="structured">'
        + "<b>x</b>" * inline_count
        + "<!--safe-->" * comments
        + "</string></resources>"
    )
    return CanonicalParserInput(
        format="android_xml",
        repository_side="direct",
        path="res/values/strings.xml",
        content=content.encode(),
        layout_identity="res",
        layout_version=1,
        base_language="en",
    )


def qt_input(dependencies=130):
    content = (
        '<TS version="2.1" language="it"><dependencies>'
        + "<dependency/>" * dependencies
        + "</dependencies><context><name>C</name><message><source>Structured</source>"
        "<translation>Strutturato</translation></message></context></TS>"
    )
    return CanonicalParserInput(
        format="qt_ts",
        repository_side="direct",
        path="translations/app_it.ts",
        content=content.encode(),
        layout_identity="qt-ts:translations/app_{locale}.ts",
        layout_version=1,
        base_language="en",
    )


def ios_input():
    return CanonicalParserInput(
        format="ios_strings", repository_side="direct",
        path="mobile/it_IT.lproj/Localizable.strings",
        content=b"/**/ " * 4096 + b'"key"="value";',
        layout_identity="ios-strings:mobile/{locale}.lproj/Localizable.strings",
        layout_version=1, base_language="en",
    )


def test_canonical_value_rejects_structure_above_shared_ceiling():
    parsed = parse_canonical_snapshot(android_input())
    assert not parsed.issues
    value = parsed.values[0]
    exact = replace(value, structure=(value.structure[0],) * STRUCTURE_LIMIT)
    assert len(exact.structure) == STRUCTURE_LIMIT
    with pytest.raises(ValueError, match="canonical value rejected"):
        replace(value, structure=exact.structure + (value.structure[0],))


@pytest.mark.parametrize("format", ["android_xml", "qt_ts"])
def test_structure_ceiling_preserves_exact_limit_and_rejects_whole_mapping(format):
    if format == "android_xml":
        exact_input = android_input(inline_count=1364, comments=2)
        excessive_input = android_input(inline_count=1364, comments=3)
        peer_input = android_input(inline_count=1)
        peer = replace(
            peer_input, path="res/values/peer.xml",
            content=peer_input.content.replace(b'name="structured"', b'name="peer"'),
        )
    else:
        exact_input = qt_input(dependencies=STRUCTURE_LIMIT - 7)
        excessive_input = qt_input(dependencies=STRUCTURE_LIMIT - 6)
        peer_input = qt_input(dependencies=1)
        peer = replace(
            peer_input,
            path="translations/app_fr.ts",
            content=peer_input.content.replace(b'language="it"', b'language="fr"'),
        )
    exact = parse_canonical_snapshot(exact_input)
    assert exact.issues == ()
    assert len(exact.values[0].structure) == (4096 if format == "android_xml" else STRUCTURE_LIMIT)
    assert parse_canonical_mapping((peer, exact_input)).issues == ()
    excessive = parse_canonical_mapping((peer, excessive_input))
    assert excessive.values == ()
    assert [issue.code for issue in excessive.issues] == ["unsupported_structure"]
    assert all(len(issue.message) <= 256 for issue in excessive.issues)
    assert all(
        "dependency" not in issue.message and "<b>" not in issue.message
        for issue in excessive.issues
    )
