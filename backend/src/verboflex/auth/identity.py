"""Canonical internal login identifiers."""

from email_validator import EmailNotValidError, validate_email

ASCII_WHITESPACE = " \t\n\r\f\v"


def normalize_email(email: str) -> str:
    """Validate and canonicalize a corporate login identifier."""
    candidate = email.strip(ASCII_WHITESPACE)
    try:
        validated = validate_email(candidate, check_deliverability=False)
    except EmailNotValidError as error:
        raise ValueError("invalid email address") from error
    return validated.normalized.lower()
