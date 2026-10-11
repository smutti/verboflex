from pathlib import Path

from verboflex.localization.preview.registry import detect_preview_layouts
from verboflex.services.repository_discovery import RepositorySourceFile

FIXTURES = Path(__file__).parents[3] / "fixtures" / "localization" / "xliff"


def _file(path: str, fixture: str) -> RepositorySourceFile:
    return RepositorySourceFile(path=path, content=(FIXTURES / fixture).read_bytes())


def test_xliff_preview_detects_both_suffixes_and_exact_versions() -> None:
    result = detect_preview_layouts(
        (
            _file("translations/it-IT/app.xlf", "valid_12.xlf"),
            _file("translations/fr-FR/app.xliff", "valid_20.xliff"),
        ),
        repository_side="direct",
    )
    candidates = [candidate for candidate in result.candidates if candidate.format == "xliff"]
    assert [candidate.layout_identity for candidate in candidates] == [
        "xliff:translations/{locale}/app.xlf",
        "xliff:translations/{locale}/app.xliff",
    ]
    assert [candidate.languages for candidate in candidates] == [("it-IT",), ("fr-FR",)]


def test_xliff_preview_uses_standalone_identity_without_locale_path_signal() -> None:
    result = detect_preview_layouts(
        (_file("exports/mobile.xliff", "valid_21.xliff"),), repository_side="direct"
    )
    candidate = next(candidate for candidate in result.candidates if candidate.format == "xliff")
    assert candidate.layout_identity == "xliff:exports/mobile.xliff"
    assert candidate.languages == ("ja-JP",)
    assert candidate.samples[0].translation == "キャンセル"
