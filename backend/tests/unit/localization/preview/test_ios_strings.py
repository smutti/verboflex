"""Evidence-first contracts for the bounded iOS strings preview lexer."""

from __future__ import annotations

import importlib

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from verboflex.services.repository_discovery import RepositorySourceFile


def _module() -> object:
    return importlib.import_module("verboflex.localization.preview.ios_strings")


def _source(path: str, content: bytes) -> RepositorySourceFile:
    return RepositorySourceFile(path=path, content=content)


def _candidate_count(content: bytes, *, path: str = "Base/en.lproj/Localizable.strings") -> int:
    detector = _module()
    return len(
        detector.detect_ios_strings_layouts(
            (_source(path, content),),
            repository_side="direct",
        ).candidates
    )


@pytest.mark.parametrize(
    "content",
    (
        b'"welcome.title" = "Welcome";\n"button.ok" = "OK";',
        b'\xef\xbb\xbf/* heading */\n"welcome.title"/* key */=// join\n"Welcome";',
        b'"quote" = "Say \\"hello\\"";\n"line" = "one\\ntwo\\t\\\\";',
        b'"accent" = "caf\\U00E9";',
        b'"emoji" = "\\UD83D\\UDE00";',
        b'"hello"="Hello"; // valid comment at end of file',
        b"\xff\xfe" + '"welcome.title" = "Benvenuto";'.encode("utf-16-le"),
        b"\xfe\xff" + '"welcome.title" = "Benvenuto";'.encode("utf-16-be"),
    ),
    ids=(
        "utf8",
        "utf8-bom-comments",
        "documented-escapes",
        "unicode-escape",
        "unicode-surrogate-pair",
        "line-comment-at-eof",
        "utf16-le-bom",
        "utf16-be-bom",
    ),
)
def test_ios_accepts_only_documented_minimal_strings_grammar(content: bytes) -> None:
    assert _candidate_count(content) == 1


def test_ios_returns_exact_candidate_samples_and_source_spans() -> None:
    detector = _module()
    content = b'/* comment */ "welcome\\U002Etitle" = "Benvenuto";'

    entries = detector.parse_ios_strings(content)
    result = detector.detect_ios_strings_layouts(
        (_source("mobile/it_IT.lproj/Localizable.strings", content),),
        repository_side="translations",
    )

    assert len(entries) == 1
    entry = entries[0]
    assert entry.key == "welcome.title"
    assert entry.value == "Benvenuto"
    assert entry.key_span.start < entry.key_span.end <= entry.value_span.start
    assert entry.value_span.end <= entry.entry_span.end
    assert entry.entry_span.start == entry.key_span.start
    candidate = result.candidates[0]
    assert candidate.version == 1
    assert candidate.format == "ios_strings"
    assert candidate.repository_side == "translations"
    assert candidate.layout_identity == "ios-strings:mobile/{locale}.lproj/Localizable.strings"
    assert candidate.confidence == 1.0
    assert candidate.files == ("mobile/it_IT.lproj/Localizable.strings",)
    assert candidate.languages == ("it-IT",)
    assert candidate.keys == ("welcome.title",)
    assert tuple(
        (sample.language, sample.key, sample.translation) for sample in candidate.samples
    ) == (("it-IT", "welcome.title", "Benvenuto"),)
    assert not hasattr(detector, "serialize_ios_strings")
    assert not hasattr(entry, "to_source")


def test_ios_groups_languages_by_one_exact_lproj_path_layout() -> None:
    detector = _module()
    result = detector.detect_ios_strings_layouts(
        (
            _source("mobile/it.lproj/Errors.strings", b'"offline"="Non disponibile";'),
            _source("mobile/en.lproj/Errors.strings", b'"offline"="Unavailable";'),
            _source("mobile/en.lproj/Localizable.strings", b'"hello"="Hello";'),
        ),
        repository_side="direct",
    )

    assert len(result.candidates) == 2
    assert tuple(candidate.layout_identity for candidate in result.candidates) == (
        "ios-strings:mobile/{locale}.lproj/Errors.strings",
        "ios-strings:mobile/{locale}.lproj/Localizable.strings",
    )
    assert result.candidates[0].languages == ("en", "it")


@pytest.mark.parametrize(
    "content",
    (
        '"hello"="Hello";'.encode("utf-16-le"),
        '"hello"="Hello";'.encode("utf-16-be"),
        b"\xff\xfe\x00\x00" + '"hello"="Hello";'.encode("utf-32-le"),
        b"\x00\x00\xfe\xff" + '"hello"="Hello";'.encode("utf-32-be"),
        b'\xff"hello"="Hello";',
        b'"hello"="Hel\xfflo";',
        b'"hello"="Hel\x00lo";',
        b"",
    ),
    ids=(
        "bomless-utf16-le",
        "bomless-utf16-be",
        "utf32-le",
        "utf32-be",
        "invalid-utf8-prefix",
        "invalid-utf8-body",
        "embedded-nul",
        "empty",
    ),
)
def test_ios_rejects_unsupported_or_malformed_encodings(content: bytes) -> None:
    assert _candidate_count(content) == 0


@pytest.mark.parametrize(
    "content",
    (
        b'"hello"="Hello"',
        b'"hello"="Hello"; trailing',
        b'"hello"="Hello"; /* unterminated',
        b'"hello"="bad\\q";',
        b'"hello"="bad\\U12X4";',
        b'"hello"="bad\\U123";',
        b'"hello"="bad\\UD83D";',
        b'"hello"="bad\\UDE00";',
        b'"hello"="line\nfeed";',
        b'"hello"="Hello"; "hello"="Again";',
        b'"welc\\U006Fme"="One"; "welcome"="Two";',
        b'#define HELLO "Hello"\n"hello"="Hello";',
        b'"plural" = {"one" = "One";};',
        b'hello = "Hello";',
        b'"hello" = Hello;',
        b'"" = "blank";',
        b"/* comments only */",
    ),
    ids=(
        "missing-semicolon",
        "trailing-token",
        "unterminated-block-comment",
        "unknown-escape",
        "invalid-unicode-hex",
        "short-unicode-escape",
        "isolated-high-surrogate",
        "isolated-low-surrogate",
        "literal-newline",
        "duplicate-key",
        "duplicate-decoded-key",
        "preprocessor",
        "plural-dictionary",
        "unquoted-key",
        "unquoted-value",
        "empty-key",
        "empty-document",
    ),
)
def test_ios_unsupported_or_ambiguous_grammar_never_confirms(content: bytes) -> None:
    assert _candidate_count(content) == 0


@pytest.mark.parametrize(
    "path",
    (
        "Localizable.strings",
        "mobile/engl.lproj/Localizable.strings",
        "mobile/en-US-POSIX.lproj/Localizable.strings",
        "mobile/en.lproj/it.lproj/Localizable.strings",
        "/mobile/en.lproj/Localizable.strings",
        "mobile/../en.lproj/Localizable.strings",
    ),
)
def test_ios_requires_one_unambiguous_bounded_lproj_locale(path: str) -> None:
    assert _candidate_count(b'"hello"="Hello";', path=path) == 0


def test_ios_invalid_file_blocks_the_complete_matching_layout() -> None:
    detector = _module()
    result = detector.detect_ios_strings_layouts(
        (
            _source("mobile/en.lproj/Localizable.strings", b'"hello"="Hello";'),
            _source("mobile/it.lproj/Localizable.strings", b'"hello"="Ciao"'),
        ),
        repository_side="direct",
    )

    assert result.candidates == ()


@settings(max_examples=75, deadline=None)
@given(st.binary(min_size=0, max_size=512))
def test_ios_arbitrary_bytes_are_bounded_and_never_raise(content: bytes) -> None:
    detector = _module()
    result = detector.detect_ios_strings_layouts(
        (_source("mobile/en.lproj/Localizable.strings", content),),
        repository_side="direct",
    )

    assert isinstance(result.candidates, tuple)


@pytest.mark.parametrize(
    "content",
    (
        b'"hello"="Hello"; /',
        b'"unterminated',
        b'"hello"="unterminated\\',
        b'"hello"="bad\\UD83D\\U0041";',
    ),
)
def test_ios_rejects_lone_comment_markers_and_unterminated_lexer_states(content: bytes) -> None:
    assert _candidate_count(content) == 0


def test_ios_duplicate_language_and_collection_limits_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    detector = _module()
    one = _source("mobile/en.lproj/Localizable.strings", b'"hello"="Hello";')
    canonical_duplicate = _source("mobile/EN.lproj/Localizable.strings", b'"hello"="Again";')
    assert (
        detector.detect_ios_strings_layouts(
            (one, canonical_duplicate), repository_side="direct"
        ).candidates
        == ()
    )
    assert (
        detector.detect_ios_strings_layouts((one, one), repository_side="direct").candidates == ()
    )

    budget = detector.SOURCE_DISCOVERY_BUDGET
    monkeypatch.setattr(
        detector,
        "SOURCE_DISCOVERY_BUDGET",
        type(budget)(
            max_pages=budget.max_pages,
            max_entries=budget.max_entries,
            max_depth=budget.max_depth,
            max_candidate_files=budget.max_candidate_files,
            max_file_bytes=25,
            max_total_bytes=30,
        ),
    )
    oversized = _source("mobile/it.lproj/Localizable.strings", b" " * 26)
    assert (
        detector.detect_ios_strings_layouts((one, oversized), repository_side="direct").candidates
        == ()
    )
    assert (
        detector.detect_ios_strings_layouts(
            (_source("Localizable.strings", b" " * 26),),
            repository_side="direct",
        ).candidates
        == ()
    )

    monkeypatch.setattr(detector, "SOURCE_DISCOVERY_BUDGET", budget)
    locales = [f"{first}{second}" for first in "abcdef" for second in "ghijkl"][:33]
    files = tuple(
        _source(f"mobile/{locale}.lproj/Localizable.strings", b'"hello"="Hello";')
        for locale in locales
    )
    assert detector.detect_ios_strings_layouts(files, repository_side="direct").candidates == ()
