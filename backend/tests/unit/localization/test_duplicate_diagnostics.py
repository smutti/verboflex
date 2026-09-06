"""Duplicate diagnostics are complete, read-only and identity-aware."""

import importlib
from dataclasses import replace

import pytest

from verboflex.localization.importing.core import CanonicalParserInput


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
