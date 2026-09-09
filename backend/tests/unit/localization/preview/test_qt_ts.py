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
    content = b"\xef\xbb\xbf<?xml version='1.0' encoding='uTf-8'?>" + _qt_document(
        language="sr_Latn_RS", translation="Zdravo"
    )

    detector = _detector_module()
    result = detector.detect_qt_ts_layouts(
        (_source("translations/app_sr-Latn-RS.ts", content),),
        repository_side="keys",
    )

    assert len(result.candidates) == 1
    assert result.candidates[0].languages == ("sr-Latn-RS",)
    assert result.candidates[0].samples[0].translation == "Zdravo"


def test_qt_accepts_real_ts_20_doctype_locations_and_legacy_utf8_attribute() -> None:
    def document(language: str, translation: str) -> bytes:
        return (
            b'<?xml version="1.0" encoding="utf-8"?>\n'
            b"<!DOCTYPE TS>\n"
            + f'<TS version="2.0" language="{language}">'.encode()
            + b"<context><name>MainWindow</name>"
            + b'<message utf8="true"><location filename="../main.cpp" line="12"/>'
            + b"<source>Hello</source>"
            + f'<translation type="unfinished">{translation}</translation>'.encode()
            + b"</message></context><context><name>Secondary</name>"
            + b"<message><source>Hello</source><translation></translation></message>"
            + b"</context></TS>"
        )

    detector = _detector_module()
    result = detector.detect_qt_ts_layouts(
        (
            _source("resources/translationsLangs/maxi_de.ts", document("de_DE", "Hallo")),
            _source("resources/translationsLangs/maxi_en.ts", document("en_US", "Hello")),
        ),
        repository_side="direct",
    )

    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.layout_identity == ("qt-ts:resources/translationsLangs/maxi_{locale}.ts")
    assert candidate.files == (
        "resources/translationsLangs/maxi_de.ts",
        "resources/translationsLangs/maxi_en.ts",
    )
    assert candidate.languages == ("de-DE", "en-US")
    assert candidate.keys == ("Hello",)


def test_qt_preview_accepts_the_same_real_world_metadata_as_the_canonical_parser() -> None:
    content = (
        b'<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE TS>\n'
        b'<TS version="2.1" language="pt_BR"><context><name>MainWindow</name>'
        b'<comment>Window messages</comment><message numerus="yes">'
        b'<location filename="../main.cpp" line="12"/><source>%n file(s)</source>'
        b'<oldsource>%n files</oldsource><extracomment>Shown after import</extracomment>'
        b'<translation type="unfinished"><numerusform>%n arquivo</numerusform>'
        b'<numerusform>%n arquivos</numerusform></translation></message></context></TS>'
    )

    detector = _detector_module()
    result = detector.detect_qt_ts_layouts(
        (_source("translations/language_pt_BR.ts", content),),
        repository_side="direct",
    )

    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.layout_identity == "qt-ts:translations/language_{locale}.ts"
    assert candidate.languages == ("pt-BR",)
    assert candidate.keys == ("%n file(s)",)


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
    assert _candidate_count(_source("translations/app.ts", _qt_document(language=locale))) == 0


@settings(max_examples=50, deadline=None)
@given(st.binary(min_size=0, max_size=256))
def test_qt_arbitrary_bytes_are_always_bounded_and_never_raise(content: bytes) -> None:
    detector = _detector_module()
    result = detector.detect_qt_ts_layouts(
        (_source("translations/app_en.ts", content),),
        repository_side="direct",
    )

    assert isinstance(result.candidates, tuple)


@pytest.mark.parametrize(
    "content",
    (
        b"<?xml broken?><TS version='2.1' language='en'/>",
        b"<Other version='2.1' language='en'><context/></Other>",
        b"<TS version='2.1' language='en' extra='x'><context/></TS>",
        (
            b"<TS version='2.1' language='en'><context extra='x'><name>Main</name>"
            b"<message><source>Hello</source><translation>Hello</translation></message>"
            b"</context></TS>"
        ),
        (
            b"<TS version='2.1' language='en'><context>text<name>Main</name>"
            b"<message><source>Hello</source><translation>Hello</translation></message>"
            b"</context></TS>"
        ),
        (
            b"<TS version='2.1' language='en'><context><source>Main</source>"
            b"<message><source>Hello</source><translation>Hello</translation></message>"
            b"</context></TS>"
        ),
        (
            b"<TS version='2.1' language='en'><context><name>Main</name>"
            b"<message>text<source>Hello</source><translation>Hello</translation></message>"
            b"</context></TS>"
        ),
        (
            b"<TS version='2.1' language='en'><context><name>Main</name>"
            b"<message><translation>Hello</translation><source>Hello</source></message>"
            b"</context></TS>"
        ),
        (
            b"<TS version='2.1' language='en'><context><name>Main</name>"
            b"<message><source></source><translation>Hello</translation></message>"
            b"</context></TS>"
        ),
        (
            b"<TS version='2.1' language='en'><other><name>Main</name>"
            b"<message><source>Hello</source><translation>Hello</translation></message>"
            b"</other></TS>"
        ),
    ),
)
def test_qt_rejects_every_structural_escape_from_the_minimal_tree(content: bytes) -> None:
    assert _candidate_count(_source("translations/app_en.ts", content)) == 0


def test_qt_duplicate_canonical_language_is_deferred_but_invalid_peer_blocks_layout() -> None:
    detector = _detector_module()
    duplicate_language = detector.detect_qt_ts_layouts(
        (
            _source("translations/product_en.ts", _qt_document(language="en")),
            _source("translations/product_EN.ts", _qt_document(language="EN")),
        ),
        repository_side="direct",
    )
    invalid_peer = detector.detect_qt_ts_layouts(
        (
            _source("translations/product_en.ts", _qt_document(language="en")),
            _source("translations/product_it.ts", b"<TS"),
        ),
        repository_side="direct",
    )

    assert len(duplicate_language.candidates) == 1
    assert duplicate_language.candidates[0].languages == ("en",)
    assert duplicate_language.candidates[0].files == (
        "translations/product_EN.ts",
        "translations/product_en.ts",
    )
    assert invalid_peer.candidates == ()


def test_qt_collection_limits_remain_bounded_without_a_language_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    detector = _detector_module()
    budget = detector.SOURCE_DISCOVERY_BUDGET
    monkeypatch.setattr(
        detector,
        "SOURCE_DISCOVERY_BUDGET",
        type(budget)(
            max_pages=budget.max_pages,
            max_entries=budget.max_entries,
            max_depth=budget.max_depth,
            max_candidate_files=budget.max_candidate_files,
            max_file_bytes=200,
            max_total_bytes=250,
        ),
    )
    one = _source("translations/product_en.ts", _qt_document(language="en"))
    oversized = _source("translations/product_it.ts", b" " * 201)

    assert detector.detect_qt_ts_layouts((one, one), repository_side="direct").candidates == ()
    assert (
        detector.detect_qt_ts_layouts((one, oversized), repository_side="direct").candidates == ()
    )
    assert (
        detector.detect_qt_ts_layouts(
            (_source("translations/ambiguous.ts", b" " * 201),),
            repository_side="direct",
        ).candidates
        == ()
    )

    monkeypatch.setattr(detector, "SOURCE_DISCOVERY_BUDGET", budget)
    locales = [f"{first}{second}" for first in "abcdef" for second in "ghijkl"][:33]
    files = tuple(
        _source(
            f"translations/app_{locale}.ts",
            _qt_document(language=locale),
        )
        for locale in locales
    )
    result = detector.detect_qt_ts_layouts(files, repository_side="direct")
    assert len(result.candidates) == 1
    assert result.candidates[0].languages == tuple(sorted(locales))
