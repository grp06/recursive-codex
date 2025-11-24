from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from enhancement_core.config_store import ConfigSchema, load_config_schema


@dataclass
class ConfigUIConfig:
    project_root: Path
    schema: ConfigSchema


def _discover_project_root() -> Path:
    env_root = os.getenv("CONFIG_UI_PROJECT_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()
    return Path(__file__).resolve().parents[2]


def get_config() -> ConfigUIConfig:
    root = _discover_project_root()
    schema = load_config_schema(root / "config/frontend_config_schema.json")
    return ConfigUIConfig(project_root=root, schema=schema)


__all__ = ["ConfigUIConfig", "get_config"]
