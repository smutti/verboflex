"""Repeated Qt metadata cannot amplify a bounded input into unbounded output."""

import importlib
import json
from dataclasses import replace

import pytest

from tests.unit.localization.importing.test_structure_bounds import qt_input
from verboflex.localization.importing.core import (
    CanonicalOutputLimitExceeded,
    CanonicalParserInput,
    CanonicalValueBuffer,
)
from verboflex.localization.importing.qt_ts import parse_qt_ts_files
from verboflex.localization.importing.registry import (
    parse_canonical_mapping,
    parse_canonical_snapshot,
)

OUTPUT_LIMIT = 20_971_520


@pytest.mark.parametrize("source_bytes", [0, OUTPUT_LIMIT])
def test_exact_utf8_output_budget_preserves_last_value_on_one_byte_overflow(source_bytes):
    parsed = parse_canonical_snapshot(qt_input(dependencies=1))
    base = replace(parsed.values[0], source_text='é"' * 30_000)
    size = value_bytes((base,))
    limit = OUTPUT_LIMIT + source_bytes
    count, remaining = divmod(limit, size)
    first = replace(base, source_text=base.source_text + "x" * remaining)
    values = CanonicalValueBuffer(source_bytes=source_bytes)
    values.append(first)
    values.extend(base for _ in range(count - 1))
    assert value_bytes(values) == limit
    with pytest.raises(CanonicalOutputLimitExceeded, match="canonical output limit exceeded"):
        values.replace_last(replace(base, source_text=base.source_text + "x"))
    assert len(values) == count
    assert values[-1] == base
    values.replace_last(replace(base, source_text=base.source_text[:-1]))
    values.replace_last(base)
    assert value_bytes(values) == limit


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
def test_qt_repeated_metadata_budget_fails_closed_before_retaining_whole_result(shape, monkeypatch):
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
    constructed = observe_value_construction(monkeypatch, "qt_ts")
    rejected = parse_canonical_mapping((peer, excessive))
    assert 2 < len(constructed) < 256
    assert rejected.values == ()
    assert [issue.code for issue in rejected.issues] == ["unsupported_structure"]


@pytest.mark.parametrize("format", ["json", "android_xml"])
def test_shared_prefix_amplification_is_bounded_during_other_adapter_builds(format, monkeypatch):
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
    constructed = observe_value_construction(monkeypatch, format)
    rejected = parse_canonical_snapshot(excessive)
    assert 2 < len(constructed) < count
    assert rejected.values == ()
    assert [issue.code for issue in rejected.issues] == ["unsupported_structure"]
    assert all(
        "mmm" not in issue.message and len(issue.message) <= 256 for issue in rejected.issues
    )


def observe_value_construction(monkeypatch, adapter_name):
    adapter = importlib.import_module(f"verboflex.localization.importing.{adapter_name}")
    constructor = adapter.CanonicalValue
    calls = []

    def construct(**fields):
        calls.append(1)
        return constructor(**fields)

    monkeypatch.setattr(adapter, "CanonicalValue", construct)
    return calls


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


def test_output_budget_is_shared_across_separate_repository_sides():
    keys = replace(amplified_input(messages=120, language="en"), repository_side="keys")
    translations = replace(amplified_input(messages=120), repository_side="translations")
    assert parse_canonical_snapshot(keys).issues == ()
    assert parse_canonical_snapshot(translations).issues == ()
    result = parse_canonical_mapping((keys, translations))
    assert result.values == ()
    assert [issue.code for issue in result.issues] == ["unsupported_structure"]


def test_source_join_cannot_reintroduce_unbounded_output_after_both_sides_pass():
    def source(side, content):
        return CanonicalParserInput(
            format="json",
            repository_side=side,
            path="locales.json",
            layout_identity="json:locale-rooted:locales.json",
            layout_version=1,
            base_language="en",
            content=json.dumps(content).encode(),
        )

    keys = source("keys", {"en": {"key": "s" * 900_000}})
    locales = [
        "es",
        "fr",
        "it",
        "de",
        "pt",
        "nl",
        "da",
        "sv",
        "no",
        "fi",
        "pl",
        "cs",
        "sk",
        "hu",
        "ro",
        "bg",
        "el",
        "tr",
        "uk",
        "ru",
        "ar",
        "he",
        "ja",
        "ko",
    ]
    translations = source("translations", {locale: {"key": "x"} for locale in locales})
    key_result = parse_canonical_snapshot(keys)
    target_result = parse_canonical_snapshot(translations)
    assert key_result.issues == target_result.issues == ()
    assert len(key_result.values) == 1 and len(target_result.values) == 24
    small_targets = source("translations", {"it": {"key": "x"}})
    small = parse_canonical_mapping((keys, small_targets))
    assert small.issues == ()
    assert small.values[-1].source_text == "s" * 900_000
    result = parse_canonical_mapping((keys, translations))
    assert result.values == ()
    assert [issue.code for issue in result.issues] == ["unsupported_structure"]


@pytest.mark.parametrize("format", ["android_xml", "json", "ios_strings"])
def test_format_peer_apis_reject_combined_output_above_expansion_allowance(format):
    adapter = importlib.import_module(f"verboflex.localization.importing.{format}")
    name = "json_localization" if format == "json" else format
    parse = getattr(adapter, f"parse_{name}_files")

    def source(index):
        key = f"k{index:02d}"
        text = "x" * 900_000
        if format == "android_xml":
            path = f"res/values/file-{index}.xml"
            layout = "res"
            content = f'<resources><string name="{key}">{text}</string></resources>'
        elif format == "json":
            path = f"file-{index}.json"
            layout = f"json:locale-rooted:{path}"
            content = json.dumps({"en": {key: text}})
        else:
            path = f"catalogs/en.lproj/file-{index}.strings"
            layout = f"ios-strings:catalogs/{{locale}}.lproj/file-{index}.strings"
            content = f'"{key}"="{text}";'
        return CanonicalParserInput(
            format=format,
            repository_side="direct",
            path=path,
            layout_identity=layout,
            layout_version=1,
            base_language="en",
            content=content.encode(),
        )

    first = source(0)
    accepted = parse((first,))
    assert accepted.issues == () and len(accepted.values) == 1
    expansion = value_bytes(accepted.values) - len(first.content)
    count = OUTPUT_LIMIT // expansion + 1
    inputs = tuple(source(index) for index in range(count))
    assert sum(len(item.content) for item in inputs) < OUTPUT_LIMIT
    rejected = parse(inputs)
    assert rejected.values == ()
    assert [issue.code for issue in rejected.issues] == ["unsupported_structure"]
    assert all(
        "xxx" not in issue.message and len(issue.message) <= 256 for issue in rejected.issues
    )
