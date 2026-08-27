"""Immutable, bounded contracts shared by read-only preview detectors."""

from __future__ import annotations

import json
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
    if (
        not layout_identity
        or not ordered_files
        or len(set(ordered_files)) != len(ordered_files)
        or len(ordered_files) > MAX_LAYOUT_FILES
        or not ordered_languages
        or len(ordered_languages) > MAX_PREVIEW_LANGUAGES
    ):
        raise ValueError("preview candidate rejected")

    samples: list[PreviewSample] = []
    for language in ordered_languages:
        translations = values[language]
        if not translations:
            raise ValueError("preview candidate rejected")
        for key in sorted(translations)[:MAX_SAMPLES_PER_LANGUAGE]:
            if len(samples) == MAX_TOTAL_SAMPLES:
                break
            samples.append(
                PreviewSample(
                    language=language,
                    key=key,
                    translation=translations[key],
                )
            )
        if len(samples) == MAX_TOTAL_SAMPLES:
            break
    if not samples:
        raise ValueError("preview candidate rejected")
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
        samples=tuple(samples),
        samples_are_partial=True,
    )


def _required_string(value: object, *, max_length: int = 1_048_576) -> str:
    if not isinstance(value, str) or not value or len(value) > max_length or "\x00" in value:
        raise ValueError("preview candidate rejected")
    return value


def layout_candidate_from_mapping(raw: object) -> PreviewLayoutCandidate:
    """Validate an untrusted worker candidate before durable persistence."""
    if not isinstance(raw, Mapping) or set(raw) != _CANDIDATE_FIELDS:
        raise ValueError("preview candidate rejected")
    repository_side = raw["repository_side"]
    format_name = raw["format"]
    if repository_side not in _REPOSITORY_SIDES or format_name not in _FORMATS:
        raise ValueError("preview candidate rejected")
    version = raw["version"]
    if not isinstance(version, int) or isinstance(version, bool) or version != 1:
        raise ValueError("preview candidate rejected")
    layout_identity = _required_string(raw["layout_identity"], max_length=4096)
    try:
        candidate_id = UUID(_required_string(raw["id"], max_length=36))
    except ValueError as error:
        raise ValueError("preview candidate rejected") from error
    confidence = raw["confidence"]
    if not isinstance(confidence, int | float) or isinstance(confidence, bool) or confidence != 1.0:
        raise ValueError("preview candidate rejected")

    files_raw = raw["files"]
    languages_raw = raw["languages"]
    keys_raw = raw["keys"]
    samples_raw = raw["samples"]
    if not all(
        isinstance(value, list)
        for value in (files_raw, languages_raw, keys_raw, samples_raw)
    ):
        raise ValueError("preview candidate rejected")
    files = tuple(_required_string(value, max_length=4096) for value in files_raw)
    languages = tuple(_required_string(value, max_length=64) for value in languages_raw)
    keys = tuple(_required_string(value) for value in keys_raw)
    if (
        not files
        or len(files) > MAX_LAYOUT_FILES
        or files != tuple(sorted(set(files)))
        or not languages
        or len(languages) > MAX_PREVIEW_LANGUAGES
        or languages != tuple(sorted(set(languages)))
        or len(keys) > MAX_TOTAL_SAMPLES
        or keys != tuple(sorted(set(keys)))
        or not samples_raw
        or len(samples_raw) > MAX_TOTAL_SAMPLES
    ):
        raise ValueError("preview candidate rejected")
    samples: list[PreviewSample] = []
    per_language: dict[str, int] = {}
    for raw_sample in samples_raw:
        if not isinstance(raw_sample, Mapping) or set(raw_sample) != _SAMPLE_FIELDS:
            raise ValueError("preview candidate rejected")
        translation = raw_sample["translation"]
        if not isinstance(translation, str) or "\x00" in translation:
            raise ValueError("preview candidate rejected")
        sample = PreviewSample(
            language=_required_string(raw_sample["language"], max_length=64),
            key=_required_string(raw_sample["key"]),
            translation=translation,
        )
        per_language[sample.language] = per_language.get(sample.language, 0) + 1
        if per_language[sample.language] > MAX_SAMPLES_PER_LANGUAGE:
            raise ValueError("preview candidate rejected")
        samples.append(sample)
    if (
        tuple((sample.language, sample.key) for sample in samples)
        != tuple(sorted((sample.language, sample.key) for sample in samples))
        or not set(keys).issubset({sample.key for sample in samples})
        or not set(sample.language for sample in samples).issubset(set(languages))
        or raw["samples_are_partial"] is not True
    ):
        raise ValueError("preview candidate rejected")
    expected_id = _candidate_id(
        repository_side=cast(RepositorySide, repository_side),
        format=cast(PreviewFormat, format_name),
        layout_identity=layout_identity,
        version=version,
    )
    if candidate_id != expected_id:
        raise ValueError("preview candidate rejected")
    return PreviewLayoutCandidate(
        id=candidate_id,
        version=version,
        repository_side=cast(RepositorySide, repository_side),
        format=cast(PreviewFormat, format_name),
        layout_identity=layout_identity,
        confidence=float(confidence),
        files=files,
        languages=languages,
        keys=keys,
        samples=tuple(samples),
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
