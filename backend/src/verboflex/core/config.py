"""Typed application settings seam."""

from functools import lru_cache
from typing import Literal, Self

from pydantic import (
    AnyHttpUrl,
    Field,
    PostgresDsn,
    RedisDsn,
    SecretStr,
    field_validator,
    model_validator,
)
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

    @field_validator("database_url")
    @classmethod
    def require_database_name(cls, database_url: PostgresDsn) -> PostgresDsn:
        """Reject PostgreSQL server addresses without a concrete database."""
        if database_url.path is None or not database_url.path.strip("/"):
            raise ValueError("database_url must name a PostgreSQL database")
        return database_url

    @field_validator("redis_url")
    @classmethod
    def require_redis_database_index(cls, redis_url: RedisDsn) -> RedisDsn:
        """Reject Redis paths that are not valid non-negative database indexes."""
        path = redis_url.path
        if path not in (None, "", "/") and not path.removeprefix("/").isdecimal():
            raise ValueError("redis_url must use a non-negative numeric database")
        return redis_url

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

    @model_validator(mode="after")
    def validate_deployment_security(self) -> Self:
        """Fail deployed environments closed when signing material is absent."""
        if self.app_env == "local":
            return self
        if self.jwt_secret_key is None:
            raise ValueError("JWT signing secret is required in staging and production")
        secret = self.jwt_secret_key.get_secret_value()
        normalized_secret = "".join(
            character for character in secret.casefold() if character.isalnum()
        )
        sentinel_markers = ("replace", "changeme", "placeholder", "example", "notareal")
        if any(marker in normalized_secret for marker in sentinel_markers):
            raise ValueError("JWT signing secret must not use a placeholder value")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide immutable settings value."""
    return Settings()
