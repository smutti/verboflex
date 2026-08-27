"""Immutable, bounded contracts shared by read-only preview detectors."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Literal, cast
from uuid import NAMESPACE_URL, UUID, uuid5

RepositorySide = Literal["direct", "keys", "translations"]
PreviewFormat = Literal["android_xml", "qt_ts", "json", "ios_strings"]

MAX_PREVIEW_LANGUAGES = 32
MAX_SAMPLES_PER_LANGUAGE = 10
MAX_TOTAL_SAMPLES = 100
MAX_LAYOUT_FILES = 500
LAYOUT_CANDIDATE_VERSION = 1

_CANDIDATE_FIELDS = {
    "id",
    "version",
    "repository_side",
    "format",
    "layout_identity",
    "confidence",
    "files",
    "languages",
    "keys",
    "samples",
    "samples_are_partial",
}
_SAMPLE_FIELDS = {"language", "key", "translation"}
_REPOSITORY_SIDES = {"direct", "keys", "translations"}
_FORMATS = {"android_xml", "qt_ts", "json", "ios_strings"}
_PREVIEW_LOCALE = re.compile(
    r"\A(?P<language>[A-Za-z]{2,3})"
    r"(?:[-_](?P<script>[A-Za-z]{4}))?"
    r"(?:[-_](?P<region>[A-Za-z]{2}|[0-9]{3}))?\Z",
    re.ASCII,
)


@dataclass(frozen=True, slots=True)
class PreviewSample:
    """One deterministic partial sample, never a canonical translation row."""

    language: str
    key: str
    translation: str

    def to_mapping(self) -> dict[str, str]:
        return {
            "language": self.language,
            "key": self.key,
            "translation": self.translation,
        }


@dataclass(frozen=True, slots=True)
class PreviewLayoutCandidate:
    """One exact format/repository-side/path convention at confidence 1.0."""

    id: UUID
    version: int
    repository_side: RepositorySide
    format: PreviewFormat
    layout_identity: str
    confidence: float
    files: tuple[str, ...]
    languages: tuple[str, ...]
    keys: tuple[str, ...]
    samples: tuple[PreviewSample, ...]
    samples_are_partial: bool

    def to_mapping(self) -> dict[str, object]:
        return {
            "id": str(self.id),
            "version": self.version,
            "repository_side": self.repository_side,
            "format": self.format,
            "layout_identity": self.layout_identity,
            "confidence": self.confidence,
            "files": list(self.files),
            "languages": list(self.languages),
            "keys": list(self.keys),
            "samples": [sample.to_mapping() for sample in self.samples],
            "samples_are_partial": self.samples_are_partial,
        }


@dataclass(frozen=True, slots=True)
class PreviewDetectionResult:
    """A deterministic set of separate exact layout candidates."""

    candidates: tuple[PreviewLayoutCandidate, ...]

    def to_mappings(self) -> list[dict[str, object]]:
        return [candidate.to_mapping() for candidate in self.candidates]


@dataclass(frozen=True, slots=True)
class _CandidateHeader:
    id: UUID
    version: int
    repository_side: RepositorySide
    format: PreviewFormat
    layout_identity: str
    confidence: float


def normalize_preview_locale(raw: str) -> str | None:
    """Canonicalize only the deliberately bounded Phase 2 locale subset."""
    if not isinstance(raw, str):
        return None
    match = _PREVIEW_LOCALE.fullmatch(raw)
    if match is None:
        return None
    parts = [match.group("language").lower()]
    script = match.group("script")
    region = match.group("region")
    if script is not None:
        parts.append(script.title())
    if region is not None:
        parts.append(region.upper())
    return "-".join(parts)


def _preview_path_parts(path: str, *, suffix: str) -> tuple[list[str], str] | None:
    if not path or not suffix or not path.endswith(suffix) or path.startswith("/") or "//" in path:
        return None
    components = path.split("/")
    if any(not component or component in {".", ".."} for component in components):
        return None
    return components, components[-1][: -len(suffix)]


def _stem_locale_signals(
    stem: str,
    *,
    suffix: str,
    allow_prefixed_stem: bool,
) -> list[tuple[str, str]]:
    signals: list[tuple[str, str]] = []
    stem_locale = normalize_preview_locale(stem)
    if stem_locale is not None:
        signals.append((stem_locale, f"{{locale}}{suffix}"))
    if not allow_prefixed_stem:
        return signals
    for offset, character in enumerate(stem):
        if character not in {"-", "_"}:
            continue
        possible = normalize_preview_locale(stem[offset + 1 :])
        if possible is not None:
            signals.append((possible, f"{stem[: offset + 1]}{{locale}}{suffix}"))
    return signals


def _select_stem_signal(
    signals: list[tuple[str, str]],
    *,
    expected_locale: str | None,
) -> tuple[str, str] | None:
    matching = (
        [signal for signal in signals if signal[0] == expected_locale]
        if expected_locale is not None
        else signals
    )
    if not matching or len({locale for locale, _ in matching}) != 1:
        return None
    return matching[0]


def _directory_locale_signals(components: list[str]) -> list[tuple[int, str, str]]:
    signals: list[tuple[int, str, str]] = []
    for index, component in enumerate(components[:-1]):
        locale = normalize_preview_locale(component)
        if locale is not None:
            signals.append((index, locale, "{locale}"))
    return signals


def _path_locale_signals(
    components: list[str],
    stem: str,
    *,
    suffix: str,
    allow_prefixed_stem: bool,
    expected_locale: str | None,
) -> list[tuple[int, str, str]] | None:
    signals = _directory_locale_signals(components)
    directory_locales = {locale for _, locale, _ in signals}
    if expected_locale is not None and directory_locales and directory_locales != {expected_locale}:
        return None
    stem_signal = _select_stem_signal(
        _stem_locale_signals(
            stem,
            suffix=suffix,
            allow_prefixed_stem=allow_prefixed_stem,
        ),
        expected_locale=expected_locale,
    )
    if stem_signal is not None:
        signals.append((len(components) - 1, stem_signal[0], stem_signal[1]))
    return signals


def _render_locale_template(
    components: list[str],
    signals: list[tuple[int, str, str]],
    *,
    expected_locale: str | None,
) -> tuple[str, str] | None:
    locales = {locale for _, locale, _ in signals}
    if not signals or len(locales) != 1:
        return None
    locale = signals[0][1]
    if expected_locale is not None and locale != expected_locale:
        return None
    templated = list(components)
    for index, _, replacement in signals:
        templated[index] = replacement
    return locale, "/".join(templated)


def extract_preview_locale_path(
    path: str,
    *,
    suffix: str,
    allow_prefixed_stem: bool = False,
    expected_locale: str | None = None,
) -> tuple[str, str] | None:
    """Return one unambiguous locale and its exact path template."""
    path_parts = _preview_path_parts(path, suffix=suffix)
    if path_parts is None:
        return None
    components, stem = path_parts
    signals = _path_locale_signals(
        components,
        stem,
        suffix=suffix,
        allow_prefixed_stem=allow_prefixed_stem,
        expected_locale=expected_locale,
    )
    if signals is None:
        return None
    return _render_locale_template(
        components,
        signals,
        expected_locale=expected_locale,
    )


def _candidate_id(
    *,
    repository_side: RepositorySide,
    format: PreviewFormat,
    layout_identity: str,
    version: int,
) -> UUID:
    identity = json.dumps(
        {
            "format": format,
            "layout_identity": layout_identity,
            "repository_side": repository_side,
            "version": version,
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return uuid5(NAMESPACE_URL, f"verboflex-preview-layout:{identity}")


def build_layout_candidate(
    *,
    repository_side: RepositorySide,
    format: PreviewFormat,
    layout_identity: str,
    files: Iterable[str],
    values: Mapping[str, Mapping[str, str]],
) -> PreviewLayoutCandidate:
    """Build one bounded candidate from already validated decoded values."""
    received_files = tuple(files)
    ordered_files = tuple(sorted(received_files))
    ordered_languages = tuple(sorted(values))
    _require_candidate(bool(layout_identity))
    _require_candidate(bool(ordered_files))
    _require_candidate(len(set(ordered_files)) == len(ordered_files))
    _require_candidate(len(ordered_files) <= MAX_LAYOUT_FILES)
    _require_candidate(bool(ordered_languages))
    _require_candidate(len(ordered_languages) <= MAX_PREVIEW_LANGUAGES)
    samples = _build_samples(values=values, ordered_languages=ordered_languages)
    keys = tuple(sorted({sample.key for sample in samples}))
    return PreviewLayoutCandidate(
        id=_candidate_id(
            repository_side=repository_side,
            format=format,
            layout_identity=layout_identity,
            version=LAYOUT_CANDIDATE_VERSION,
        ),
        version=LAYOUT_CANDIDATE_VERSION,
        repository_side=repository_side,
        format=format,
        layout_identity=layout_identity,
        confidence=1.0,
        files=ordered_files,
        languages=ordered_languages,
        keys=keys,
        samples=samples,
        samples_are_partial=True,
    )


def _build_samples(
    *,
    values: Mapping[str, Mapping[str, str]],
    ordered_languages: tuple[str, ...],
) -> tuple[PreviewSample, ...]:
    samples: list[PreviewSample] = []
    for language in ordered_languages:
        translations = values[language]
        _require_candidate(bool(translations))
        for key in sorted(translations)[:MAX_SAMPLES_PER_LANGUAGE]:
            if len(samples) == MAX_TOTAL_SAMPLES:
                return tuple(samples)
            translation = translations[key]
            _require_candidate(isinstance(translation, str) and "\x00" not in translation)
            samples.append(PreviewSample(language=language, key=key, translation=translation))
    _require_candidate(bool(samples))
    return tuple(samples)


def _required_string(value: object, *, max_length: int = 1_048_576) -> str:
    if not isinstance(value, str) or not value or len(value) > max_length or "\x00" in value:
        raise ValueError("preview candidate rejected")
    return value


def _require_candidate(condition: bool) -> None:
    if not condition:
        raise ValueError("preview candidate rejected")


def _candidate_header(raw: Mapping[object, object]) -> _CandidateHeader:
    repository_side = raw["repository_side"]
    format_name = raw["format"]
    _require_candidate(repository_side in _REPOSITORY_SIDES)
    _require_candidate(format_name in _FORMATS)
    version_raw = raw["version"]
    _require_candidate(isinstance(version_raw, int) and not isinstance(version_raw, bool))
    version = cast(int, version_raw)
    _require_candidate(version == LAYOUT_CANDIDATE_VERSION)
    layout_identity = _required_string(raw["layout_identity"], max_length=4096)
    try:
        candidate_id = UUID(_required_string(raw["id"], max_length=36))
    except ValueError as error:
        raise ValueError("preview candidate rejected") from error
    confidence_raw = raw["confidence"]
    _require_candidate(isinstance(confidence_raw, int | float))
    confidence = cast(int | float, confidence_raw)
    _require_candidate(not isinstance(confidence, bool) and confidence == 1.0)
    return _CandidateHeader(
        id=candidate_id,
        version=version,
        repository_side=cast(RepositorySide, repository_side),
        format=cast(PreviewFormat, format_name),
        layout_identity=layout_identity,
        confidence=float(confidence),
    )


def _ordered_unique_strings(
    raw: object,
    *,
    max_count: int,
    max_length: int,
) -> tuple[str, ...]:
    _require_candidate(isinstance(raw, list))
    items = cast(list[object], raw)
    values = tuple(_required_string(value, max_length=max_length) for value in items)
    _require_candidate(bool(values))
    _require_candidate(len(values) <= max_count)
    _require_candidate(values == tuple(sorted(set(values))))
    return values


def _sample_from_mapping(raw: object) -> PreviewSample:
    _require_candidate(isinstance(raw, Mapping))
    mapping = cast(Mapping[object, object], raw)
    _require_candidate(set(mapping) == _SAMPLE_FIELDS)
    translation = mapping["translation"]
    _require_candidate(isinstance(translation, str) and "\x00" not in translation)
    return PreviewSample(
        language=_required_string(mapping["language"], max_length=64),
        key=_required_string(mapping["key"]),
        translation=cast(str, translation),
    )


def _validated_samples(raw: object) -> tuple[PreviewSample, ...]:
    _require_candidate(isinstance(raw, list))
    items = cast(list[object], raw)
    _require_candidate(bool(items))
    _require_candidate(len(items) <= MAX_TOTAL_SAMPLES)
    samples = tuple(_sample_from_mapping(item) for item in items)
    per_language: dict[str, int] = {}
    for sample in samples:
        per_language[sample.language] = per_language.get(sample.language, 0) + 1
        _require_candidate(per_language[sample.language] <= MAX_SAMPLES_PER_LANGUAGE)
    pairs = tuple((sample.language, sample.key) for sample in samples)
    _require_candidate(pairs == tuple(sorted(set(pairs))))
    return samples


def _validate_candidate_links(
    *,
    header: _CandidateHeader,
    files: tuple[str, ...],
    languages: tuple[str, ...],
    keys: tuple[str, ...],
    samples: tuple[PreviewSample, ...],
    samples_are_partial: object,
) -> None:
    del files
    _require_candidate({sample.language for sample in samples}.issubset(set(languages)))
    _require_candidate(set(keys) == {sample.key for sample in samples})
    _require_candidate(samples_are_partial is True)
    _require_candidate(
        header.id
        == _candidate_id(
            repository_side=header.repository_side,
            format=header.format,
            layout_identity=header.layout_identity,
            version=header.version,
        )
    )


def layout_candidate_from_mapping(raw: object) -> PreviewLayoutCandidate:
    """Validate an untrusted worker candidate before durable persistence."""
    if not isinstance(raw, Mapping) or set(raw) != _CANDIDATE_FIELDS:
        raise ValueError("preview candidate rejected")
    header = _candidate_header(raw)
    files = _ordered_unique_strings(raw["files"], max_count=MAX_LAYOUT_FILES, max_length=4096)
    languages = _ordered_unique_strings(
        raw["languages"], max_count=MAX_PREVIEW_LANGUAGES, max_length=64
    )
    keys = _ordered_unique_strings(raw["keys"], max_count=MAX_TOTAL_SAMPLES, max_length=1_048_576)
    samples = _validated_samples(raw["samples"])
    _validate_candidate_links(
        header=header,
        files=files,
        languages=languages,
        keys=keys,
        samples=samples,
        samples_are_partial=raw["samples_are_partial"],
    )
    return PreviewLayoutCandidate(
        id=header.id,
        version=header.version,
        repository_side=header.repository_side,
        format=header.format,
        layout_identity=header.layout_identity,
        confidence=header.confidence,
        files=files,
        languages=languages,
        keys=keys,
        samples=samples,
        samples_are_partial=True,
    )


def validate_layout_candidate_mappings(raw_candidates: object) -> list[dict[str, object]]:
    """Close and canonicalize the complete worker candidate list."""
    if not isinstance(raw_candidates, list):
        raise ValueError("preview result rejected")
    candidates = tuple(layout_candidate_from_mapping(raw) for raw in raw_candidates)
    if candidates != tuple(
        sorted(
            candidates,
            key=lambda candidate: (
                candidate.repository_side,
                candidate.format,
                candidate.layout_identity,
                str(candidate.id),
            ),
        )
    ):
        raise ValueError("preview result rejected")
    return [candidate.to_mapping() for candidate in candidates]
