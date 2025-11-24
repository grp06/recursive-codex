import os
from pathlib import Path

from enhancement_core.config.runtime import (
    DEFAULT_FEEDBACK_PROMPT,
    FeedbackSettings,
    HostBridgeSettings,
    PipelineSettings,
    RouterSettings,
    ScreenshotSettings,
)


def load_environment_file(path: Path | None = None) -> None:
    candidate = path or Path(".env")
    if not candidate.exists():
        return
    for raw in candidate.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = value.strip()


__all__ = [
    "DEFAULT_FEEDBACK_PROMPT",
    "FeedbackSettings",
    "HostBridgeSettings",
    "PipelineSettings",
    "RouterSettings",
    "ScreenshotSettings",
    "load_environment_file",
]
