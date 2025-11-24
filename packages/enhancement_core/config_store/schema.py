from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


class ConfigOption(BaseModel):
    value: Any
    label: str


class ConfigField(BaseModel):
    key: str
    label: str
    target: Literal["env", "cli"]
    group: str
    control: str
    sensitive: bool = False
    required: bool = False
    services: list[str] = Field(default_factory=list)
    validation: dict[str, Any] = Field(default_factory=dict)
    options: list[ConfigOption] = Field(default_factory=list)
    help: str | None = None
    default: Any = None
    default_source: str | None = None
    cli_flag: str | None = None
    path_mode: str | None = None


class ConfigGroup(BaseModel):
    id: str
    label: str
    description: str | None = None
    default_expanded: bool = False


class ConfigSchema(BaseModel):
    version: int
    updated: str
    groups: list[ConfigGroup]
    fields: list[ConfigField]


def load_config_schema(path: Path | None = None) -> ConfigSchema:
    schema_path = path or Path("config/frontend_config_schema.json")
    try:
        payload = schema_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"unable to read schema {schema_path}") from exc
    data = json.loads(payload)
    return ConfigSchema(**data)


__all__ = [
    "ConfigField",
    "ConfigGroup",
    "ConfigOption",
    "ConfigSchema",
    "load_config_schema",
]
