"""Exact-origin protection for cookie-authenticated mutations."""

from verboflex.core.config import Settings


class OriginNotAllowed(PermissionError):
    """Raised when a present browser Origin is outside the exact allowlist."""


def enforce_cookie_origin(origin: str | None, *, settings: Settings) -> None:
    """Allow absent Origin or one exact configured scheme/host/port origin."""
    if origin is None:
        return
    allowed = {
        configured.unicode_string().removesuffix("/") for configured in settings.cors_origins
    }
    if origin not in allowed:
        raise OriginNotAllowed("origin not allowed")
