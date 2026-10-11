"""Focused administrator preview base-language transport contracts."""

from __future__ import annotations

import importlib
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from verboflex.schemas.previews import (
    AdminActiveRevisionRevalidationConfirmationRequest,
    AdminActiveRevisionRevalidationConfirmationResponse,
    AdminPreviewConfirmationRequest,
    AdminPreviewConfirmationResponse,
)


def _candidate_payload() -> dict[str, object]:
    return {
        "preview_digest": "a" * 64,
        "layout_candidate_id": str(uuid4()),
        "layout_candidate_version": 1,
    }


def _active_payload() -> dict[str, object]:
    return {
        "active_revision_id": str(uuid4()),
        "active_revision_version": 1,
        "mapping_id": str(uuid4()),
        "connection_generation": 1,
        "commits": [{"role": "direct", "commit_hash": "b" * 40}],
        **_candidate_payload(),
    }


@pytest.mark.parametrize(
    "schema,payload",
    [
        (AdminPreviewConfirmationRequest, _candidate_payload()),
        (AdminActiveRevisionRevalidationConfirmationRequest, _active_payload()),
    ],
)
def test_base_language_confirmation_requests_are_required_bounded_and_closed(
    schema: type[AdminPreviewConfirmationRequest]
    | type[AdminActiveRevisionRevalidationConfirmationRequest],
    payload: dict[str, object],
) -> None:
    """The generated transport field is required, nullable for sole selection, and closed."""
    with pytest.raises(ValidationError):
        schema.model_validate(payload)
    assert schema.model_validate({**payload, "base_language": None}).base_language is None
    assert schema.model_validate({**payload, "base_language": "en-US"}).base_language == "en-US"
    for rejected in ("", "a" * 65):
        with pytest.raises(ValidationError):
            schema.model_validate({**payload, "base_language": rejected})
    with pytest.raises(ValidationError):
        schema.model_validate({**payload, "base_language": "en", "source_bytes": "forbidden"})


@pytest.mark.parametrize(
    "schema,fields",
    [
        (
            AdminPreviewConfirmationResponse,
            {
                "job_id": uuid4(),
                "mapping_id": uuid4(),
            },
        ),
        (
            AdminActiveRevisionRevalidationConfirmationResponse,
            {
                "job_id": uuid4(),
                "product_id": uuid4(),
                "active_revision_id": uuid4(),
                "active_revision_version": 1,
                "mapping_id": uuid4(),
                "connection_generation": 1,
                "commits": [
                    {
                        "role": "direct",
                        "repository_id": uuid4(),
                        "source_branch": "main",
                        "commit_hash": "b" * 40,
                    }
                ],
            },
        ),
    ],
)
def test_base_language_confirmation_responses_carry_exact_selected_authority(
    schema: type[AdminPreviewConfirmationResponse]
    | type[AdminActiveRevisionRevalidationConfirmationResponse],
    fields: dict[str, object],
) -> None:
    """Candidate and active confirmation responses expose only the selected language."""
    response = schema.model_validate(
        {
            **fields,
            "preview_digest": "c" * 64,
            "layout_candidate_id": uuid4(),
            "layout_candidate_version": 1,
            "base_language": "it",
            "confirmed_by": uuid4(),
            "confirmed_at": datetime.now(UTC),
        }
    )
    assert response.base_language == "it"
    assert "source_bytes" not in response.model_dump()


def test_base_language_required_uses_one_bounded_conflict_projection() -> None:
    """Ambiguous selection exposes only its closed blocker code."""
    routes = importlib.import_module("verboflex.api.v1.routes.admin_previews")
    service = importlib.import_module("verboflex.services.preview_jobs")

    with pytest.raises(HTTPException) as raised:
        routes._raise_preview_error(service.PreviewBaseLanguageRequired())

    assert raised.value.status_code == 409
    assert raised.value.detail == "base_language_required"
