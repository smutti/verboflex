"""Data-only Qt screenshot manifests. Executable runners are operator-owned."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from verboflex.integrations.bitbucket.urls import validate_repository_relative_path

MANIFEST_PATH = ".verboflex/qt-screenshots.json"
MAX_MANIFEST_BYTES = 1_048_576
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class QtScenario(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: Annotated[str, Field(pattern=r"^[a-zA-Z0-9_.-]{1,128}$")]
    label: Annotated[str, Field(min_length=1, max_length=128)]
    context: Annotated[str, Field(min_length=1, max_length=512)]
    source: Annotated[str, Field(min_length=1, max_length=65536)]
    disambiguation: Annotated[str, Field(max_length=512)] = ""


class QtManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    version: Literal[1] = 1
    runner_profile: Annotated[str, Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")]
    width: Annotated[int, Field(ge=1, le=4096)]
    height: Annotated[int, Field(ge=1, le=4096)]
    qt_version: Annotated[str, Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")]
    platform: Literal["offscreen", "linuxfb", "eglfs"]
    sources: Annotated[dict[str, Digest], Field(min_length=1, max_length=500)]
    scenarios: Annotated[tuple[QtScenario, ...], Field(min_length=1, max_length=100)]

    @model_validator(mode="after")
    def unique_and_safe(self) -> QtManifest:
        if len({s.id for s in self.scenarios}) != len(self.scenarios):
            raise ValueError("Duplicate Qt scenario")
        for path in self.sources:
            validate_repository_relative_path(path)
        return self
