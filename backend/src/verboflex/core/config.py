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

PREVIEW_MAX_TERMINALIZATION_SECONDS = 300
IMPORT_MAX_TERMINALIZATION_SECONDS = 300


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
    bitbucket_oauth_client_id: str | None = None
    bitbucket_oauth_client_secret: SecretStr | None = None
    bitbucket_token_encryption_keyring: SecretStr | None = None
    bitbucket_http_connect_timeout_seconds: Literal[3] = 3
    bitbucket_http_read_timeout_seconds: Literal[10] = 10
    bitbucket_http_write_timeout_seconds: Literal[10] = 10
    bitbucket_http_pool_timeout_seconds: Literal[3] = 3
    preview_soft_time_limit_seconds: int = Field(default=60, gt=0, le=300)
    preview_hard_time_limit_seconds: int = Field(default=75, gt=0, le=300)
    preview_watchdog_grace_seconds: int = Field(default=15, gt=0, le=300)
    preview_watchdog_interval_seconds: int = Field(default=5, gt=0, le=300)
    import_soft_time_limit_seconds: int = Field(default=60, gt=0, le=300)
    import_hard_time_limit_seconds: int = Field(default=75, gt=0, le=300)
    import_watchdog_grace_seconds: int = Field(default=15, gt=0, le=300)
    import_watchdog_interval_seconds: int = Field(default=5, gt=0, le=300)

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

    @field_validator("refresh_cookie_secure")
    @classmethod
    def require_secure_refresh_cookie(cls, secure: bool) -> bool:
        """Reject every attempt to disable the approved Secure-only cookie."""
        if not secure:
            raise ValueError("refresh cookie must always be Secure")
        return secure

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
    def validate_preview_recovery_limits(self) -> Self:
        """Keep the watchdog inside one explicit finite terminalization bound."""
        if self.preview_soft_time_limit_seconds >= self.preview_hard_time_limit_seconds:
            raise ValueError("preview soft time limit must be below the hard time limit")
        if self.preview_watchdog_interval_seconds >= self.preview_watchdog_grace_seconds:
            raise ValueError("preview watchdog interval must be shorter than its grace")
        if self.preview_max_terminalization_seconds > PREVIEW_MAX_TERMINALIZATION_SECONDS:
            raise ValueError("preview maximum terminalization bound exceeds 300 seconds")
        return self

    @property
    def preview_max_terminalization_seconds(self) -> int:
        """Maximum age plus one scheduler scan before durable terminalization."""
        return (
            self.preview_hard_time_limit_seconds
            + self.preview_watchdog_grace_seconds
            + self.preview_watchdog_interval_seconds
        )

    @model_validator(mode="after")
    def validate_import_recovery_limits(self) -> Self:
        """Keep import execution and recovery inside one finite ordered bound."""
        if self.import_soft_time_limit_seconds >= self.import_hard_time_limit_seconds:
            raise ValueError("import soft time limit must be below the hard time limit")
        if self.import_watchdog_interval_seconds >= self.import_watchdog_grace_seconds:
            raise ValueError("import watchdog interval must be shorter than its grace")
        if self.import_max_terminalization_seconds > IMPORT_MAX_TERMINALIZATION_SECONDS:
            raise ValueError("import maximum terminalization bound exceeds 300 seconds")
        return self

    @property
    def import_max_terminalization_seconds(self) -> int:
        """Maximum import age plus one scheduler scan before terminalization."""
        return (
            self.import_hard_time_limit_seconds
            + self.import_watchdog_grace_seconds
            + self.import_watchdog_interval_seconds
        )

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
        if len(secret.encode("utf-8")) < 32:
            raise ValueError("JWT signing secret must contain at least 32 bytes")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide immutable settings value."""
    return Settings()
