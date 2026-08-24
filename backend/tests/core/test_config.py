"""Executable contracts for deployment settings."""

import pytest
from pydantic import AnyHttpUrl, PostgresDsn, RedisDsn, ValidationError

from verboflex.core.config import Settings


def test_local_settings_are_typed_and_allow_explicit_insecure_cookie() -> None:
    """Local HTTP can opt out of Secure while every operational value is typed."""
    settings = Settings(
        app_env="local",
        database_url=PostgresDsn("postgresql+psycopg://verboflex@postgres:5432/verboflex"),
        redis_url=RedisDsn("redis://redis:6379/0"),
        cors_origins=(AnyHttpUrl("http://localhost:5173"),),
        access_token_expire_minutes=15,
        password_change_token_expire_minutes=5,
        refresh_token_expire_days=7,
        service_probe_timeout_seconds=2.0,
        refresh_cookie_secure=False,
    )

    assert settings.app_env == "local"
    assert isinstance(settings.database_url, PostgresDsn)
    assert isinstance(settings.redis_url, RedisDsn)
    assert settings.cors_origins == (AnyHttpUrl("http://localhost:5173/"),)
    assert settings.access_token_expire_minutes == 15
    assert settings.password_change_token_expire_minutes == 5
    assert settings.refresh_token_expire_days == 7
    assert settings.service_probe_timeout_seconds == 2.0
    assert settings.refresh_cookie_secure is False


def test_cors_requires_at_least_one_exact_http_origin() -> None:
    """Credentialed browser requests never run with an empty allowlist."""
    with pytest.raises(ValidationError, match="at least one exact HTTP origin"):
        Settings(cors_origins=())
