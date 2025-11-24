from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache

import httpx
from enhancement_core.config import RouterSettings
from fastapi import FastAPI

from .config import RouterServiceConfig, get_config

_client: httpx.AsyncClient | None = None


@lru_cache
def get_router_settings(config: RouterServiceConfig | None = None) -> RouterSettings:
    cfg = config or get_config()
    return cfg.settings


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    global _client
    settings = get_router_settings()
    _client = httpx.AsyncClient(timeout=settings.request_timeout)
    try:
        yield
    finally:
        if _client is not None:
            await _client.aclose()
            _client = None


def get_http_client() -> httpx.AsyncClient:
    if _client is None:
        raise RuntimeError("http client not initialized")
    return _client


__all__ = ["get_http_client", "get_router_settings", "lifespan"]
