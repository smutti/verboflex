"""Duplicate diagnostics are complete, read-only and identity-aware."""

import importlib
from dataclasses import replace
from typing import Any, cast

import pytest

from verboflex.localization.importing.android_xml import parse_android_xml
from verboflex.localization.importing.core import (
    CanonicalDiagnosticResult,
    CanonicalIssue,
    CanonicalParserInput,
)
from verboflex.localization.importing.registry import (
    parse_canonical_mapping_quarantining_duplicates,
)
from verboflex.localization.preview.registry import detect_preview_layouts
from verboflex.services.repository_discovery import RepositorySourceFile


def inspect(inputs):
    try:
        module = importlib.import_module("verboflex.localization.duplicate_diagnostics")
    except ModuleNotFoundError:
        pytest.fail("duplicate diagnostics are not implemented")
    return module.inspect_duplicate_keys(inputs)


def source(xml: str, **changes):
    return replace(
        CanonicalParserInput(
            format="android_xml",
            repository_side="direct",
            path="res/values/strings.xml",
            content=f"<resources>{xml}</resources>".encode(),
            layout_identity="res",
            layout_version=1,
            base_language="en",
        ),
        **changes,
    )


def test_reports_every_occurrence_without_first_or_last_wins():
    report = inspect(
        (
            source(
                '<string name="same">One</string><string name="safe">OK</string>'
                '<string name="same">Two</string><string name="same">One</string>'
            ),
        )
    )
    assert report.complete
    assert len(report.groups) == 1
    assert report.repeated_occurrences == 2
    group = report.groups[0]
    assert group.key_preview == "same"
    assert group.language == "en"
    assert [occurrence.position for occurrence in group.occurrences] == [0, 2, 3]
    assert all(occurrence.path == "res/values/strings.xml" for occurrence in group.occurrences)
    assert "One" not in repr(report) and "Two" not in repr(report)


def test_quarantine_parser_imports_unique_values_without_choosing_a_duplicate():
    result = parse_canonical_mapping_quarantining_duplicates(
        (
            source(
                '<string name="same">One</string><string name="safe">OK</string>'
                '<string name="same">Two</string>'
            ),
        )
    )

    assert result.issues == ()
    assert [(value.logical_key, value.display_text) for value in result.values] == [("safe", "OK")]


def test_ios_base_lproj_falls_back_only_when_an_explicit_base_locale_peer_is_absent():
    contents = {
        "mobile/Base.lproj/Localizable.strings": b'"welcome" = "Base fallback";',
        "mobile/en.lproj/Localizable.strings": b'"welcome" = "Explicit English";',
    }
    snapshot = tuple(
        RepositorySourceFile(path=path, content=content) for path, content in contents.items()
    )
    preview = detect_preview_layouts(snapshot, repository_side="direct")
    assert len(preview.candidates) == 1
    candidate = preview.candidates[0]
    parser_inputs = tuple(
        CanonicalParserInput(
            format=candidate.format,
            repository_side="direct",
            path=path,
            content=contents[path],
            layout_identity=candidate.layout_identity,
            layout_version=candidate.version,
            base_language="en",
        )
        for path in candidate.files
    )

    result = parse_canonical_mapping_quarantining_duplicates(parser_inputs)
    reversed_result = parse_canonical_mapping_quarantining_duplicates(
        tuple(reversed(parser_inputs))
    )

    assert result.issues == ()
    assert inspect(parser_inputs).groups == ()
    assert reversed_result == result
    assert [
        (value.language, value.display_text, value.locator.path) for value in result.values
    ] == [("en", "Explicit English", "mobile/en.lproj/Localizable.strings")]


def test_ios_base_lproj_remains_the_base_language_when_no_explicit_peer_exists():
    parser_input = CanonicalParserInput(
        format="ios_strings",
        repository_side="direct",
        path="mobile/Base.lproj/Localizable.strings",
        content=b'"welcome" = "Base fallback";',
        layout_identity="ios-strings:mobile/{locale}.lproj/Localizable.strings",
        layout_version=1,
        base_language="en",
    )

    result = parse_canonical_mapping_quarantining_duplicates((parser_input,))

    assert result.issues == ()
    assert [
        (value.language, value.display_text, value.locator.path) for value in result.values
    ] == [("en", "Base fallback", "mobile/Base.lproj/Localizable.strings")]


def test_cross_file_duplicates_are_grouped_but_other_languages_are_not():
    first = source('<string name="same">Value</string>')
    second = replace(first, path="res/values/other.xml")
    italian = replace(first, path="res/values-it/strings.xml")
    report = inspect((first, second, italian))
    assert report.complete
    assert len(report.groups) == 1
    assert report.repeated_occurrences == 1
    assert {occurrence.path for occurrence in report.groups[0].occurrences} == {
        first.path,
        second.path,
    }
    assert inspect((first, italian)).groups == ()


def test_invalid_peer_does_not_look_like_complete_empty_diagnostics():
    report = inspect(
        (
            source('<string name="safe">OK</string>'),
            source(
                "",
                path="res/values/bad.xml",
                content=b'<!DOCTYPE resources [<!ENTITY e "bad">]><resources/>',
            ),
        )
    )
    assert not report.complete
    assert report.issue_codes == ("malformed_file",)


def test_moko_base_is_explicit_and_duplicate_markup_is_preserved_for_validation():
    report = inspect(
        (
            source(
                '<string name="same">A <b>B</b></string>'
                '<string name="same" translatable="false">C</string>',
                path="module/moko-resources/base/strings.xml",
                layout_identity="module/moko-resources",
                base_language="fr",
            ),
        )
    )
    assert report.complete
    assert report.groups[0].language == "fr"
    assert report.repeated_occurrences == 1


def test_unsupported_string_content_keeps_all_duplicate_source_positions():
    report = inspect(
        (source('<string name="same">Unsupported \\z</string><string name="same">Other</string>'),)
    )
    assert report.complete is False
    assert report.issue_codes == ("unsupported_structure",)
    assert report.repeated_occurrences == 1
    assert [occurrence.position for occurrence in report.groups[0].occurrences] == [0, 1]


@pytest.mark.parametrize(
    "parser_input",
    (
        CanonicalParserInput(
            format="json",
            repository_side="direct",
            path="assets/en/messages.json",
            content=b'{"same":"One","safe":"OK","same":"Two"}',
            layout_identity="json:flat-per-locale:assets/{locale}/messages.json",
            layout_version=1,
            base_language="en",
        ),
        CanonicalParserInput(
            format="ios_strings",
            repository_side="direct",
            path="mobile/en.lproj/Localizable.strings",
            content=b'"same" = "One";\n"safe" = "OK";\n"same" = "Two";',
            layout_identity="ios-strings:mobile/{locale}.lproj/Localizable.strings",
            layout_version=1,
            base_language="en",
        ),
        CanonicalParserInput(
            format="qt_ts",
            repository_side="direct",
            path="translations/app_en.ts",
            content=(
                b'<TS version="2.1" language="en"><context><name>Main</name>'
                b'<message id="same"><source>One</source><translation>One</translation></message>'
                b'<message id="safe"><source>OK</source><translation>OK</translation></message>'
                b'<message id="same"><source>Two</source><translation>Two</translation></message>'
                b"</context></TS>"
            ),
            layout_identity="qt-ts:translations/app_{locale}.ts",
            layout_version=1,
            base_language="en",
        ),
        CanonicalParserInput(
            format="xliff",
            repository_side="direct",
            path="translations/app_it.xliff",
            content=(
                b'<xliff xmlns="urn:oasis:names:tc:xliff:document:2.0" '
                b'version="2.0" srcLang="en" trgLang="it"><file id="app">'
                b'<unit id="same"><segment><source>One</source><target>Uno</target>'
                b'</segment></unit><unit id="safe"><segment><source>OK</source>'
                b'<target>OK</target></segment></unit><unit id="same"><segment>'
                b"<source>Two</source><target>Due</target></segment></unit></file></xliff>"
            ),
            layout_identity="xliff:translations/app_{locale}.xliff",
            layout_version=1,
            base_language="en",
        ),
    ),
    ids=("json", "ios-strings", "qt-ts", "xliff"),
)
def test_every_supported_format_reports_duplicate_source_positions(parser_input):
    report = inspect((parser_input,))

    assert report.complete
    assert report.issue_codes == ()
    assert report.repeated_occurrences == 1
    assert len(report.groups) == 1
    assert report.groups[0].key_preview == "same"
    assert [occurrence.position for occurrence in report.groups[0].occurrences] == [0, 2]


def test_diagnostic_result_rejects_noncanonical_containers_and_members() -> None:
    parsed = parse_android_xml(source('<string name="a">A</string><string name="b">B</string>'))
    first, second = parsed.values
    first_issue = CanonicalIssue(
        code="malformed_file",
        repository_side="direct",
        path="a.xml",
        message="Malformed file.",
    )
    second_issue = CanonicalIssue(
        code="unsupported_structure",
        repository_side="direct",
        path="b.xml",
        message="Unsupported structure.",
    )

    rejected = (
        {"values": cast(Any, [first])},
        {"values": cast(Any, (object(),))},
        {"issues": cast(Any, (object(),))},
        {"values": (first,), "issues": (first_issue,)},
        {"values": (second, first)},
        {"issues": (second_issue, first_issue)},
        {"issues": (first_issue, first_issue)},
    )
    for arguments in rejected:
        with pytest.raises(ValueError, match="canonical diagnostic result rejected"):
            CanonicalDiagnosticResult(**arguments)


@pytest.mark.parametrize(
    ("module_name", "public_name", "private_name"),
    (
        (
            "verboflex.localization.importing.json",
            "parse_json_localization",
            "_parse_json_localization",
        ),
        (
            "verboflex.localization.importing.ios_strings",
            "parse_ios_strings",
            "_parse_ios_strings",
        ),
        (
            "verboflex.localization.importing.qt_ts",
            "parse_qt_ts",
            "_parse_qt_ts",
        ),
    ),
)
def test_canonical_entrypoints_reject_diagnostic_output(
    monkeypatch: pytest.MonkeyPatch,
    module_name: str,
    public_name: str,
    private_name: str,
) -> None:
    module = importlib.import_module(module_name)
    monkeypatch.setattr(
        module,
        private_name,
        lambda _parser_input, *, allow_duplicates: CanonicalDiagnosticResult(),
    )

    with pytest.raises(AssertionError, match="returned diagnostic output"):
        getattr(module, public_name)(source('<string name="safe">OK</string>'))
