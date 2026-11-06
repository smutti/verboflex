"""Large application baselines remain readable after successful activation."""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from verboflex.schemas.imports import (
    AdminImportBaselineResponse,
    AdminImportSourceReferenceResponse,
)


@pytest.mark.parametrize("count", [614, 5_500, 5_501])
def test_application_and_localization_baseline_capacity(count: int) -> None:
    references = [
        AdminImportSourceReferenceResponse(
            position=position,
            repository_side="keys" if position < 5_000 else "translations",
            repository_id=UUID(int=1 if position < 5_000 else 2),
            source_branch="next" if position < 5_000 else "master",
            commit_hash="a" * 40,
            path=f"synthetic/source-{position}.kt",
            size_bytes=100,
            sha256="b" * 64,
        )
        for position in range(count)
    ]
    if count > 5_500:
        with pytest.raises(ValidationError, match="at most 5500 items"):
            AdminImportBaselineResponse(imported_at=datetime.now(UTC), source_references=references)
    else:
        response = AdminImportBaselineResponse(
            imported_at=datetime.now(UTC), source_references=references
        )
        assert len(response.model_dump(mode="json")["source_references"]) == count
