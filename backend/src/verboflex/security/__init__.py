"""Security primitives with narrow, non-disclosing interfaces."""

from verboflex.security.secret_box import (
    SecretBox,
    SecretBoxConfigurationError,
    SecretBoxDecryptionError,
)

__all__ = ["SecretBox", "SecretBoxConfigurationError", "SecretBoxDecryptionError"]
