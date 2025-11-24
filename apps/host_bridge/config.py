from dataclasses import dataclass

from enhancement_core.config import HostBridgeSettings


@dataclass
class HostBridgeConfig:
    settings: HostBridgeSettings


def get_config() -> HostBridgeConfig:
    return HostBridgeConfig(settings=HostBridgeSettings())


__all__ = ["HostBridgeConfig", "get_config"]
