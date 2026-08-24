"""Typed application settings seam."""

from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field, PostgresDsn, RedisDsn, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings shared by the API scaffold."""

    app_name: str = "VerboFlex API"
    app_env: Literal["local", "staging", "production"] = "local"
    api_v1_prefix: str = "/api/v1"
    database_url: PostgresDsn = PostgresDsn(
        "postgresql+psycopg://verboflex@localhost:5432/verboflex"
    )
    redis_url: RedisDsn = RedisDsn("redis://localhost:6379/0")
    jwt_secret_key: SecretStr | None = None
    jwt_algorithm: Literal["HS256"] = "HS256"
    cors_origins: tuple[AnyHttpUrl, ...] = (AnyHttpUrl("http://localhost:5173"),)
    access_token_expire_minutes: int = Field(default=15, ge=1, le=60)
    password_change_token_expire_minutes: int = Field(default=5, ge=1, le=15)
    refresh_token_expire_days: int = Field(default=7, ge=1, le=30)
    service_probe_timeout_seconds: float = Field(default=2.0, gt=0, le=30)
    refresh_cookie_secure: bool = True

    model_config = SettingsConfigDict(
        env_prefix="VERBOFLEX_",
        case_sensitive=False,
        extra="ignore",
        frozen=True,
    )

    @field_validator("cors_origins")
    @classmethod
    def require_cors_origin(cls, origins: tuple[AnyHttpUrl, ...]) -> tuple[AnyHttpUrl, ...]:
        """Require a concrete allowlist for credentialed browser requests."""
        if not origins:
            raise ValueError("CORS requires at least one exact HTTP origin")
        if any(
            origin.path not in (None, "", "/")
            or origin.query is not None
            or origin.fragment is not None
            or origin.username is not None
            or origin.password is not None
            for origin in origins
        ):
            raise ValueError("CORS allowlist must contain exact HTTP origins")
        return origins


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide immutable settings value."""
    return Settings()
