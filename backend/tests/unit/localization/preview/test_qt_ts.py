"""Evidence-first contracts for the strict Qt TS preview detector."""

from __future__ import annotations

import importlib

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from verboflex.services.repository_discovery import RepositorySourceFile


def _detector_module() -> object:
    return importlib.import_module("verboflex.localization.preview.qt_ts")


def _source(path: str, content: bytes) -> RepositorySourceFile:
    return RepositorySourceFile(path=path, content=content)


def _qt_document(
    *,
    language: str = "en",
    context: str = "MainWindow",
    source: str = "Hello",
    translation: str = "Hello",
) -> bytes:
    return (
        f'<TS version="2.1" language="{language}">'
        f"<context><name>{context}</name><message>"
        f"<source>{source}</source><translation>{translation}</translation>"
        "</message></context></TS>"
    ).encode()


def _candidate_count(*files: RepositorySourceFile) -> int:
    detector = _detector_module()
    return len(detector.detect_qt_ts_layouts(files, repository_side="direct").candidates)


def test_qt_plain_messages_produce_one_deterministic_exact_candidate() -> None:
    detector = _detector_module()
    files = (
        _source(
            "translations/app_it-IT.ts",
            _qt_document(language="it_IT", source="button.ok", translation="Va bene"),
        ),
        _source(
            "translations/app_en.ts",
            _qt_document(language="en", source="button.ok", translation="OK"),
        ),
    )

    result = detector.detect_qt_ts_layouts(files, repository_side="translations")

    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.version == 1
    assert candidate.format == "qt_ts"
    assert candidate.repository_side == "translations"
    assert candidate.confidence == 1.0
    assert candidate.files == (
        "translations/app_en.ts",
        "translations/app_it-IT.ts",
    )
    assert candidate.languages == ("en", "it-IT")
    assert candidate.keys == ("button.ok",)
    assert tuple(
        (sample.language, sample.key, sample.translation) for sample in candidate.samples
    ) == (("en", "button.ok", "OK"), ("it-IT", "button.ok", "Va bene"))
    assert candidate.samples_are_partial is True


def test_qt_accepts_utf8_bom_and_case_insensitive_utf8_declaration() -> None:
    content = (
        b"\xef\xbb\xbf<?xml version='1.0' encoding='uTf-8'?>"
        + _qt_document(language="sr_Latn_RS", translation="Zdravo")
    )

    detector = _detector_module()
    result = detector.detect_qt_ts_layouts(
        (_source("translations/app_sr-Latn-RS.ts", content),),
        repository_side="keys",
    )

    assert len(result.candidates) == 1
    assert result.candidates[0].languages == ("sr-Latn-RS",)
    assert result.candidates[0].samples[0].translation == "Zdravo"


@pytest.mark.parametrize(
    "content",
    (
        _qt_document().decode().encode("utf-16"),
        _qt_document().decode().encode("utf-32"),
        b"\xff<TS/>",
        b"<TS language='en'>Hel\xfflo</TS>",
        b"<?xml version='1.0' encoding='iso-8859-1'?><TS/>",
        b"<?xml version='1.0' encoding='UTF-8'?\x00><TS/>",
        b"",
    ),
    ids=(
        "utf-16",
        "utf-32",
        "invalid-utf8-prefix",
        "invalid-utf8-body",
        "declared-non-utf8",
        "embedded-nul",
        "empty",
    ),
)
def test_qt_unsupported_encodings_never_confirm(content: bytes) -> None:
    assert _candidate_count(_source("translations/app_en.ts", content)) == 0


@pytest.mark.parametrize(
    "content",
    (
        (
            b"<!DOCTYPE TS [<!ENTITY secret 'expanded'>]>"
            b"<TS version='2.1' language='en'><context><name>Main</name><message>"
            b"<source>Hello</source><translation>&secret;</translation>"
            b"</message></context></TS>"
        ),
        b"<TS version='2.1' language='en'></TS>",
        b"<TS version='2.1' language='en'><context><name>Main</name></context></TS>",
        (
            b"<TS version='2.1' language='en'><context><name>Main</name>"
            b"<message numerus='yes'><source>Count</source><translation>Counts</translation>"
            b"</message></context></TS>"
        ),
        (
            b"<TS version='2.1' language='en'><context><name>Main</name><message>"
            b"<source>Hello</source><translation type='unfinished'>Hello</translation>"
            b"</message></context></TS>"
        ),
        (
            b"<TS version='2.1' language='en'><context><name>Main</name><message>"
            b"<source>Hello</source><translation type='obsolete'>Hello</translation>"
            b"</message></context></TS>"
        ),
        (
            b"<TS version='2.1' language='en'><context><name>Main</name><message>"
            b"<source>Hello</source><translation variants='yes'>Hello</translation>"
            b"</message></context></TS>"
        ),
        (
            b"<TS version='2.1' language='en'><context><name>Main</name><message>"
            b"<source>Hello</source><translation><lengthvariant>Hello</lengthvariant>"
            b"</translation></message></context></TS>"
        ),
        (
            b"<TS version='2.1' language='en'><context><name>Main</name><message>"
            b"<source>Hello</source><translation><byte value='x41'/></translation>"
            b"</message></context></TS>"
        ),
        (
            b"<TS version='2.1' language='en'><context><name>Main</name><message>"
            b"<source><b>Hello</b></source><translation>Hello</translation>"
            b"</message></context></TS>"
        ),
        (
            b"<TS version='2.1' language='en'><context><name>Main</name>"
            b"<message><source>Hello</source><translation>One</translation></message>"
            b"<message><source>Hello</source><translation>Two</translation></message>"
            b"</context></TS>"
        ),
        b"<TS version='2.1' language='en'><context>",
    ),
    ids=(
        "dtd-entity",
        "empty-ts",
        "empty-context",
        "numerus",
        "unfinished",
        "obsolete",
        "variants-attribute",
        "lengthvariant",
        "byte-node",
        "source-markup",
        "duplicate-message",
        "malformed",
    ),
)
def test_qt_unsupported_grammar_never_confirms(content: bytes) -> None:
    assert _candidate_count(_source("translations/app_en.ts", content)) == 0


@pytest.mark.parametrize(
    ("locale", "canonical"),
    (
        ("en", "en"),
        ("eng", "eng"),
        ("sr_Latn", "sr-Latn"),
        ("sr-latn-rs", "sr-Latn-RS"),
        ("es_419", "es-419"),
    ),
)
def test_qt_uses_the_exact_canonical_locale_subset(locale: str, canonical: str) -> None:
    detector = _detector_module()
    result = detector.detect_qt_ts_layouts(
        (_source(f"translations/app_{canonical}.ts", _qt_document(language=locale)),),
        repository_side="direct",
    )

    assert result.candidates[0].languages == (canonical,)


@pytest.mark.parametrize(
    "locale",
    ("e", "engl", "en-US-POSIX", "en-u-ca-gregory", "12", "en-1", "en-US-x-test"),
)
def test_qt_rejects_locale_variants_extensions_and_malformed_tags(locale: str) -> None:
    assert (
        _candidate_count(_source("translations/app.ts", _qt_document(language=locale))) == 0
    )


@settings(max_examples=50, deadline=None)
@given(st.binary(min_size=0, max_size=256))
def test_qt_arbitrary_bytes_are_always_bounded_and_never_raise(content: bytes) -> None:
    detector = _detector_module()
    result = detector.detect_qt_ts_layouts(
        (_source("translations/app_en.ts", content),),
        repository_side="direct",
    )

    assert isinstance(result.candidates, tuple)

