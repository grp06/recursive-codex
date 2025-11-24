from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, field_validator

_ALLOWED_EFFORT = {"low", "medium", "high"}


class PipelineOverrides(BaseModel):
    iterations: int = 1
    model: str | None = None
    model_reasoning_effort: str | None = None
    demo: bool = False
    artifacts_dir: str | None = None

    @field_validator("iterations")
    @classmethod
    def validate_iterations(cls, value: int) -> int:
        if value < 1:
            raise ValueError("iterations must be at least 1")
        return value

    @field_validator("model_reasoning_effort")
    @classmethod
    def validate_effort(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if value not in _ALLOWED_EFFORT:
            raise ValueError("invalid reasoning effort")
        return value


@dataclass
class PipelineOverridesSnapshot:
    overrides: PipelineOverrides
    digest: str
    mtime: float | None


class PipelineOverridesError(RuntimeError):
    pass


class PipelineOverridesVersionError(PipelineOverridesError):
    pass


class PipelineOverridesStore:
    def __init__(self, path: Path | None = None):
        self.path = path or Path("config/pipeline_overrides.json")

    def load(self) -> PipelineOverridesSnapshot:
        text = self._read_or_initialize()
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        data = json.loads(text) if text else {}
        overrides = PipelineOverrides(**data)
        mtime = self.path.stat().st_mtime if self.path.exists() else None
        return PipelineOverridesSnapshot(overrides=overrides, digest=digest, mtime=mtime)

    def save(self, updates: dict[str, Any], expected_digest: str | None = None) -> PipelineOverridesSnapshot:
        current = self.load()
        if expected_digest and current.digest != expected_digest:
            raise PipelineOverridesVersionError("pipeline overrides changed on disk")
        data = current.overrides.model_dump()
        for key, value in updates.items():
            data[key] = value
        overrides = PipelineOverrides(**data)
        payload = json.dumps(overrides.model_dump(), indent=2, sort_keys=True)
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path.write_text(payload + "\n", encoding="utf-8")
            os.replace(tmp_path, self.path)
        except OSError as exc:
            raise PipelineOverridesError(f"unable to write {self.path}") from exc
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass
        return self.load()

    def _read_or_initialize(self) -> str:
        if self.path.exists():
            try:
                return self.path.read_text(encoding="utf-8")
            except OSError as exc:
                raise PipelineOverridesError(f"unable to read {self.path}") from exc
        overrides = PipelineOverrides()
        payload = json.dumps(overrides.model_dump(), indent=2, sort_keys=True)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(payload + "\n", encoding="utf-8")
        except OSError as exc:
            raise PipelineOverridesError(f"unable to initialize {self.path}") from exc
        return payload + "\n"


__all__ = [
    "PipelineOverrides",
    "PipelineOverridesStore",
    "PipelineOverridesSnapshot",
    "PipelineOverridesError",
    "PipelineOverridesVersionError",
]
