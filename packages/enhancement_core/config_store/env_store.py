from __future__ import annotations

import hashlib
import os
from collections import OrderedDict
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass
class EnvEntry:
    raw: str
    key: str | None = None
    value: str | None = None


@dataclass
class EnvSnapshot:
    values: OrderedDict[str, str]
    entries: list[EnvEntry]
    digest: str
    mtime: float | None


class EnvStoreError(RuntimeError):
    pass


class EnvVersionConflictError(EnvStoreError):
    pass


class EnvStore:
    def __init__(self, path: Path):
        self.path = path

    def load(self) -> EnvSnapshot:
        text = self._read_text()
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        entries, values = self._parse(text)
        mtime = self.path.stat().st_mtime if self.path.exists() else None
        return EnvSnapshot(values=values, entries=entries, digest=digest, mtime=mtime)

    def save(self, updates: dict[str, str], expected_digest: str | None = None) -> EnvSnapshot:
        current = self.load()
        if expected_digest and current.digest != expected_digest:
            raise EnvVersionConflictError(".env file changed on disk")
        content = self._render(current.entries, updates)
        self._write_text(content)
        return self.load()

    def overwrite(self, content: str, expected_digest: str | None = None) -> EnvSnapshot:
        current = self.load()
        if expected_digest and current.digest != expected_digest:
            raise EnvVersionConflictError(".env file changed on disk")
        normalized = content if not content or content.endswith("\n") else content + "\n"
        self._write_text(normalized)
        return self.load()

    def _read_text(self) -> str:
        if not self.path.exists():
            return ""
        try:
            return self.path.read_text(encoding="utf-8")
        except OSError as exc:
            raise EnvStoreError(f"unable to read {self.path}") from exc

    def _write_text(self, content: str) -> None:
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path.write_text(content, encoding="utf-8")
            try:
                os.replace(tmp_path, self.path)
            except OSError:
                # Fallback for bind-mounted files (e.g. Docker) where replace fails
                self.path.write_text(content, encoding="utf-8")
        except OSError as exc:
            raise EnvStoreError(f"unable to write {self.path}") from exc
        finally:
            with suppress(OSError):
                tmp_path.unlink(missing_ok=True)

    def _parse(self, text: str) -> tuple[list[EnvEntry], OrderedDict[str, str]]:
        entries: list[EnvEntry] = []
        values: OrderedDict[str, str] = OrderedDict()
        if not text:
            return entries, values
        for line in text.splitlines():
            entry = self._parse_line(line)
            entries.append(entry)
            if entry.key:
                values[entry.key] = entry.value or ""
        return entries, values

    def _parse_line(self, line: str) -> EnvEntry:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            return EnvEntry(raw=line)
        key, value = line.split("=", 1)
        key = key.strip()
        return EnvEntry(raw=line, key=key, value=value)

    def _render(self, entries: Iterable[EnvEntry], updates: dict[str, str]) -> str:
        pending = {key: str(value) for key, value in updates.items()}
        lines: list[str] = []
        for entry in entries:
            if entry.key and entry.key in pending:
                lines.append(f"{entry.key}={pending.pop(entry.key)}")
            else:
                lines.append(entry.raw)
        if pending:
            if lines and lines[-1] != "":
                lines.append("")
            for key, value in pending.items():
                lines.append(f"{key}={value}")
        rendered = "\n".join(lines)
        if rendered and not rendered.endswith("\n"):
            rendered += "\n"
        return rendered


__all__ = ["EnvStore", "EnvSnapshot", "EnvEntry", "EnvStoreError", "EnvVersionConflictError"]
