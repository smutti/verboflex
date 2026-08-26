"""Executable contracts for deployment settings."""

from typing import Literal

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import AnyHttpUrl, PostgresDsn, RedisDsn, ValidationError

from verboflex.core.config import Settings, get_settings


def test_local_settings_are_typed_and_enforce_secure_cookie() -> None:
    """Every operational setting is typed and the refresh cookie stays Secure."""
    settings = Settings(
        app_env="local",
        database_url=PostgresDsn("postgresql+psycopg://verboflex@postgres:5432/verboflex"),
        redis_url=RedisDsn("redis://redis:6379/0"),
        cors_origins=(AnyHttpUrl("http://localhost:5173"),),
        access_token_expire_minutes=15,
        password_change_token_expire_minutes=5,
        refresh_token_expire_days=7,
        service_probe_timeout_seconds=2.0,
    )

    assert settings.app_env == "local"
    assert isinstance(settings.database_url, PostgresDsn)
    assert isinstance(settings.redis_url, RedisDsn)
    assert settings.cors_origins == (AnyHttpUrl("http://localhost:5173/"),)
    assert settings.access_token_expire_minutes == 15
    assert settings.password_change_token_expire_minutes == 5
    assert settings.refresh_token_expire_days == 7
    assert settings.service_probe_timeout_seconds == 2.0
    assert settings.refresh_cookie_secure is True


def test_cors_requires_at_least_one_exact_http_origin() -> None:
    """Credentialed browser requests never run with an empty allowlist."""
    with pytest.raises(ValidationError, match="at least one exact HTTP origin"):
        Settings(cors_origins=())


def test_cors_rejects_urls_that_are_not_exact_origins() -> None:
    """Paths, queries, fragments, and embedded credentials are not origins."""
    with pytest.raises(ValidationError, match="must contain exact HTTP origins"):
        Settings(cors_origins=(AnyHttpUrl("https://app.verboflex.example/path"),))


def test_database_url_requires_a_named_postgresql_database() -> None:
    """A syntactically valid server-only DSN is not an operational database target."""
    with pytest.raises(ValidationError, match="must name a PostgreSQL database"):
        Settings(database_url=PostgresDsn("postgresql+psycopg://verboflex@postgres"))


def test_redis_url_rejects_a_non_numeric_database_path() -> None:
    """Reject Redis paths that the client cannot interpret as a database index."""
    with pytest.raises(ValidationError, match="non-negative numeric database"):
        Settings(redis_url=RedisDsn("redis://redis:6379/not-a-database"))


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("access_token_expire_minutes", 0),
        ("access_token_expire_minutes", 61),
        ("password_change_token_expire_minutes", 0),
        ("password_change_token_expire_minutes", 16),
        ("refresh_token_expire_days", 0),
        ("refresh_token_expire_days", 31),
        ("service_probe_timeout_seconds", 0),
        ("service_probe_timeout_seconds", 30.1),
    ],
)
def test_token_lifetimes_and_probe_timeout_are_bounded(
    field_name: str, invalid_value: int | float
) -> None:
    """Reject zero, negative, or operationally excessive timing values."""
    with pytest.raises(ValidationError):
        Settings.model_validate({field_name: invalid_value})


@pytest.mark.parametrize("app_env", ["staging", "production"])
def test_deployed_environments_reject_a_missing_signing_secret(
    app_env: Literal["staging", "production"],
) -> None:
    """A deployed process never starts without an explicit signing secret."""
    with pytest.raises(ValidationError, match="signing secret is required"):
        Settings(app_env=app_env, jwt_secret_key=None, refresh_cookie_secure=True)


@pytest.mark.parametrize("app_env", ["staging", "production"])
@pytest.mark.parametrize(
    "sentinel",
    [
        "replace-me-with-at-least-32-random-bytes",
        "change-me-before-deploying-this-app-please",
        "example-placeholder-not-a-real-secret-value",
    ],
)
def test_deployed_environments_reject_sentinel_signing_secrets(
    app_env: Literal["staging", "production"], sentinel: str
) -> None:
    """Long documentation placeholders remain unusable deployment credentials."""
    with pytest.raises(ValidationError, match="must not use a placeholder value"):
        Settings.model_validate(
            {
                "app_env": app_env,
                "jwt_secret_key": sentinel,
                "refresh_cookie_secure": True,
            }
        )


@pytest.mark.parametrize("app_env", ["staging", "production"])
@pytest.mark.parametrize("short_secret", ["x" * 31, "é" * 15])
def test_deployed_environments_reject_signing_secrets_shorter_than_32_bytes(
    app_env: Literal["staging", "production"], short_secret: str
) -> None:
    """The minimum applies to encoded key bytes rather than Unicode characters."""
    with pytest.raises(ValidationError, match="at least 32 bytes"):
        Settings.model_validate(
            {
                "app_env": app_env,
                "jwt_secret_key": short_secret,
                "refresh_cookie_secure": True,
            }
        )


@given(st.text(alphabet=st.characters(min_codepoint=33, max_codepoint=126), max_size=31))
def test_production_rejects_every_generated_ascii_secret_shorter_than_32_bytes(
    short_secret: str,
) -> None:
    """Every generated ASCII key below the byte boundary fails closed."""
    with pytest.raises(ValidationError):
        Settings.model_validate(
            {
                "app_env": "production",
                "jwt_secret_key": short_secret,
                "refresh_cookie_secure": True,
            }
        )


@pytest.mark.parametrize("app_env", ["local", "staging", "production"])
def test_every_environment_rejects_insecure_refresh_cookies(
    app_env: Literal["local", "staging", "production"],
) -> None:
    """No environment can disable the approved Secure-only cookie contract."""
    with pytest.raises(ValidationError):
        Settings.model_validate(
            {
                "app_env": app_env,
                "jwt_secret_key": "0123456789abcdef" * 2,
                "refresh_cookie_secure": False,
            }
        )


@pytest.mark.parametrize("app_env", ["staging", "production"])
def test_deployed_environments_accept_strong_secret_and_secure_cookie(
    app_env: Literal["staging", "production"],
) -> None:
    """Fail-closed checks retain the approved secure startup path."""
    settings = Settings.model_validate(
        {
            "app_env": app_env,
            "jwt_secret_key": "0123456789abcdef" * 2,
            "refresh_cookie_secure": True,
        }
    )

    assert settings.app_env == app_env
    assert settings.refresh_cookie_secure is True


def test_process_settings_are_cached_and_immutable() -> None:
    """All application consumers share one frozen validated settings instance."""
    get_settings.cache_clear()

    settings = get_settings()

    assert get_settings() is settings
    with pytest.raises(ValidationError, match="Instance is frozen"):
        settings.app_env = "production"
