from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path
from typing import Any

from enhancement_core.config import FeedbackSettings, HostBridgeSettings, PipelineSettings, RouterSettings, ScreenshotSettings
from enhancement_core.config_store import (
    ConfigField,
    ConfigSchema,
    EnvStore,
    EnvStoreError,
    EnvSnapshot,
    EnvVersionConflictError,
    PipelineOverrides,
    PipelineOverridesError,
    PipelineOverridesSnapshot,
    PipelineOverridesStore,
    PipelineOverridesVersionError,
)
from enhancement_core.logging import request_context
from fastapi import Body, Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import ValidationError

from .dependencies import (
    get_env_example_store,
    get_env_store,
    get_pipeline_overrides_store,
    get_project_root,
    get_schema,
    lifespan,
)
from .models import ConfigUpdatePayload, ConfigValidatePayload, EnvUploadPayload, ErrorDetail

logger = logging.getLogger(__name__)
app = FastAPI(title="Config UI", version="0.1.0", lifespan=lifespan)
STATIC_DIR = Path(__file__).resolve().parent / "static"
_SETTINGS_CLASSES = [ScreenshotSettings, FeedbackSettings, RouterSettings, HostBridgeSettings, PipelineSettings]
_SKIP_HOST_PATH_CHECK = os.getenv("CONFIG_UI_SKIP_HOST_PATH_CHECK", "1").lower() not in {"0", "false", "no"}


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    with request_context(request_id):
        response = await call_next(request)
    response.headers["x-request-id"] = request_id
    response.headers["Access-Control-Allow-Origin"] = "http://localhost:8110"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    return response


def _load_example_values(example_store: EnvStore) -> dict[str, str]:
    try:
        snapshot = example_store.load()
    except EnvStoreError:
        return {}
    return dict(snapshot.values)


def _mask_secret(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def _textarea_from_env(field: ConfigField, value: str) -> str:
    if field.control != "textarea":
        return value
    return value.replace("\\n", "\n")


def _textarea_to_env(field: ConfigField, value: str) -> str:
    if field.control != "textarea":
        return value
    normalized = value.replace("\r\n", "\n")
    return normalized.replace("\n", "\\n")


def _build_defaults(schema: ConfigSchema, example_values: dict[str, str]) -> dict[str, Any]:
    defaults: dict[str, Any] = {}
    for field in schema.fields:
        if field.target == "env":
            defaults[field.key] = _textarea_from_env(field, example_values.get(field.key, field.default or ""))
        else:
            defaults[field.key] = field.default
    return defaults


def _build_values(
    schema: ConfigSchema,
    env_snapshot: EnvSnapshot,
    overrides_snapshot: PipelineOverridesSnapshot,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    values: dict[str, Any] = {}
    secrets: dict[str, dict[str, Any]] = {}
    env_values = dict(env_snapshot.values)
    overrides = overrides_snapshot.overrides.model_dump()
    for field in schema.fields:
        if field.target == "env":
            raw_value = env_values.get(field.key, "")
            if field.sensitive:
                secrets[field.key] = {
                    "present": bool(raw_value),
                    "preview": _mask_secret(raw_value.strip()),
                }
                values[field.key] = None
            else:
                values[field.key] = _textarea_from_env(field, raw_value)
        else:
            values[field.key] = overrides.get(field.key)
    return values, secrets


def _collect_env_updates(schema: ConfigSchema, payload: dict[str, Any]) -> dict[str, str]:
    updates: dict[str, str] = {}
    for field in schema.fields:
        if field.target != "env":
            continue
        if field.key not in payload:
            continue
        incoming = payload[field.key]
        if field.sensitive and incoming is None:
            continue
        if isinstance(incoming, str):
            value = incoming
        elif incoming is None:
            value = ""
        else:
            value = str(incoming)
        value = _textarea_to_env(field, value)
        updates[field.key] = value
    return updates


def _collect_override_updates(schema: ConfigSchema, payload: dict[str, Any]) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    for field in schema.fields:
        if field.target != "cli":
            continue
        if field.key not in payload:
            continue
        updates[field.key] = payload[field.key]
    return updates


def _settings_payload(cls, env_values: dict[str, str]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for name, field in cls.model_fields.items():
        alias = field.alias or name
        if alias in env_values:
            payload[alias] = env_values[alias]
    return payload


def _translate_errors(errors: list[dict[str, Any]], cls, ignore_aliases: set[str] | None = None) -> list[ErrorDetail]:
    details: list[ErrorDetail] = []
    alias_map = {name: (field.alias or name) for name, field in cls.model_fields.items()}
    alias_values = set(alias_map.values())
    for item in errors:
        loc = item.get("loc", ())
        if loc and loc[0] in alias_values:
            field = loc[0]
            alias_name = field
        elif loc and loc[0] in alias_map:
            field = alias_map[loc[0]]
            alias_name = field
        else:
            first = loc[0] if loc else None
            field = first if isinstance(first, str) else None
            alias_name = field
        if ignore_aliases and alias_name in ignore_aliases:
            continue
        details.append(ErrorDetail(field=field, message=item.get("msg", "invalid value")))
    return details


def _validate_env(env_values: dict[str, str]) -> list[ErrorDetail]:
    errors: list[ErrorDetail] = []
    for cls in _SETTINGS_CLASSES:
        payload = _settings_payload(cls, env_values)
        try:
            cls.model_validate(payload)
        except ValidationError as exc:
            ignore: set[str] | None = None
            if _SKIP_HOST_PATH_CHECK and cls is HostBridgeSettings:
                ignore = {"TARGET_REPO_PATH"}
            translated = _translate_errors(exc.errors(), cls, ignore)
            if translated:
                errors.extend(translated)
    return errors


def _prepare_env_state(env_snapshot: EnvSnapshot, env_updates: dict[str, str]) -> dict[str, str]:
    state = dict(env_snapshot.values)
    state.update(env_updates)
    return state


def _validate_overrides(overrides_snapshot: PipelineOverridesSnapshot, updates: dict[str, Any]) -> list[ErrorDetail]:
    data = overrides_snapshot.overrides.model_dump()
    data.update(updates)
    try:
        PipelineOverrides(**data)
    except ValidationError as exc:
        return [ErrorDetail(field=str(err.get("loc", (None,))[0]), message=err.get("msg", "invalid value")) for err in exc.errors()]
    return []


def _versions_payload(env_snapshot: EnvSnapshot, overrides_snapshot: PipelineOverridesSnapshot) -> dict[str, Any]:
    return {
        "env": {"digest": env_snapshot.digest, "mtime": env_snapshot.mtime},
        "overrides": {"digest": overrides_snapshot.digest, "mtime": overrides_snapshot.mtime},
    }


def _fresh_snapshot(
    schema: ConfigSchema,
    env_store: EnvStore,
    overrides_store: PipelineOverridesStore,
    example_store: EnvStore,
) -> dict[str, Any]:
    env_snapshot = env_store.load()
    overrides_snapshot = overrides_store.load()
    defaults = _build_defaults(schema, _load_example_values(example_store))
    values, secrets = _build_values(schema, env_snapshot, overrides_snapshot)
    return {
        "schema": schema.model_dump(),
        "values": values,
        "defaults": defaults,
        "versions": _versions_payload(env_snapshot, overrides_snapshot),
        "secrets": secrets,
    }


@app.get("/api/config")
def read_config(
    schema: ConfigSchema = Depends(get_schema),
    env_store: EnvStore = Depends(get_env_store),
    overrides_store: PipelineOverridesStore = Depends(get_pipeline_overrides_store),
    example_store: EnvStore = Depends(get_env_example_store),
):
    return _fresh_snapshot(schema, env_store, overrides_store, example_store)


def _apply_updates(
    payload: ConfigUpdatePayload,
    schema: ConfigSchema,
    env_store: EnvStore,
    overrides_store: PipelineOverridesStore,
    example_store: EnvStore,
) -> dict[str, Any]:
    env_snapshot = env_store.load()
    overrides_snapshot = overrides_store.load()
    env_updates = _collect_env_updates(schema, payload.values)
    override_updates = _collect_override_updates(schema, payload.values)
    env_state = _prepare_env_state(env_snapshot, env_updates)
    errors = _validate_env(env_state)
    errors.extend(_validate_overrides(overrides_snapshot, override_updates))
    if errors:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"errors": [e.model_dump() for e in errors]})
    if env_updates:
        expected_env = payload.versions.env
        if not expected_env:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"message": "env version missing"})
        try:
            env_store.save(env_updates, expected_digest=expected_env)
        except EnvVersionConflictError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"message": str(exc)}) from exc
        except EnvStoreError as exc:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"message": str(exc)}) from exc
    if override_updates:
        expected_overrides = payload.versions.overrides
        if not expected_overrides:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"message": "overrides version missing"})
        try:
            overrides_store.save(override_updates, expected_digest=expected_overrides)
        except PipelineOverridesVersionError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"message": str(exc)}) from exc
        except PipelineOverridesError as exc:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"message": str(exc)}) from exc
    if env_updates or override_updates:
        logger.info(
            "config updated",
            extra={
                "env_keys": sorted(env_updates.keys()),
                "override_keys": sorted(override_updates.keys()),
                "secret_keys": [key for key in env_updates if key in {f.key for f in schema.fields if f.sensitive}],
            },
        )
    return _fresh_snapshot(schema, env_store, overrides_store, example_store)


@app.put("/api/config")
def update_config(
    payload: ConfigUpdatePayload = Body(...),
    schema: ConfigSchema = Depends(get_schema),
    env_store: EnvStore = Depends(get_env_store),
    overrides_store: PipelineOverridesStore = Depends(get_pipeline_overrides_store),
    example_store: EnvStore = Depends(get_env_example_store),
):
    return _apply_updates(payload, schema, env_store, overrides_store, example_store)


@app.post("/api/config/validate")
def validate_config(
    payload: ConfigValidatePayload = Body(...),
    schema: ConfigSchema = Depends(get_schema),
    env_store: EnvStore = Depends(get_env_store),
    overrides_store: PipelineOverridesStore = Depends(get_pipeline_overrides_store),
):
    env_snapshot = env_store.load()
    overrides_snapshot = overrides_store.load()
    env_updates = _collect_env_updates(schema, payload.values)
    override_updates = _collect_override_updates(schema, payload.values)
    env_state = _prepare_env_state(env_snapshot, env_updates)
    errors = _validate_env(env_state)
    errors.extend(_validate_overrides(overrides_snapshot, override_updates))
    if errors:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"errors": [e.model_dump() for e in errors]})
    return {
        "status": "ok",
        "versions": _versions_payload(env_snapshot, overrides_snapshot),
    }


@app.get("/api/env/file")
def download_env(env_store: EnvStore = Depends(get_env_store)):
    snapshot = env_store.load()
    path = env_store.path
    if not path.exists():
        return PlainTextResponse("", media_type="text/plain")
    return FileResponse(path, media_type="text/plain", filename=".env")


@app.post("/api/env/file")
def upload_env(
    payload: EnvUploadPayload = Body(...),
    env_store: EnvStore = Depends(get_env_store),
    schema: ConfigSchema = Depends(get_schema),
    overrides_store: PipelineOverridesStore = Depends(get_pipeline_overrides_store),
    example_store: EnvStore = Depends(get_env_example_store),
):
    env_text = payload.content
    lines = env_text.splitlines()
    parsed: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        parsed[key.strip()] = value
    errors = _validate_env(parsed)
    if errors:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"errors": [e.model_dump() for e in errors]})
    try:
        env_store.overwrite(env_text, expected_digest=payload.digest)
    except EnvVersionConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"message": str(exc)}) from exc
    except EnvStoreError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"message": str(exc)}) from exc
    return _fresh_snapshot(schema, env_store, overrides_store, example_store)


def _resolve_static(path: str) -> Path | None:
    candidate = (STATIC_DIR / path).resolve()
    try:
        candidate.relative_to(STATIC_DIR)
    except ValueError:
        return None
    if candidate.is_file():
        return candidate
    return None


@app.get("/", include_in_schema=False)
def index():
    target = STATIC_DIR / "index.html"
    if not target.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"message": "index missing"})
    return FileResponse(target)


@app.get("/{path:path}", include_in_schema=False)
def static_assets(path: str):
    if path.startswith("api/"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    resolved = _resolve_static(path)
    if resolved:
        return FileResponse(resolved)
    target = STATIC_DIR / "index.html"
    if target.exists():
        return FileResponse(target)
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


__all__ = ["app"]
