"""Closed administrator contracts for versioned product configuration."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from verboflex.schemas.translations import LanguageCode


class AdminProductCreateRequest(BaseModel):
    """Create one stable product identity and its initial candidate revision."""

    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(min_length=1, max_length=1000)]
    description: str | None = None


class AdminProductUpdateRequest(BaseModel):
    """Compare and save the current candidate configuration."""

    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(min_length=1, max_length=1000)]
    description: str | None = None
    expected_candidate_version: Annotated[int, Field(ge=1)]


class AdminProductPublishRequest(BaseModel):
    """Publish one exact candidate under optimistic version authority."""

    model_config = ConfigDict(extra="forbid")

    candidate_revision_id: UUID
    expected_candidate_version: Annotated[int, Field(ge=1)]


class AdminProductReactivateRequest(BaseModel):
    """Reactivate one exact published revision under version authority."""

    model_config = ConfigDict(extra="forbid")

    active_revision_id: UUID
    expected_active_version: Annotated[int, Field(ge=1)]


class AdminProductRevisionSummary(BaseModel):
    """Bounded active or candidate revision projection."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    version: int
    name: str
    description: str | None
    is_published: bool


class AdminProductResponse(BaseModel):
    """Stable product identity with explicitly separate revision states."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    name: str
    is_active: bool
    affected_mapping_count: Annotated[int, Field(ge=0)]
    active_revision: AdminProductRevisionSummary | None
    candidate_revision: AdminProductRevisionSummary | None


class AdminProductListResponse(BaseModel):
    """One bounded stable keyset page of products."""

    model_config = ConfigDict(extra="forbid")

    items: list[AdminProductResponse]
    next_cursor: str | None


class AdminProductLanguageCoverage(BaseModel):
    """Logical target strings for one language found in successful imports."""

    model_config = ConfigDict(extra="forbid")

    language: LanguageCode
    expected_count: Annotated[int, Field(ge=0)]
    translated_count: Annotated[int, Field(ge=0)]
    missing_count: Annotated[int, Field(ge=0)]
    coverage_percent: Annotated[float, Field(ge=0, le=100)] | None


class AdminProductSummaryResponse(BaseModel):
    """Repository coverage, independent of proposal and approval workflow state."""

    model_config = ConfigDict(extra="forbid")

    product_id: UUID
    source_string_count: Annotated[int, Field(ge=0)]
    target_language_count: Annotated[int, Field(ge=0)]
    expected_translation_count: Annotated[int, Field(ge=0)]
    translated_count: Annotated[int, Field(ge=0)]
    missing_count: Annotated[int, Field(ge=0)]
    coverage_percent: Annotated[float, Field(ge=0, le=100)] | None
    imported_scope_count: Annotated[int, Field(ge=0)]
    unimported_scope_count: Annotated[int, Field(ge=0)]
    last_imported_at: datetime | None
    languages: Annotated[list[AdminProductLanguageCoverage], Field(max_length=500)]
    languages_has_more: bool


class AdminProductConflictResponse(BaseModel):
    """Bounded conflict with optional field affinity for form recovery."""

    model_config = ConfigDict(extra="forbid")

    detail: str
    field: Literal["name"] | None = None


AdminProductPublicationBlocker = Literal[
    "mappings_required",
    "mapping_configuration_invalid",
    "target_configuration_invalid",
    "layout_required",
    "preview_confirmation_required",
]


class AdminProductLifecycleConflictResponse(BaseModel):
    """Stable lifecycle conflict with a closed ordered blocker vocabulary."""

    model_config = ConfigDict(extra="forbid")

    detail: Literal[
        "Product lifecycle conflict",
        "Product publication blocked",
    ]
    blockers: list[AdminProductPublicationBlocker]


class AdminProductDeletionConflictResponse(BaseModel):
    """Closed reason why logical deletion cannot start yet."""

    model_config = ConfigDict(extra="forbid")

    detail: Literal["Product deletion blocked"]
    blockers: list[Literal["active_work"]]


AdminProductStatus = Literal["active", "inactive"]


AdminProductReactivationBlocker = Literal[
    "product_active",
    "candidate_revision_present",
    "mappings_required",
    "mapping_configuration_invalid",
    "layout_required",
    "revalidation_confirmation_required",
]


class AdminProductReactivationMappingResponse(BaseModel):
    """Bounded currentness projection for one published mapping."""

    model_config = ConfigDict(extra="forbid")

    mapping_id: UUID
    is_current: bool
    blocker_codes: Annotated[
        list[AdminProductReactivationBlocker],
        Field(max_length=6),
    ]


class AdminProductReactivationEligibilityResponse(BaseModel):
    """Exact active-revision recovery state without configuration contents."""

    model_config = ConfigDict(extra="forbid")

    product_id: UUID
    active_revision_id: UUID
    active_revision_version: Annotated[int, Field(ge=1)]
    eligible: bool
    blocker_codes: Annotated[
        list[AdminProductReactivationBlocker],
        Field(max_length=6),
    ]
    mappings: Annotated[
        list[AdminProductReactivationMappingResponse],
        Field(max_length=500),
    ]
