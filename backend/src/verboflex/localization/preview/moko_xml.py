"""MOKO preview validated through the canonical Android XML grammar."""

from collections import defaultdict
from collections.abc import Iterable

from verboflex.localization.importing.core import CanonicalParserInput
from verboflex.localization.importing.registry import parse_canonical_mapping
from verboflex.localization.moko_layout import moko_layout, moko_resource_root
from verboflex.localization.preview.core import (
    PreviewDetectionResult,
    PreviewLayoutCandidate,
    RepositorySide,
    build_layout_candidate,
)
from verboflex.services.repository_discovery import RepositorySourceFile


def detect_moko_layouts(
    files: Iterable[RepositorySourceFile], *, repository_side: RepositorySide
) -> PreviewDetectionResult:
    grouped: dict[str, list[RepositorySourceFile]] = defaultdict(list)
    unsupported_roots: set[str] = set()
    for file in files:
        classified = moko_layout(file.path)
        if classified is not None:
            grouped[classified[0]].append(file)
        elif (root := moko_resource_root(file.path)) is not None:
            unsupported_roots.add(root)
    candidates: list[PreviewLayoutCandidate] = []
    for layout, sources in sorted(grouped.items()):
        if layout in unsupported_roots:
            continue
        # "und" is an internal validation placeholder, never published as the
        # inferred base language. Preview exposes the established default marker.
        parsed = parse_canonical_mapping(
            tuple(
                CanonicalParserInput(
                    format="android_xml",
                    repository_side="direct",
                    path=file.path,
                    content=file.content,
                    layout_identity=layout,
                    layout_version=1,
                    base_language="und",
                )
                for file in sources
            )
        )
        if parsed.issues:
            continue
        values: dict[str, dict[str, str]] = defaultdict(dict)
        for value in parsed.values:
            classified = moko_layout(value.locator.path)
            assert classified is not None
            locale = classified[1]
            # Collection selectors are not represented by the scalar preview
            # contract; fail closed instead of merging distinct typed values.
            if value.selector.kind != "scalar":
                break
            values[locale][value.logical_key] = value.display_text
        else:
            try:
                candidates.append(
                    build_layout_candidate(
                        repository_side=repository_side,
                        format="android_xml",
                        layout_identity=layout,
                        files=(file.path for file in sources),
                        values=values,
                    )
                )
            except ValueError:
                continue
    return PreviewDetectionResult(candidates=tuple(candidates))
