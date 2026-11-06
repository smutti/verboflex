"""Versioned, data-only web scenarios. Operator profiles own executable commands."""

from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

from verboflex.integrations.bitbucket.urls import validate_repository_relative_path

Short = Annotated[str, Field(min_length=1, max_length=512)]


class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class WebCaptureConfig(Closed):
    catalog_url_prefix: Annotated[str, Field(pattern=r"^/(?:[a-zA-Z0-9_-]+/)+$")] = "/assets/i18n/"
    manifest_path: Short
    application_root: str | None = None
    source_roots: Annotated[tuple[str, ...], Field(min_length=1, max_length=10)] = ("src/app",)
    source_excludes: Annotated[tuple[str, ...], Field(max_length=30)] = ()
    runner_profile: Annotated[str, Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")]
    marker: Annotated[str, Field(pattern=r"^[a-zA-Z_$][a-zA-Z0-9_$]{0,63}$")] = "_"

    @model_validator(mode="after")
    def paths(self) -> WebCaptureConfig:
        for path in (self.manifest_path, *self.source_roots, *self.source_excludes):
            validate_repository_relative_path(path)
        if self.application_root is not None:
            validate_repository_relative_path(self.application_root)
            if any(
                not p.startswith(self.application_root + "/")
                for p in (self.manifest_path, *self.source_roots)
            ):
                raise ValueError("Web sources must be within the application root")
        if len(set(self.source_roots)) != len(self.source_roots):
            raise ValueError("Duplicate source roots")
        return self


class WebAction(Closed):
    action: Literal["click", "fill", "blur", "wait", "assert_disabled", "assert_enabled"]
    selector: Short
    value: Annotated[str, Field(max_length=4096)] | None = None

    @model_validator(mode="after")
    def fill_value(self) -> WebAction:
        if (self.action == "fill") != (self.value is not None):
            raise ValueError("Only fill actions require a value")
        return self


class WebTarget(Closed):
    attribute: Literal["placeholder"] | None = None
    key: Short
    selector: Short


class WebResponse(Closed):
    path: Short
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = "GET"
    status: Annotated[int, Field(ge=200, le=599)] = 200
    body: JsonValue

    @field_validator("path")
    @classmethod
    def local_api(cls, value: str) -> str:
        parts = urlsplit(value)
        if (
            not value.startswith("/api/")
            or parts.scheme
            or parts.netloc
            or parts.fragment
            or "\\" in value
            or any(ord(c) < 32 for c in value)
        ):
            raise ValueError("Fixtures must address local API routes")
        return value


class WebScenario(Closed):
    id: Annotated[str, Field(pattern=r"^[a-zA-Z0-9_.-]{1,128}$")]
    label: Annotated[str, Field(min_length=1, max_length=128)]
    route: Short
    ready: Short
    actions: Annotated[tuple[WebAction, ...], Field(max_length=30)] = ()
    targets: Annotated[tuple[WebTarget, ...], Field(min_length=1, max_length=100)]
    responses: Annotated[tuple[WebResponse, ...], Field(max_length=100)] = ()

    @model_validator(mode="after")
    def safe(self) -> WebScenario:
        if (
            not self.route.startswith(("#/", "/"))
            or self.route.startswith("//")
            or "\\" in self.route
            or any(ord(c) < 32 for c in self.route)
        ):
            raise ValueError("Scenario route must be local")
        if len({t.key for t in self.targets}) != len(self.targets):
            raise ValueError("Duplicate scenario target")
        if len({(r.method, r.path) for r in self.responses}) != len(self.responses):
            raise ValueError("Duplicate API fixture")
        return self


class WebManifest(Closed):
    version: Literal[1] = 1
    scenarios: Annotated[tuple[WebScenario, ...], Field(min_length=1, max_length=100)]

    @model_validator(mode="after")
    def unique(self) -> WebManifest:
        if len({s.id for s in self.scenarios}) != len(self.scenarios):
            raise ValueError("Duplicate scenario ID")
        return self


class WebUsage(Closed):
    key: str | None
    path: Short
    line: Annotated[int, Field(ge=1)]
    kind: Literal["pipe", "instant", "get", "marker", "dynamic"]


class WebUsageIndex(Closed):
    occurrences: Annotated[list[WebUsage], Field(max_length=50000)]
