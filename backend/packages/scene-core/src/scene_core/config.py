import os
import re
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

from .contracts import STAGES


def expand_environment(path, keep_unset=False):
    """Unset or empty ${VAR} values expand to nothing, or stay literal so validation can name them."""
    return re.sub(
        r"\$\{(\w+)\}",
        lambda m: os.environ.get(m.group(1)) or (m.group(0) if keep_unset else ""),
        Path(path).read_text(),
    )


class StageConfig(BaseModel):
    algorithm: str
    params: dict = Field(default_factory=dict)


class PipelineConfig(BaseModel):
    """Every Stage runs on the one Target (ADR-0005), usually named through ${GPU_TARGET}; an unset variable
    stays literal so open_target_workspace can name it."""

    target: str = "cpu"
    stages: dict[str, StageConfig]

    @model_validator(mode="after")
    def validate_stages(self):
        if tuple(self.stages) != STAGES:
            raise ValueError("Pipeline must declare all nine stages in order")
        return self

    @classmethod
    def load(cls, path):
        return cls.model_validate(yaml.safe_load(expand_environment(path, keep_unset=True)))


class TargetConfig(BaseModel):
    backend: str = "inprocess"
    url: str | None = None
    token: str = ""
    headers: dict[str, str] = Field(default_factory=dict)
    chunk_size: int = 25 * 1024 * 1024
    # Files an upload or a Publication moves at once; each request waits out the Target's round trip.
    transfer_concurrency: int = Field(8, ge=1)
    timeout: float = 29.0
    startup_timeout: float = 900
    poll_interval: float = 1

    @property
    def missing_url(self):
        return self.backend == "http" and not self.url

    @field_validator("url", mode="before")
    @classmethod
    def blank_url(cls, value):
        return value or None

    @field_validator("token", mode="before")
    @classmethod
    def blank_token(cls, value):
        return value or ""

    @field_validator("headers", mode="before")
    @classmethod
    def strip_headers(cls, value):
        return {k: str(v or "").strip() for k, v in (value or {}).items()}


class ComputeConfig(BaseModel):
    targets: dict[str, TargetConfig] = Field(default_factory=lambda: {"cpu": TargetConfig()})

    @classmethod
    def load(cls, path):
        return cls.model_validate(yaml.safe_load(expand_environment(path)))
