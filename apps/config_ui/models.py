from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class VersionPayload(BaseModel):
    env: str | None = None
    overrides: str | None = None


class ConfigUpdatePayload(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)
    versions: VersionPayload


class ConfigValidatePayload(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)


class EnvUploadPayload(BaseModel):
    content: str
    digest: str


class ErrorDetail(BaseModel):
    field: str | None = None
    message: str


__all__ = [
    "ConfigUpdatePayload",
    "ConfigValidatePayload",
    "EnvUploadPayload",
    "ErrorDetail",
    "VersionPayload",
]
