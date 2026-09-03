"""Authenticated encryption for backend-only provider secrets."""

from __future__ import annotations

from typing import Self

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

INVALID_KEYRING_MESSAGE = "Secret encryption keyring is invalid"
INVALID_CIPHERTEXT_MESSAGE = "Encrypted secret is invalid"


class SecretBoxConfigurationError(ValueError):
    """The configured authenticated-encryption keyring is unusable."""


class SecretBoxDecryptionError(ValueError):
    """Ciphertext cannot be authenticated or decoded with this keyring."""


class SecretBox:
    """Encrypt and decrypt text with an ordered Fernet rotation keyring."""

    __slots__ = ("_cipher",)

    def __init__(self, cipher: MultiFernet) -> None:
        self._cipher = cipher

    @classmethod
    def from_keyring(cls, keyring: str) -> Self:
        """Build a box whose first key encrypts and whose remaining keys decrypt."""
        raw_keys = keyring.split(",")
        if not raw_keys or any(not key for key in raw_keys):
            raise SecretBoxConfigurationError(INVALID_KEYRING_MESSAGE)
        try:
            cipher = MultiFernet([Fernet(key.encode("ascii")) for key in raw_keys])
        except (UnicodeEncodeError, TypeError, ValueError) as error:
            raise SecretBoxConfigurationError(INVALID_KEYRING_MESSAGE) from error
        return cls(cipher)

    def encrypt(self, plaintext: str) -> str:
        """Return authenticated URL-safe ciphertext for one nonempty secret."""
        if not isinstance(plaintext, str) or not plaintext:
            raise ValueError("Secret plaintext must be a nonempty string")
        return self._cipher.encrypt(plaintext.encode("utf-8")).decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        """Authenticate and decrypt without reflecting invalid input."""
        try:
            plaintext = self._cipher.decrypt(ciphertext.encode("ascii"))
            return plaintext.decode("utf-8")
        except AttributeError, InvalidToken, TypeError, UnicodeDecodeError, UnicodeEncodeError:
            raise SecretBoxDecryptionError(INVALID_CIPHERTEXT_MESSAGE) from None

    def __repr__(self) -> str:
        """Keep key material and previously processed secrets out of diagnostics."""
        return "SecretBox(<redacted>)"
