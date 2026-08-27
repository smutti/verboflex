"""Fail-closed construction and validation for Bitbucket Cloud REST URLs."""

from __future__ import annotations

import re
from urllib.parse import quote, unquote, urlencode, urlsplit

BITBUCKET_API_HOST = "api.bitbucket.org"
BITBUCKET_API_ORIGIN = f"https://{BITBUCKET_API_HOST}"
BITBUCKET_URL_REJECTED_MESSAGE = "Bitbucket provider URL rejected"

_PROVIDER_IDENTIFIER = re.compile(r"[a-z0-9][a-z0-9_-]{0,99}")
_ENCODED_PATH_SEGMENT = r"(?:[A-Za-z0-9._~-]|%[0-9A-Fa-f]{2})+"
_REPOSITORY_READ_BASE = rf"/2\.0/repositories/{_ENCODED_PATH_SEGMENT}/{_ENCODED_PATH_SEGMENT}"
_ALLOWED_READ_PATHS = (
    re.compile(rf"{_REPOSITORY_READ_BASE}/?"),
    re.compile(
        rf"{_REPOSITORY_READ_BASE}/refs/branches"
        rf"(?:/{_ENCODED_PATH_SEGMENT})?/?"
    ),
    re.compile(
        rf"{_REPOSITORY_READ_BASE}/src/[0-9A-Fa-f]{{40}}"
        rf"(?:/{_ENCODED_PATH_SEGMENT}(?:/{_ENCODED_PATH_SEGMENT})*)?/?"
    ),
)


def _source_path_is_safe(path: str) -> bool:
    marker = "/src/"
    if marker not in path:
        return True
    suffix = path.split(marker, 1)[1]
    parts = suffix.split("/")[1:]
    for encoded_part in parts:
        if not encoded_part:
            continue
        decoded_part = unquote(encoded_part)
        if (
            decoded_part in {".", ".."}
            or "/" in decoded_part
            or "\\" in decoded_part
            or "\x00" in decoded_part
            or not decoded_part.isprintable()
        ):
            return False
    return True


def validate_bitbucket_api_url(url: str) -> str:
    """Return one exact Bitbucket REST URL or reject it before authentication."""
    if not isinstance(url, str) or not url or "\\" in url:
        raise ValueError(BITBUCKET_URL_REJECTED_MESSAGE)
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        raise ValueError(BITBUCKET_URL_REJECTED_MESSAGE) from None
    if (
        parsed.scheme != "https"
        or parsed.hostname != BITBUCKET_API_HOST
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
        or not any(pattern.fullmatch(parsed.path) for pattern in _ALLOWED_READ_PATHS)
        or not _source_path_is_safe(parsed.path)
        or parsed.fragment
    ):
        raise ValueError(BITBUCKET_URL_REJECTED_MESSAGE)
    return url


def repository_metadata_url(*, workspace: str, repository_slug: str) -> str:
    """Build the only repository metadata endpoint accepted by the tracer."""
    if (
        _PROVIDER_IDENTIFIER.fullmatch(workspace) is None
        or _PROVIDER_IDENTIFIER.fullmatch(repository_slug) is None
    ):
        raise ValueError(BITBUCKET_URL_REJECTED_MESSAGE)
    url = (
        f"{BITBUCKET_API_ORIGIN}/2.0/repositories/"
        f"{quote(workspace, safe='')}/{quote(repository_slug, safe='')}"
    )
    return validate_bitbucket_api_url(url)


def repository_branches_url(*, workspace: str, repository_slug: str) -> str:
    """Build the live branch collection with Bitbucket's maximum page size."""
    base = repository_metadata_url(workspace=workspace, repository_slug=repository_slug)
    return validate_bitbucket_api_url(f"{base}/refs/branches?{urlencode({'pagelen': 100})}")


def repository_branch_url(
    *,
    workspace: str,
    repository_slug: str,
    branch: str,
) -> str:
    """Build one exact branch-detail endpoint without interpreting its spelling."""
    if (
        not isinstance(branch, str)
        or not branch
        or len(branch) > 255
        or "\\" in branch
        or "\x00" in branch
        or not branch.isprintable()
    ):
        raise ValueError(BITBUCKET_URL_REJECTED_MESSAGE)
    base = repository_branches_url(
        workspace=workspace,
        repository_slug=repository_slug,
    ).split("?", 1)[0]
    return validate_bitbucket_api_url(f"{base}/{quote(branch, safe='')}")


def validate_repository_relative_path(path: str) -> str:
    """Return one printable repository-relative POSIX path without traversal."""
    if (
        not isinstance(path, str)
        or not path
        or len(path) > 4096
        or path.startswith("/")
        or path.endswith("/")
        or "\\" in path
        or "\x00" in path
        or not path.isprintable()
    ):
        raise ValueError(BITBUCKET_URL_REJECTED_MESSAGE)
    parts = path.split("/")
    if any(not part or part in {".", ".."} for part in parts):
        raise ValueError(BITBUCKET_URL_REJECTED_MESSAGE)
    return "/".join(parts)


def repository_source_url(
    *,
    workspace: str,
    repository_slug: str,
    commit_hash: str,
    path: str | None = None,
    paginated: bool = False,
) -> str:
    """Build one commit-bound source tree or raw-file endpoint."""
    if (
        not isinstance(commit_hash, str)
        or len(commit_hash) != 40
        or any(character not in "0123456789abcdefABCDEF" for character in commit_hash)
    ):
        raise ValueError(BITBUCKET_URL_REJECTED_MESSAGE)
    base = repository_metadata_url(workspace=workspace, repository_slug=repository_slug)
    url = f"{base}/src/{commit_hash}/"
    if path is not None:
        encoded_path = "/".join(
            quote(part, safe="") for part in validate_repository_relative_path(path).split("/")
        )
        url = f"{url}{encoded_path}"
    if paginated:
        url = f"{url}?{urlencode({'pagelen': 100})}"
    return validate_bitbucket_api_url(url)
