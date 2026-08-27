"""Evidence-first contracts for the strict Android XML preview detector."""

from __future__ import annotations

import importlib
from dataclasses import FrozenInstanceError

import pytest

from verboflex.services.repository_discovery import RepositorySourceFile


def _detector_module() -> object:
    """Resolve the production detector at test time so RED is a behavioral failure."""
    return importlib.import_module("verboflex.localization.preview.android_xml")


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
