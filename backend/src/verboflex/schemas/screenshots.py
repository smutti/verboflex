"""Authenticated code context and on-demand screenshot contracts."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from verboflex.localization.code_keys.catalog import CodeOccurrence, CodePreview


class ScreenshotRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    engine: Literal["compose", "web"] = "compose"
    preview_function: Annotated[str, Field(min_length=1, max_length=512)] | None = None
    scenario_id: Annotated[str, Field(min_length=1, max_length=128)] | None = None
    target_value_id: UUID | None = None
    viewport: Literal["desktop", "mobile"] = "desktop"
    theme: Literal["light", "dark"] = "light"
    proposal_version: Annotated[int, Field(ge=1)] | None = None

    @model_validator(mode="after")
    def engine_request(self) -> ScreenshotRequest:
        if self.engine == "compose":
            if (
                not self.preview_function
                or self.scenario_id
                or self.target_value_id
                or self.viewport != "desktop"
            ):
                raise ValueError("Compose requests require only a preview function")
        elif (
            self.preview_function
            or not self.scenario_id
            or not self.target_value_id
            or self.theme != "light"
        ):
            raise ValueError("Web requests require a scenario, exact value and light appearance")
        return self

    def as_payload(self) -> dict[str, object]:
        result = self.model_dump(mode="json")
        if self.engine == "compose":
            return {key: result[key] for key in ("preview_function", "theme", "proposal_version")}
        return result


class WebCaptureTarget(BaseModel):
    value_id: UUID
    runtime_key: str
    json_path: list[str]
    scenario_ids: list[str]


class ScreenshotRegion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    x: Annotated[float, Field(ge=0, le=1)]
    y: Annotated[float, Field(ge=0, le=1)]
    width: Annotated[float, Field(gt=0, le=1)]
    height: Annotated[float, Field(gt=0, le=1)]

    @model_validator(mode="after")
    def inside_image(self) -> ScreenshotRegion:
        if self.x + self.width > 1.000001 or self.y + self.height > 1.000001:
            raise ValueError("Text region extends outside the image")
        return self


class ScreenshotLocation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["found", "not_found", "ambiguous", "unavailable"]
    regions: Annotated[list[ScreenshotRegion], Field(max_length=20)] = []

    @model_validator(mode="after")
    def evidence(self) -> ScreenshotLocation:
        if (self.status == "found") != bool(self.regions):
            raise ValueError("Only a located text can have regions")
        return self


class WebCaptureReceipt(BaseModel):
    render_id: UUID
    rendered_at: datetime
    model_config = ConfigDict(extra="forbid")
    engine: Literal["web"]
    version: Literal[1]
    input_digest: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    image_digest: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    commit: Annotated[str, Field(pattern=r"^[a-f0-9]{40,64}$")]
    scenario_id: str
    language: str
    viewport: Literal["desktop", "mobile"]
    manifest_digest: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    source_digest: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    location: ScreenshotLocation
    text: Annotated[str, Field(max_length=65536)]


class ScreenshotResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)
    id: UUID
    state: Literal["queued", "rendering", "succeeded", "failed", "cancelled", "expired"]
    request: ScreenshotRequest
    input_digest: str
    image_digest: str | None
    error_code: str | None
    created_at: datetime
    expires_at: datetime
    location: ScreenshotLocation | None = None
    receipt: WebCaptureReceipt | None = None


class ScreenScenario(BaseModel):
    preview_function: str = ""
    scenario_id: str | None = Field(default=None, exclude_if=lambda value: value is None)
    label: str
    explicit: bool


class ScreenshotPage(BaseModel):
    items: list[ScreenshotResponse]
    next_cursor: UUID | None


class CodeContextResponse(BaseModel):
    configured: bool
    engine: Literal["compose", "web"] = "compose"
    web_targets: list[WebCaptureTarget] = []
    diagnostics: list[str] = []
    occurrences: list[CodeOccurrence]
    previews: list[CodePreview]
    capture_functions: list[str]
    code_commit: str | None = None
    occurrences_truncated: bool = False
    scenarios: list[ScreenScenario] = []


class CodeCatalogEntry(BaseModel):
    key: str
    missing_translation: bool
    missing_base: bool


class CodeCatalogPage(BaseModel):
    items: list[CodeCatalogEntry]
    next_cursor: str | None
    orphan_count: int


class CodeSourceSummary(BaseModel):
    scope_id: UUID
    mapping_id: UUID
    key_count: int
    missing_count: int


class CodeSourcePage(BaseModel):
    items: list[CodeSourceSummary]
    next_cursor: UUID | None
