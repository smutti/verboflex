"""Bounded public and authenticated system contracts."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    """Constant public liveness response."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"]


ServiceState = Literal["online", "unavailable", "pending"]


class SystemStatusResponse(BaseModel):
    """Bounded service state without infrastructure details."""

    model_config = ConfigDict(extra="forbid")

    api: Literal["online"]
    database: ServiceState
    redis: ServiceState
    worker: ServiceState
    checked_at: datetime
