"""Repeated Qt metadata cannot amplify a bounded input into unbounded output."""

import json
from dataclasses import replace

import pytest

from tests.unit.localization.importing.test_structure_bounds import qt_input
from verboflex.localization.importing.core import CanonicalParserInput
from verboflex.localization.importing.qt_ts import parse_qt_ts_files
from verboflex.localization.importing.registry import (
    parse_canonical_mapping,
    parse_canonical_snapshot,
)

OUTPUT_LIMIT = 20_971_520


def amplified_input(*, messages=1, variants=0, metadata_bytes=100_000, language="it"):
    if variants:
        content = (
            '<message numerus="yes"><source>key</source><translation>'
            '<numerusform variants="yes">'
            + "".join(
                f'<lengthvariant priority="{index + 1}">x</lengthvariant>'
                for index in range(variants)
            )
            + "</numerusform></translation></message>"
        )
    else:
        content = "".join(
            f'<message id="k{index}"><source>x</source><translation>x</translation></message>'
            for index in range(messages)
        )
    return replace(
        qt_input(),
        path=f"translations/app_{language}.ts",
        content=(
            f'<TS version="2.1" language="{language}"><context><name>C</name><comment>'
            + "m" * metadata_bytes
            + "</comment>"
            + content
            + "</context></TS>"
        ).encode(),
    )


def value_bytes(values):
    return sum(
        len(json.dumps(value.to_mapping(), ensure_ascii=False, separators=(",", ":")).encode())
        for value in values
    )


@pytest.mark.parametrize("shape", ["messages", "nested_variants"])
def test_qt_repeated_metadata_budget_fails_closed_before_retaining_whole_result(shape):
    small = amplified_input(messages=2, variants=2 if shape == "nested_variants" else 0)
    accepted = parse_canonical_snapshot(small)
    assert accepted.issues == ()
    assert len(accepted.values) == 2
    assert all(
        value.structure[2].fields[-1] == ("value", "m" * 100_000) for value in accepted.values
    )
    excessive = amplified_input(messages=256, variants=256 if shape == "nested_variants" else 0)
    assert len(excessive.content) < 1_048_576
    peer_source = qt_input()
    peer = replace(
        peer_source,
        path="translations/app_fr.ts",
        content=peer_source.content.replace(b'language="it"', b'language="fr"'),
    )
    assert parse_canonical_mapping((peer, small)).issues == ()
    rejected = parse_canonical_mapping((peer, excessive))
    assert rejected.values == ()
    assert [issue.code for issue in rejected.issues] == ["unsupported_structure"]


@pytest.mark.parametrize("format", ["json", "android_xml"])
def test_shared_prefix_amplification_is_bounded_during_other_adapter_builds(format):
    if format == "json":

        def source(count):
            return CanonicalParserInput(
                format="json",
                repository_side="direct",
                path="locales/it.json",
                layout_identity="json:flat-per-locale:locales/{locale}.json",
                layout_version=1,
                base_language="en",
                content=json.dumps({"p" * 3000: {f"k{i}": "x" for i in range(count)}}).encode(),
            )

        count = 2500
    else:

        def source(count):
            return CanonicalParserInput(
                format="android_xml",
                repository_side="direct",
                path="res/values/strings.xml",
                layout_identity="res",
                layout_version=1,
                base_language="en",
                content=(
                    "<resources><!--"
                    + "m" * 100_000
                    + '--><string-array name="key">'
                    + "<item>x</item>" * count
                    + "</string-array></resources>"
                ).encode(),
            )

        count = 256
    small = parse_canonical_snapshot(source(2))
    assert small.issues == ()
    assert len(small.values) == 2
    excessive = source(count)
    assert len(excessive.content) < 1_048_576
    rejected = parse_canonical_snapshot(excessive)
    assert rejected.values == ()
    assert [issue.code for issue in rejected.issues] == ["unsupported_structure"]
    assert all(
        "mmm" not in issue.message and len(issue.message) <= 256 for issue in rejected.issues
    )


@pytest.mark.parametrize("parse", [parse_canonical_mapping, parse_qt_ts_files])
def test_qt_output_budget_is_shared_across_peer_files(parse):
    first = amplified_input(messages=120)
    second = amplified_input(messages=120, language="fr")
    for source in (first, second):
        accepted = parse_canonical_snapshot(source)
        assert accepted.issues == ()
        assert len(accepted.values) == 120
        assert OUTPUT_LIMIT / 2 < value_bytes(accepted.values) < OUTPUT_LIMIT
    rejected = parse((first, second))
    assert rejected.values == ()
    assert [issue.code for issue in rejected.issues] == ["unsupported_structure"]
