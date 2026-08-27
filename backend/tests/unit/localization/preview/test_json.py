"""Evidence-first contracts for strict duplicate-aware JSON preview detection."""

from __future__ import annotations

import importlib

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from verboflex.services.repository_discovery import RepositorySourceFile


def _detector_module() -> object:
    return importlib.import_module("verboflex.localization.preview.json")


def _registry_module() -> object:
    return importlib.import_module("verboflex.localization.preview.registry")


def _core_module() -> object:
    return importlib.import_module("verboflex.localization.preview.core")


def _source(path: str, content: bytes) -> RepositorySourceFile:
    return RepositorySourceFile(path=path, content=content)


def _candidate_count(path: str, content: bytes) -> int:
    detector = _detector_module()
    return len(
        detector.detect_json_layouts(
            (_source(path, content),),
            repository_side="direct",
        ).candidates
    )


def test_json_flat_per_locale_files_form_one_exact_deterministic_candidate() -> None:
    detector = _detector_module()
    files = (
        _source(
            "locales/it-IT.json",
            b'\xef\xbb\xbf{"welcome.title":"Benvenuto","button.ok":"Va bene"}',
        ),
        _source(
            "locales/en.json",
            b'{"button.ok":"OK","welcome.title":"Welcome"}',
        ),
    )

    result = detector.detect_json_layouts(files, repository_side="translations")

    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.version == 1
    assert candidate.format == "json"
    assert candidate.repository_side == "translations"
    assert candidate.confidence == 1.0
    assert candidate.files == ("locales/en.json", "locales/it-IT.json")
    assert candidate.languages == ("en", "it-IT")
    assert candidate.keys == ("button.ok", "welcome.title")
    assert tuple(
        (sample.language, sample.key, sample.translation) for sample in candidate.samples
    ) == (
        ("en", "button.ok", "OK"),
        ("en", "welcome.title", "Welcome"),
        ("it-IT", "button.ok", "Va bene"),
        ("it-IT", "welcome.title", "Benvenuto"),
    )


def test_json_locale_directory_files_form_an_independent_exact_candidate() -> None:
    detector = _detector_module()
    result = detector.detect_json_layouts(
        (
            _source("assets/en/messages.json", b'{"hello":"Hello"}'),
            _source("assets/it/messages.json", b'{"hello":"Ciao"}'),
        ),
        repository_side="direct",
    )

    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.files == ("assets/en/messages.json", "assets/it/messages.json")
    assert candidate.languages == ("en", "it")
    assert tuple(sample.translation for sample in candidate.samples) == ("Hello", "Ciao")


def test_json_locale_rooted_map_forms_one_separate_candidate() -> None:
    detector = _detector_module()
    content = (
        b'{"it_IT":{"welcome.title":"Benvenuto"},"en":{"welcome.title":"Welcome","button.ok":"OK"}}'
    )

    result = detector.detect_json_layouts(
        (_source("locales.json", content),),
        repository_side="keys",
    )

    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.repository_side == "keys"
    assert candidate.languages == ("en", "it-IT")
    assert candidate.keys == ("button.ok", "welcome.title")
    assert candidate.files == ("locales.json",)


def test_registry_keeps_flat_and_locale_rooted_interpretations_separate() -> None:
    registry = _registry_module()
    result = registry.detect_preview_layouts(
        (
            _source("locales/en.json", b'{"hello":"Hello"}'),
            _source("catalog.json", b'{"en":{"hello":"Hello"}}'),
        ),
        repository_side="direct",
    )

    json_candidates = tuple(
        candidate for candidate in result.candidates if candidate.format == "json"
    )
    assert len(json_candidates) == 2
    assert len({candidate.layout_identity for candidate in json_candidates}) == 2
    assert {candidate.files for candidate in json_candidates} == {
        ("locales/en.json",),
        ("catalog.json",),
    }


@pytest.mark.parametrize(
    ("raw", "canonical"),
    (
        ("en", "en"),
        ("ENG", "eng"),
        ("sr_Latn", "sr-Latn"),
        ("SR-lATN-rs", "sr-Latn-RS"),
        ("es_419", "es-419"),
    ),
)
def test_locale_recognizer_accepts_only_the_bounded_subset(raw: str, canonical: str) -> None:
    core = _core_module()
    assert core.normalize_preview_locale(raw) == canonical


@pytest.mark.parametrize(
    "raw",
    (
        "e",
        "engl",
        "en-US-POSIX",
        "en-u-ca-gregory",
        "en-x-private",
        "12",
        "en-1",
        "en--US",
        "en/US",
        "\u00e9n",
        "",
    ),
)
def test_locale_recognizer_rejects_variants_extensions_and_non_ascii(raw: str) -> None:
    core = _core_module()
    assert core.normalize_preview_locale(raw) is None


@pytest.mark.parametrize(
    ("path", "content"),
    (
        ("en.json", b'{"hello":"one","hello":"two"}'),
        ("root.json", b'{"en":{"hello":"one","hello":"two"}}'),
        ("root.json", b'{"en-US":{"hello":"one"},"en_US":{"hello":"two"}}'),
        ("root.json", b'{"en":{},"it":{"hello":"ciao"}}'),
        ("root.json", b'{"en":{"":"blank"}}'),
    ),
    ids=(
        "duplicate-flat-name",
        "duplicate-nested-name",
        "duplicate-canonical-locale",
        "empty-locale-object",
        "blank-key",
    ),
)
def test_json_duplicate_or_empty_semantic_identities_never_confirm(
    path: str, content: bytes
) -> None:
    assert _candidate_count(path, content) == 0


@pytest.mark.parametrize(
    "content",
    (
        b"{}",
        b"[]",
        b'"value"',
        b"42",
        b"true",
        b"null",
        b'{"hello":null}',
        b'{"hello":false}',
        b'{"hello":1}',
        b'{"hello":[]}',
        b'{"hello":{"nested":"value"}}',
        b'{"en":{"hello":"Hello"},"metadata":"mixed"}',
        b'{"en":{"hello":{"nested":"value"}}}',
        b'{"hello":NaN}',
        b'{"hello":Infinity}',
        b'{"hello":-Infinity}',
        b'{"":"blank"}',
        b'{"hello":"ok"',
    ),
    ids=(
        "empty-object",
        "array",
        "string-scalar",
        "number-scalar",
        "boolean-scalar",
        "null-scalar",
        "null-value",
        "boolean-value",
        "number-value",
        "array-value",
        "nested-flat",
        "mixed-root",
        "nested-rooted",
        "nan",
        "positive-infinity",
        "negative-infinity",
        "blank-key",
        "malformed",
    ),
)
def test_json_unsupported_shapes_never_confirm(content: bytes) -> None:
    assert _candidate_count("en.json", content) == 0


@pytest.mark.parametrize(
    "content",
    (
        '{"hello":"Hello"}'.encode("utf-16"),
        '{"hello":"Hello"}'.encode("utf-32"),
        b'\xff{"hello":"Hello"}',
        b'{"hello":"Hel\xfflo"}',
        b'{"hello":"Hel\x00lo"}',
        b"",
    ),
    ids=("utf-16", "utf-32", "invalid-prefix", "invalid-body", "nul", "empty"),
)
def test_json_invalid_encodings_never_confirm(content: bytes) -> None:
    assert _candidate_count("en.json", content) == 0


@pytest.mark.parametrize(
    "path",
    (
        "messages.json",
        "en/it/messages.json",
        "en/fr.json",
        "en-US-POSIX.json",
        "en-u-ca-gregory/messages.json",
    ),
)
def test_json_flat_maps_with_missing_or_ambiguous_path_locale_never_confirm(path: str) -> None:
    assert _candidate_count(path, b'{"hello":"Hello"}') == 0


def test_json_file_order_does_not_change_candidate_identity_or_output() -> None:
    detector = _detector_module()
    files = (
        _source("locales/it.json", b'{"hello":"Ciao"}'),
        _source("locales/en.json", b'{"hello":"Hello"}'),
    )

    forward = detector.detect_json_layouts(files, repository_side="direct")
    reverse = detector.detect_json_layouts(tuple(reversed(files)), repository_side="direct")

    assert forward == reverse


@settings(max_examples=50, deadline=None)
@given(st.binary(min_size=0, max_size=256))
def test_json_invalid_utf8_prefixes_are_always_bounded_and_never_raise(content: bytes) -> None:
    detector = _detector_module()
    result = detector.detect_json_layouts(
        (_source("en.json", b"\xff" + content),),
        repository_side="direct",
    )

    assert result.candidates == ()


def test_locale_and_path_helpers_reject_non_strings_and_unsafe_or_conflicting_paths() -> None:
    core = _core_module()

    assert core.normalize_preview_locale(42) is None
    for path in ("", "/en.json", "en//messages.json", "en/../messages.json", "en.txt"):
        assert core.extract_preview_locale_path(path, suffix=".json") is None
    assert (
        core.extract_preview_locale_path(
            "en/app_it.ts",
            suffix=".ts",
            allow_prefixed_stem=True,
            expected_locale="it",
        )
        is None
    )


def test_json_duplicate_language_invalid_peer_and_limits_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    detector = _detector_module()
    duplicate_language = detector.detect_json_layouts(
        (
            _source("locales/en.json", b'{"hello":"Hello"}'),
            _source("locales/EN.json", b'{"hello":"Again"}'),
        ),
        repository_side="direct",
    )
    invalid_peer = detector.detect_json_layouts(
        (
            _source("locales/en.json", b'{"hello":"Hello"}'),
            _source("locales/it.json", b"{"),
        ),
        repository_side="direct",
    )
    assert duplicate_language.candidates == ()
    assert invalid_peer.candidates == ()

    budget = detector.SOURCE_DISCOVERY_BUDGET
    monkeypatch.setattr(
        detector,
        "SOURCE_DISCOVERY_BUDGET",
        type(budget)(
            max_pages=budget.max_pages,
            max_entries=budget.max_entries,
            max_depth=budget.max_depth,
            max_candidate_files=budget.max_candidate_files,
            max_file_bytes=20,
            max_total_bytes=30,
        ),
    )
    one = _source("locales/en.json", b'{"hello":"Hello"}')
    assert detector.detect_json_layouts((one, one), repository_side="direct").candidates == ()
    assert (
        detector.detect_json_layouts(
            (one, _source("locales/it.json", b" " * 21)),
            repository_side="direct",
        ).candidates
        == ()
    )
    assert (
        detector.detect_json_layouts(
            (_source("catalog.json", b" " * 21),),
            repository_side="direct",
        ).candidates
        == ()
    )

    monkeypatch.setattr(detector, "SOURCE_DISCOVERY_BUDGET", budget)
    locales = [f"{first}{second}" for first in "abcdef" for second in "ghijkl"][:33]
    rooted = {locale: {"hello": locale} for locale in locales}
    content = __import__("json").dumps(rooted).encode()
    assert _candidate_count("catalog.json", content) == 0
