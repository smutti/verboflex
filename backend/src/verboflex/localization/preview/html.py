"""One recursive HTML template collection within the selected import root."""

from collections.abc import Iterable
from posixpath import commonpath, dirname

from verboflex.localization.html import html_path
from verboflex.localization.importing.core import CanonicalParserInput
from verboflex.localization.importing.html import parse_html
from verboflex.localization.preview.core import (
    PreviewDetectionResult,
    RepositorySide,
    build_layout_candidate,
)
from verboflex.services.repository_discovery import RepositorySourceFile


def detect_html_layouts(
    files: Iterable[RepositorySourceFile],
    *,
    repository_side: RepositorySide,
) -> PreviewDetectionResult:
    sources = tuple(file for file in files if file.path.lower().endswith((".html", ".htm")))
    if not sources or len(sources) > 500 or sum(len(f.content) for f in sources) > 20971520:
        return PreviewDetectionResult(candidates=())
    root = commonpath([dirname(file.path) for file in sources]) or "."
    layout = f"html:{root}"
    values: dict[str, dict[str, str]] = {}
    for file in sources:
        identity = html_path(file.path)
        if identity is None:
            return PreviewDetectionResult(candidates=())
        language = identity[0]
        result = parse_html(
            CanonicalParserInput(
                format="html",
                repository_side=repository_side,
                path=file.path,
                content=file.content,
                layout_identity=layout,
                layout_version=1,
                base_language=language,
            )
        )
        if result.issues:
            return PreviewDetectionResult(candidates=())
        peers = values.setdefault(language, {})
        for value in result.values:
            if value.logical_key in peers:
                return PreviewDetectionResult(candidates=())
            peers[value.logical_key] = value.display_text
    try:
        candidate = build_layout_candidate(
            repository_side=repository_side,
            format="html",
            layout_identity=layout,
            files=(file.path for file in sources),
            values=values,
        )
        return PreviewDetectionResult(candidates=(candidate,))
    except ValueError:
        return PreviewDetectionResult(candidates=())
