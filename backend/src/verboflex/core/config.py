"""Typed application settings seam."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings shared by the API scaffold."""

    app_name: str = "VerboFlex API"
    app_env: Literal["local", "staging", "production"] = "local"
    api_v1_prefix: str = "/api/v1"

    model_config = SettingsConfigDict(
        env_prefix="VERBOFLEX_",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide immutable settings value."""
    return Settings()
