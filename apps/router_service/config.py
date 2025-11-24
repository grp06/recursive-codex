from dataclasses import dataclass

from enhancement_core.config import RouterSettings


@dataclass
class RouterServiceConfig:
    settings: RouterSettings


def get_config() -> RouterServiceConfig:
    return RouterServiceConfig(settings=RouterSettings())


__all__ = ["RouterServiceConfig", "get_config"]
