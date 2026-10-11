"""Text accepted by UTF-8 APIs and PostgreSQL, without changing user content."""

from typing import Annotated

from pydantic import AfterValidator


def validate_storable_text(value: str) -> str:
    if "\x00" in value:
        raise ValueError("Text cannot contain a null character")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise ValueError("Text must contain valid Unicode characters") from None
    return value


StorableText = Annotated[str, AfterValidator(validate_storable_text)]
