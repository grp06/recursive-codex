import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache

from enhancement_core.config import ScreenshotSettings
from enhancement_core.screenshots.capture import capture_full_page
from fastapi import FastAPI
from playwright.async_api import Browser, async_playwright

from .config import get_config


class ScreenshotCaptureRunner:
    def __init__(self, settings: ScreenshotSettings):
        self.settings = settings
        self._playwright = None
        self._browser: Browser | None = None
        self._lock = asyncio.Lock()

    async def start(self):
        if self._playwright is None:
            self._playwright = await async_playwright().start()
        if self._browser is None:
            self._browser = await self._playwright.chromium.launch(headless=True)

    async def capture(self):
        async with self._lock:
            if self._browser is None:
                await self.start()
            return await capture_full_page(self.settings, browser=self._browser)

    async def stop(self):
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None


@lru_cache
def get_settings() -> ScreenshotSettings:
    cfg = get_config()
    return cfg.settings


_runner: ScreenshotCaptureRunner | None = None


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    global _runner
    settings = get_settings()
    _runner = ScreenshotCaptureRunner(settings)
    await _runner.start()
    try:
        yield
    finally:
        await _runner.stop()
        _runner = None


def get_capture_runner() -> ScreenshotCaptureRunner:
    if _runner is None:
        raise RuntimeError("screenshot capture runner unavailable")
    return _runner


__all__ = ["ScreenshotCaptureRunner", "get_capture_runner", "get_settings", "lifespan"]
