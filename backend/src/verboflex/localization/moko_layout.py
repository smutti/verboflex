"""Exact MOKO Resources XML paths, without inferring the base language."""

from verboflex.integrations.bitbucket.urls import validate_repository_relative_path
from verboflex.localization.preview.core import normalize_preview_locale


def moko_layout(path: str) -> tuple[str, str] | None:
    try:
        validate_repository_relative_path(path)
    except ValueError:
        return None
    parts = path.split("/")
    if len(parts) < 3 or parts[-3] != "moko-resources" or parts[-1] != "strings.xml":
        return None
    locale = "default" if parts[-2] == "base" else normalize_preview_locale(parts[-2])
    if locale is None:
        return None
    return "/".join(parts[:-2]), locale


def moko_resource_root(path: str) -> str | None:
    """Recognize membership even when a peer has an unsupported locale/filename."""
    try:
        validate_repository_relative_path(path)
    except ValueError:
        return None
    parts = path.split("/")
    if "moko-resources" not in parts:
        return None
    return "/".join(parts[: parts.index("moko-resources") + 1])
