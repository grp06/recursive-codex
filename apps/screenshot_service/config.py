from dataclasses import dataclass

from enhancement_core.config import ScreenshotSettings


@dataclass
class ScreenshotServiceConfig:
    settings: ScreenshotSettings


def get_config() -> ScreenshotServiceConfig:
    return ScreenshotServiceConfig(settings=ScreenshotSettings())


__all__ = ["ScreenshotServiceConfig", "get_config"]
