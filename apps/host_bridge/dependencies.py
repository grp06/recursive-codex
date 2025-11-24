from functools import lru_cache

from enhancement_core.codex import CodexRunner
from enhancement_core.config import HostBridgeSettings

from .config import HostBridgeConfig, get_config


@lru_cache
def get_host_settings(config: HostBridgeConfig | None = None) -> HostBridgeSettings:
    cfg = config or get_config()
    return cfg.settings


_runner: CodexRunner | None = None


def get_runner() -> CodexRunner:
    global _runner
    if _runner is None:
        _runner = CodexRunner(get_host_settings())
    return _runner


__all__ = ["get_host_settings", "get_runner"]
