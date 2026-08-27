"""Fail-closed construction and validation for Bitbucket Cloud REST URLs."""

from __future__ import annotations

import re
from urllib.parse import quote, urlsplit

BITBUCKET_API_HOST = "api.bitbucket.org"
BITBUCKET_API_ORIGIN = f"https://{BITBUCKET_API_HOST}"
BITBUCKET_URL_REJECTED_MESSAGE = "Bitbucket provider URL rejected"

_PROVIDER_IDENTIFIER = re.compile(r"[a-z0-9][a-z0-9_-]{0,99}")


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
        or not parsed.path.startswith("/2.0/")
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
