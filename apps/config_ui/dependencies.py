from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path

from enhancement_core.config_store import ConfigSchema, EnvStore, PipelineOverridesStore
from enhancement_core.logging import configure_logging
from fastapi import FastAPI

from .config import ConfigUIConfig, get_config


@lru_cache
def _get_config() -> ConfigUIConfig:
    return get_config()


def get_schema() -> ConfigSchema:
    return _get_config().schema


def get_project_root() -> Path:
    return _get_config().project_root


def get_env_store() -> EnvStore:
    return EnvStore(get_project_root() / ".env")


def get_env_example_store() -> EnvStore:
    return EnvStore(get_project_root() / ".env.example")


def get_pipeline_overrides_store() -> PipelineOverridesStore:
    return PipelineOverridesStore(get_project_root() / "config/pipeline_overrides.json")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging("config_ui")
    yield


__all__ = [
    "get_schema",
    "get_project_root",
    "get_env_store",
    "get_env_example_store",
    "get_pipeline_overrides_store",
    "lifespan",
]
