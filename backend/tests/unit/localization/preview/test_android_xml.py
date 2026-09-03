"""Evidence-first contracts for the strict Android XML preview detector."""

from __future__ import annotations

import importlib
from dataclasses import FrozenInstanceError
from itertools import product

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from verboflex.services.repository_discovery import (
    SOURCE_DISCOVERY_BUDGET,
    RepositorySourceFile,
)


def _detector_module() -> object:
    """Resolve the production detector at test time so RED is a behavioral failure."""
    return importlib.import_module("verboflex.localization.preview.android_xml")


def _source(path: str, content: bytes) -> RepositorySourceFile:
    return RepositorySourceFile(path=path, content=content)


def _plain_xml(*, key: str = "hello", translation: str = "Hello") -> bytes:
    return f'<resources><string name="{key}">{translation}</string></resources>'.encode()


def _xml_at_size(size: int, *, key: str = "hello") -> bytes:
    minimal = _plain_xml(key=key)
    assert len(minimal) <= size
    return minimal + (b" " * (size - len(minimal)))


def _candidate_count(*files: RepositorySourceFile) -> int:
    detector = _detector_module()
    return len(detector.detect_android_layouts(files, repository_side="direct").candidates)


def test_android_plain_strings_produce_one_deterministic_exact_candidate() -> None:
    """One Android resource root yields one immutable, exact, sorted layout."""
    detector = _detector_module()
    files = (
        RepositorySourceFile(
            path="app/src/main/res/values-it/strings.xml",
            content=(
                b'<resources><string name="welcome.title">Benvenuto</string>'
                b'<string name="button.ok">Va bene</string></resources>'
            ),
        ),
        RepositorySourceFile(
            path="app/src/main/res/values/strings.xml",
            content=(
                b'<resources><string name="welcome.title">Welcome</string>'
                b'<string name="button.ok">OK</string></resources>'
            ),
        ),
    )

    result = detector.detect_android_layouts(files, repository_side="direct")

    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.version == 1
    assert candidate.format == "android_xml"
    assert candidate.repository_side == "direct"
    assert candidate.layout_identity == "app/src/main/res"
    assert candidate.confidence == 1.0
    assert candidate.files == (
        "app/src/main/res/values-it/strings.xml",
        "app/src/main/res/values/strings.xml",
    )
    assert candidate.languages == ("default", "it")
    assert candidate.keys == ("button.ok", "welcome.title")
    assert tuple(
        (sample.language, sample.key, sample.translation) for sample in candidate.samples
    ) == (
        ("default", "button.ok", "OK"),
        ("default", "welcome.title", "Welcome"),
        ("it", "button.ok", "Va bene"),
        ("it", "welcome.title", "Benvenuto"),
    )
    assert candidate.samples_are_partial is True
    with pytest.raises(FrozenInstanceError):
        candidate.confidence = 0.5


def test_android_accepts_utf8_bom_and_case_insensitive_utf8_declaration() -> None:
    """The only promoted decoder is strict UTF-8 with an optional UTF-8 BOM."""
    detector = _detector_module()
    result = detector.detect_android_layouts(
        (
            RepositorySourceFile(
                path="res/values-fr/labels.xml",
                content=(
                    b"\xef\xbb\xbf<?xml version='1.0' encoding='uTf-8'?>"
                    b'<resources><string name="hello">Bonjour</string></resources>'
                ),
            ),
        ),
        repository_side="translations",
    )

    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.repository_side == "translations"
    assert candidate.languages == ("fr",)
    assert candidate.keys == ("hello",)
    assert candidate.samples[0].translation == "Bonjour"
    assert candidate.samples_are_partial is True


@pytest.mark.parametrize(
    "content",
    (
        "<resources><string name='hello'>Hello</string></resources>".encode("utf-16"),
        "<resources><string name='hello'>Hello</string></resources>".encode("utf-32"),
        b"\xff<resources><string name='hello'>Hello</string></resources>",
        b"<resources><string name='hello'>Hel\xfflo</string></resources>",
        b"<?xml version='1.0' encoding='iso-8859-1'?><resources/>",
        b"<?xml version='1.0' encoding='UTF-8'?\x00><resources/>",
        b"",
    ),
    ids=(
        "utf-16",
        "utf-32",
        "invalid-utf-8",
        "invalid-utf-8-in-translation",
        "declared-non-utf-8",
        "embedded-nul",
        "empty",
    ),
)
def test_android_unsupported_encodings_never_confirm(content: bytes) -> None:
    assert _candidate_count(_source("res/values/strings.xml", content)) == 0


@pytest.mark.parametrize(
    "content",
    (
        (
            b"<!DOCTYPE resources [<!ENTITY secret 'expanded'>]>"
            b"<resources><string name='hello'>&secret;</string></resources>"
        ),
        (
            b"<resources><string name='hello'>Hello</string>"
            b"<string name='hello'>Again</string></resources>"
        ),
        b"<resources><string name='hello'><b>Hello</b></string></resources>",
        b"<resources><plurals name='count'/></resources>",
        b"<resources><string-array name='items'/></resources>",
        b"<wrapper><resources><string name='hello'>Hello</string></resources></wrapper>",
        b"<resources><string name='hello'>Hello</resources>",
        b"<resources/>",
    ),
    ids=(
        "dtd-entity",
        "duplicate-name",
        "child-markup",
        "plurals",
        "string-array",
        "content-outside-root",
        "malformed",
        "empty-resources",
    ),
)
def test_android_unsupported_grammar_never_confirms(content: bytes) -> None:
    assert _candidate_count(_source("res/values/strings.xml", content)) == 0


def test_android_empty_names_and_unrelated_files_never_confirm_or_interfere() -> None:
    empty_name = b"<resources><string name=''>Hello</string></resources>"
    unrelated = _source("docs/example.xml", b"not Android XML")

    assert _candidate_count(_source("res/values/strings.xml", empty_name)) == 0
    assert _candidate_count(unrelated, _source("res/values/strings.xml", _plain_xml())) == 1


def test_android_duplicate_source_paths_and_unsupported_qualifiers_block_layout() -> None:
    duplicate_path = (
        _source("res/values/first.xml", _plain_xml(key="first")),
        _source("res/values/first.xml", _plain_xml(key="second")),
    )
    unsupported_qualifier = (
        _source("res/values/strings.xml", _plain_xml()),
        _source("res/values-en-rUS/strings.xml", _plain_xml()),
    )

    assert _candidate_count(*duplicate_path) == 0
    assert _candidate_count(*unsupported_qualifier) == 0


def test_android_case_folded_language_duplicates_block_the_layout() -> None:
    files = (
        _source("res/values-en/strings.xml", _plain_xml()),
        _source("res/values-EN/strings.xml", _plain_xml()),
    )

    assert _candidate_count(*files) == 0


def test_android_raw_file_limit_accepts_exact_boundary_and_rejects_one_byte_more() -> None:
    maximum = SOURCE_DISCOVERY_BUDGET.max_file_bytes

    assert _candidate_count(_source("res/values/strings.xml", _xml_at_size(maximum))) == 1
    assert _candidate_count(_source("res/values/strings.xml", _xml_at_size(maximum + 1))) == 0


def test_android_total_byte_limit_accepts_exact_boundary_and_rejects_one_byte_more() -> None:
    per_file = SOURCE_DISCOVERY_BUDGET.max_file_bytes
    file_count = SOURCE_DISCOVERY_BUDGET.max_total_bytes // per_file
    exact = tuple(
        _source(
            f"res/values/strings-{index:02d}.xml",
            _xml_at_size(per_file, key=f"key-{index:02d}"),
        )
        for index in range(file_count)
    )

    assert sum(len(file.content) for file in exact) == SOURCE_DISCOVERY_BUDGET.max_total_bytes
    assert _candidate_count(*exact) == 1
    assert (
        _candidate_count(
            *exact,
            _source("res/values/overflow.xml", _plain_xml(key="overflow")),
        )
        == 0
    )


def test_android_language_limit_accepts_32_and_rejects_33_without_truncation() -> None:
    languages = tuple(
        first + second for first, second in product("abcdefghijklmnopqrstuvwxyz", repeat=2)
    )[:33]

    accepted = tuple(
        _source(f"res/values-{language}/strings.xml", _plain_xml()) for language in languages[:32]
    )
    rejected = accepted + (_source(f"res/values-{languages[32]}/strings.xml", _plain_xml()),)

    detector = _detector_module()
    result = detector.detect_android_layouts(accepted, repository_side="direct")
    assert len(result.candidates) == 1
    assert result.candidates[0].languages == tuple(sorted(languages[:32]))
    assert _candidate_count(*rejected) == 0


def test_android_samples_are_capped_per_language_and_globally_in_code_point_order() -> None:
    languages = ("aa", "ab", "ac", "ad", "ae", "af", "ag", "ah", "ai", "aj", "ak")
    keys = tuple(f"key-{index:02d}" for index in range(11))
    files = tuple(
        _source(
            f"res/values-{language}/strings.xml",
            b"<resources>"
            + b"".join(
                f'<string name="{key}">{language}-{key}</string>'.encode() for key in reversed(keys)
            )
            + b"</resources>",
        )
        for language in reversed(languages)
    )

    detector = _detector_module()
    candidate = detector.detect_android_layouts(files, repository_side="direct").candidates[0]
    pairs = tuple((sample.language, sample.key) for sample in candidate.samples)

    assert len(candidate.samples) == 100
    assert pairs == tuple(sorted(pairs))
    assert all(pairs.count((language, key)) <= 1 for language, key in pairs)
    assert all(
        sum(sample.language == language for sample in candidate.samples) <= 10
        for language in candidate.languages
    )
    assert tuple(sample.key for sample in candidate.samples[:10]) == keys[:10]
    assert candidate.samples_are_partial is True


@settings(max_examples=100, deadline=None)
@given(st.binary(max_size=2048))
def test_arbitrary_invalid_android_bytes_never_crash_or_confirm(payload: bytes) -> None:
    assert _candidate_count(_source("res/values/strings.xml", b"\xff" + payload)) == 0


@pytest.mark.parametrize("raw", (None, (), {"unexpected": "field"}))
def test_untrusted_candidate_mappings_fail_closed_before_persistence(raw: object) -> None:
    core = importlib.import_module("verboflex.localization.preview.core")

    with pytest.raises(ValueError, match="preview candidate rejected"):
        core.layout_candidate_from_mapping(raw)
