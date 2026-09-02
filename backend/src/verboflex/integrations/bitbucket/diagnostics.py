"""Allowlisted structured diagnostics for terminal Bitbucket read failures."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Final, Literal
from uuid import UUID

from verboflex.integrations.bitbucket.urls import (
    PHASE_3_READ_OPERATIONS,
    BitbucketOperation,
)

BitbucketDiagnosticErrorCategory = Literal[
    "disconnected",
    "reauthorization_required",
    "permission_denied",
    "not_found",
    "rate_limited",
    "unavailable",
    "timeout",
    "invalid_source",
    "limit_exceeded",
]

BITBUCKET_OPERATION_FAILURE_EVENT: Final = "bitbucket.provider_operation_failed"
MAX_DIAGNOSTIC_ELAPSED_MS: Final = 2_147_483_647

_ERROR_CATEGORIES: Final = frozenset(
    {
        "disconnected",
        "reauthorization_required",
        "permission_denied",
        "not_found",
        "rate_limited",
        "unavailable",
        "timeout",
        "invalid_source",
        "limit_exceeded",
    }
)
_LOGGER = logging.getLogger("verboflex.bitbucket.operations")


@dataclass(frozen=True, slots=True)
class BitbucketDiagnosticContext:
    """One import execution identity safe to retain in operational logs."""

    import_id: UUID
    execution_number: int

    def __post_init__(self) -> None:
        if not isinstance(self.import_id, UUID):
            raise ValueError("Bitbucket diagnostic import identity rejected")
        if (
            not isinstance(self.execution_number, int)
            or isinstance(self.execution_number, bool)
            or self.execution_number < 1
        ):
            raise ValueError("Bitbucket diagnostic execution identity rejected")


def _safe_provider_status(provider_status: int | None) -> int | None:
    if provider_status is None:
        return None
    if (
        not isinstance(provider_status, int)
        or isinstance(provider_status, bool)
        or not 100 <= provider_status <= 599
    ):
        raise ValueError("Bitbucket diagnostic provider status rejected")
    return provider_status


def _safe_elapsed_ms(elapsed_ms: int | float) -> int:
    if (
        not isinstance(elapsed_ms, int | float)
        or isinstance(elapsed_ms, bool)
        or not math.isfinite(elapsed_ms)
        or elapsed_ms < 0
    ):
        raise ValueError("Bitbucket diagnostic elapsed time rejected")
    return min(int(elapsed_ms), MAX_DIAGNOSTIC_ELAPSED_MS)


def log_bitbucket_operation_failure(
    *,
    context: BitbucketDiagnosticContext,
    operation: BitbucketOperation,
    error_category: BitbucketDiagnosticErrorCategory,
    provider_status: int | None,
    elapsed_ms: int | float,
) -> None:
    """Emit one fixed event containing only validated, allowlisted metadata."""
    if not isinstance(context, BitbucketDiagnosticContext):
        raise ValueError("Bitbucket diagnostic context rejected")
    if not isinstance(operation, BitbucketOperation) or operation not in PHASE_3_READ_OPERATIONS:
        raise ValueError("Bitbucket diagnostic operation rejected")
    if error_category not in _ERROR_CATEGORIES:
        raise ValueError("Bitbucket diagnostic error category rejected")

    safe_status = _safe_provider_status(provider_status)
    safe_elapsed = _safe_elapsed_ms(elapsed_ms)
    import_identity = str(context.import_id)
    fields: dict[str, str | int | None] = {
        "event_name": BITBUCKET_OPERATION_FAILURE_EVENT,
        "operation": operation.value,
        "error_category": error_category,
        "provider_status": safe_status,
        "correlation_id": import_identity,
        "import_id": import_identity,
        "execution_number": context.execution_number,
        "elapsed_ms": safe_elapsed,
    }

    try:
        _LOGGER.info(BITBUCKET_OPERATION_FAILURE_EVENT, extra=fields)
    except Exception:
        # Operational logging is deliberately subordinate to durable import state.
        return


__all__ = [
    "MAX_DIAGNOSTIC_ELAPSED_MS",
    "BitbucketDiagnosticContext",
    "BitbucketDiagnosticErrorCategory",
    "log_bitbucket_operation_failure",
]
