"""Interpret the provider's Retry-After header as an absolute UTC deadline."""

from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime


def retry_deadline(value: str | None) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    try:
        if value.isascii() and value.isdecimal():
            return datetime.now(UTC) + timedelta(seconds=int(value))
        deadline = parsedate_to_datetime(value)
        return deadline.astimezone(UTC) if deadline.tzinfo else None
    except TypeError, ValueError, OverflowError:
        return None
