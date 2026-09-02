"""Structured Bitbucket diagnostics retain useful facts without provider material."""

from __future__ import annotations

import logging
import math
from typing import Any
from uuid import UUID

import pytest

IMPORT_ID = UUID("1e4decb8-fb89-4e92-a27c-1b42b9a30ef2")


def _diagnostic_record(caplog: pytest.LogCaptureFixture) -> logging.LogRecord:
    records = [
        record for record in caplog.records if record.name == "verboflex.bitbucket.operations"
    ]
    assert len(records) == 1
    return records[0]


def test_bitbucket_failure_event_has_only_closed_bounded_operational_fields(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """One record keeps exact correlation fields while discarding failure context."""
    from verboflex.integrations.bitbucket.diagnostics import (
        BitbucketDiagnosticContext,
        log_bitbucket_operation_failure,
    )
    from verboflex.integrations.bitbucket.urls import BitbucketOperation

    caplog.set_level(logging.INFO, logger="verboflex.bitbucket.operations")
    context = BitbucketDiagnosticContext(import_id=IMPORT_ID, execution_number=3)
    log_bitbucket_operation_failure(
        context=context,
        operation=BitbucketOperation.SOURCE_FILE,
        error_category="permission_denied",
        provider_status=403,
        elapsed_ms=37.9,
    )

    record = _diagnostic_record(caplog)
    assert record.getMessage() == "bitbucket.provider_operation_failed"
    assert record.args == ()
    assert {
        "event_name": record.event_name,
        "operation": record.operation,
        "error_category": record.error_category,
        "provider_status": record.provider_status,
        "correlation_id": record.correlation_id,
        "import_id": record.import_id,
        "execution_number": record.execution_number,
        "elapsed_ms": record.elapsed_ms,
    } == {
        "event_name": "bitbucket.provider_operation_failed",
        "operation": "raw-source-file-read-at-commit",
        "error_category": "permission_denied",
        "provider_status": 403,
        "correlation_id": str(IMPORT_ID),
        "import_id": str(IMPORT_ID),
        "execution_number": 3,
        "elapsed_ms": 37,
    }


def test_bitbucket_failure_event_excludes_recursive_sensitive_canaries(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Active exception context and every provider/source canary stay out of logs."""
    from verboflex.integrations.bitbucket.diagnostics import (
        BitbucketDiagnosticContext,
        log_bitbucket_operation_failure,
    )
    from verboflex.integrations.bitbucket.urls import BitbucketOperation

    canaries = (
        "provider-body-c6a87b5f",
        "access-token-4fb2ef94",
        "client-secret-f1287285",  # pragma: allowlist secret
        "Bearer authorization-header-d418d508",  # pragma: allowlist secret
        "raw-source-text-63e5f819",
        "https://api.bitbucket.org/2.0/repositories/unsafe-workspace-a2f58d/"
        "unsafe-repository-09a3fe/src/deadbeef/unsafe-path-8ea1e7",
        "unsafe-workspace-a2f58d",
        "unsafe-repository-09a3fe",
        "unsafe-branch-96c257",
        "unsafe-path-8ea1e7",
        "traceback-canary-59129f",
    )
    caplog.set_level(logging.INFO, logger="verboflex.bitbucket.operations")

    try:
        raise RuntimeError(" :: ".join(canaries))
    except RuntimeError:
        log_bitbucket_operation_failure(
            context=BitbucketDiagnosticContext(import_id=IMPORT_ID, execution_number=1),
            operation=BitbucketOperation.SOURCE_TREE,
            error_category="invalid_source",
            provider_status=200,
            elapsed_ms=1,
        )

    record = _diagnostic_record(caplog)
    rendered_surfaces = (
        repr(record.msg),
        repr(record.args),
        repr(record.__dict__),
        caplog.text,
    )
    for canary in canaries:
        assert all(canary not in surface for surface in rendered_surfaces)
    assert record.exc_info is None
    assert record.stack_info is None


@pytest.mark.parametrize(
    ("overrides", "expected_exception"),
    [
        ({"operation": "free-form-operation"}, ValueError),
        ({"error_category": "free-form-category"}, ValueError),
        ({"provider_status": "403"}, ValueError),
        ({"provider_status": True}, ValueError),
        ({"provider_status": 99}, ValueError),
        ({"provider_status": 600}, ValueError),
        ({"elapsed_ms": -1}, ValueError),
        ({"elapsed_ms": math.inf}, ValueError),
        ({"elapsed_ms": math.nan}, ValueError),
    ],
)
def test_bitbucket_failure_event_rejects_free_form_or_invalid_values(
    caplog: pytest.LogCaptureFixture,
    overrides: dict[str, Any],
    expected_exception: type[Exception],
) -> None:
    """Unbounded caller-controlled values are rejected before logging."""
    from verboflex.integrations.bitbucket.diagnostics import (
        BitbucketDiagnosticContext,
        log_bitbucket_operation_failure,
    )
    from verboflex.integrations.bitbucket.urls import BitbucketOperation

    values: dict[str, Any] = {
        "context": BitbucketDiagnosticContext(import_id=IMPORT_ID, execution_number=1),
        "operation": BitbucketOperation.REPOSITORY_METADATA,
        "error_category": "unavailable",
        "provider_status": None,
        "elapsed_ms": 0,
    }
    values.update(overrides)
    caplog.set_level(logging.INFO, logger="verboflex.bitbucket.operations")

    with pytest.raises(expected_exception):
        log_bitbucket_operation_failure(**values)

    assert caplog.records == []


@pytest.mark.parametrize(
    "context_values",
    [
        {"import_id": str(IMPORT_ID), "execution_number": 1},
        {"import_id": IMPORT_ID, "execution_number": 0},
        {"import_id": IMPORT_ID, "execution_number": True},
    ],
)
def test_bitbucket_diagnostic_context_rejects_invalid_identity(
    context_values: dict[str, Any],
) -> None:
    """The correlation context cannot be forged with strings or invalid counters."""
    from verboflex.integrations.bitbucket.diagnostics import BitbucketDiagnosticContext

    with pytest.raises(ValueError):
        BitbucketDiagnosticContext(**context_values)


def test_bitbucket_failure_elapsed_time_is_capped_to_a_safe_integer(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Unexpectedly large monotonic intervals cannot create unbounded log values."""
    from verboflex.integrations.bitbucket.diagnostics import (
        MAX_DIAGNOSTIC_ELAPSED_MS,
        BitbucketDiagnosticContext,
        log_bitbucket_operation_failure,
    )
    from verboflex.integrations.bitbucket.urls import BitbucketOperation

    caplog.set_level(logging.INFO, logger="verboflex.bitbucket.operations")
    log_bitbucket_operation_failure(
        context=BitbucketDiagnosticContext(import_id=IMPORT_ID, execution_number=1),
        operation=BitbucketOperation.BRANCH_RESOLVE,
        error_category="timeout",
        provider_status=None,
        elapsed_ms=10**30,
    )

    assert _diagnostic_record(caplog).elapsed_ms == MAX_DIAGNOSTIC_ELAPSED_MS


def test_bitbucket_failure_helper_has_no_generic_provider_context_channel() -> None:
    """Arbitrary provider context cannot enter the structured boundary."""
    from verboflex.integrations.bitbucket.diagnostics import (
        BitbucketDiagnosticContext,
        log_bitbucket_operation_failure,
    )
    from verboflex.integrations.bitbucket.urls import BitbucketOperation

    with pytest.raises(TypeError):
        log_bitbucket_operation_failure(
            context=BitbucketDiagnosticContext(import_id=IMPORT_ID, execution_number=1),
            operation=BitbucketOperation.SOURCE_FILE,
            error_category="unavailable",
            provider_status=None,
            elapsed_ms=1,
            provider_context={"body": "must-not-be-accepted"},  # type: ignore[call-arg]
        )
