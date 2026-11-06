"""Closed, revision-owned JSON catalog selection. No inferred filename exclusions."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from verboflex.integrations.bitbucket.urls import validate_repository_relative_path
from verboflex.localization.preview.core import (
    extract_preview_locale_path,
    normalize_preview_locale,
)
from verboflex.localization.web.contracts import WebCaptureConfig
from verboflex.services.repository_discovery import RepositorySourceFile


class JsonCatalogProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    version: Literal[1] = 1
    syntax: Literal["ngx_translate"] = "ngx_translate"
    files: Annotated[dict[str, str], Field(min_length=1, max_length=100)]
    web_capture: WebCaptureConfig | None = None
    rich_text_paths: Annotated[tuple[tuple[str, ...], ...], Field(max_length=100)] = ()

    @field_validator("files")
    @classmethod
    def valid_files(cls, files: dict[str, str]) -> dict[str, str]:
        if len(set(files.values())) != len(files):
            raise ValueError("Each locale needs a distinct catalog")
        for locale, path in files.items():
            validate_repository_relative_path(path)
            signal = extract_preview_locale_path(path, suffix=".json")
            if normalize_preview_locale(locale) != locale or signal is None or signal[0] != locale:
                raise ValueError("Catalog path and locale must match")
        return dict(sorted(files.items()))

    @field_validator("rich_text_paths")
    @classmethod
    def valid_paths(cls, paths: tuple[tuple[str, ...], ...]) -> tuple[tuple[str, ...], ...]:
        if len(set(paths)) != len(paths) or any(
            not path
            or len(path) > 12
            or any(not p or len(p) > 255 or not p.isprintable() for p in path)
            for path in paths
        ):
            raise ValueError("Invalid rich text path")
        return paths

    def catalog_paths(self, root: str | None) -> set[str]:
        return {f"{root}/{path}" if root else path for path in self.files.values()}


def select_catalogs(
    files: tuple[RepositorySourceFile, ...], profile: JsonCatalogProfile | None, root: str | None
) -> tuple[RepositorySourceFile, ...]:
    if profile is None:
        return files
    wanted = profile.catalog_paths(root)
    selected = tuple(file for file in files if file.path in wanted)
    if {file.path for file in selected} != wanted or len(selected) != len(wanted):
        raise ValueError("Configured JSON catalogs are missing or duplicated")
    return selected
