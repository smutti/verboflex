"""Closed administrator contracts for candidate-owned repository mappings."""

from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from verboflex.integrations.bitbucket.urls import validate_localization_root
from verboflex.localization.code_keys.catalog import CodeSourceConfig

LocalizationRoot = Annotated[
    str, Field(max_length=4096), AfterValidator(validate_localization_root)
]


class AdminDirectMappingWriteRequest(BaseModel):
    """Create or replace one direct mapping under candidate-version authority."""

    model_config = ConfigDict(extra="forbid")

    topology: Literal["direct"]
    repository_id: UUID
    localization_root: LocalizationRoot | None = None
    source_branch: Annotated[str, Field(min_length=1, max_length=255)]
    allowed_target_branches: Annotated[list[str], Field(min_length=1, max_length=100)]
    default_target_branch: Annotated[str, Field(min_length=1, max_length=255)]
    expected_candidate_version: Annotated[int, Field(ge=1)]


class AdminSeparateMappingSideWriteRequest(BaseModel):
    """One closed explicit side of a separate mapping."""

    model_config = ConfigDict(extra="forbid")

    role: Literal["keys", "translations"]
    repository_id: UUID
    localization_root: LocalizationRoot | None = None
    source_branch: Annotated[str, Field(min_length=1, max_length=255)]


class AdminSeparateMappingWriteRequest(BaseModel):
    """Create or replace one mapping with exact Keys and Translations sides."""

    model_config = ConfigDict(extra="forbid")

    topology: Literal["separate"]
    code_source: CodeSourceConfig | None = None
    sides: Annotated[
        list[AdminSeparateMappingSideWriteRequest],
        Field(min_length=2, max_length=2),
    ]
    allowed_target_branches: Annotated[list[str], Field(min_length=1, max_length=100)]
    default_target_branch: Annotated[str, Field(min_length=1, max_length=255)]
    expected_candidate_version: Annotated[int, Field(ge=1)]

    @model_validator(mode="after")
    def require_exact_roles(self) -> Self:
        if {side.role for side in self.sides} != {"keys", "translations"}:
            raise ValueError("separate requires exact keys and translations sides")
        return self


AdminMappingWriteRequest = Annotated[
    AdminDirectMappingWriteRequest | AdminSeparateMappingWriteRequest,
    Field(discriminator="topology"),
]


class AdminMappingResponse(BaseModel):
    """One lifecycle-free direct or separate mapping projection."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    topology: Literal["direct", "separate"]
    primary_repository_id: UUID
    primary_source_branch: str
    translations_repository_id: UUID | None
    translations_source_branch: str | None
    allowed_target_branches: list[str]
    default_target_branch: str
    selected_layout_candidate_id: UUID | None
    selected_layout_version: int | None
    candidate_version: int
    code_source: CodeSourceConfig | None = None
    primary_localization_root: str | None = None
    translations_localization_root: str | None = None


class AdminMappingListResponse(BaseModel):
    """One bounded exact-order candidate mapping page."""

    model_config = ConfigDict(extra="forbid")

    items: list[AdminMappingResponse]
    next_cursor: str | None


class AdminMappingConflictResponse(BaseModel):
    """Form-addressable candidate mapping conflict."""

    model_config = ConfigDict(extra="forbid")

    detail: str
    field: Literal[
        "mapping_identity",
        "candidate_version",
        "source_branch",
        "keys_source_branch",
        "translations_source_branch",
        "allowed_target_branches",
    ]
