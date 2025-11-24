import asyncio
import base64
import binascii
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from enhancement_core.codex.options import CodexOptions
from enhancement_core.config import PipelineSettings

logger = logging.getLogger(__name__)


class PipelineError(RuntimeError):
    pass


def _prepare_run_dir(root: Path, demo: bool) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    folder = f"{timestamp}-demo" if demo else timestamp
    path = root / folder
    try:
        path.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        raise PipelineError(f"unables to prepare pipeline artifacts at {path}") from exc
    return path


def _write_json(path: Path, payload: Any) -> None:
    try:
        path.write_text(json.dumps(payload, indent=2))
    except OSError as exc:
        raise PipelineError(f"unable to write pipeline artifact {path}") from exc


def _sanitize_screenshot_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Remove or truncate base64 image data from screenshot payload for logging."""
    sanitized = payload.copy()
    if "image_b64" in sanitized and isinstance(sanitized["image_b64"], str):
        # Truncate to first 50 chars + "..." to indicate it's been truncated
        truncated = sanitized["image_b64"][:50] + "..."
        sanitized["image_b64"] = truncated
    return sanitized


def _store_image(path: Path, image_b64: str) -> None:
    try:
        data = base64.b64decode(image_b64)
    except binascii.Error as exc:
        raise PipelineError("screenshot payload was not valid base64") from exc
    try:
        path.write_bytes(data)
    except OSError as exc:
        raise PipelineError(f"unable to write screenshot artifact {path}") from exc


async def _call_screenshot(client: httpx.AsyncClient, settings: PipelineSettings) -> dict[str, Any]:
    print("📸 Capturing screenshot...")
    logger.debug("requesting screenshot from %s", settings.screenshot_endpoint)
    try:
        response = await client.post(settings.screenshot_endpoint)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise PipelineError(f"screenshot service error: {exc.response.text}") from exc
    except httpx.RequestError as exc:
        raise PipelineError(f"screenshot service unreachable: {exc}") from exc
    payload = response.json()
    if not isinstance(payload, dict) or not payload.get("image_b64"):
        raise PipelineError("screenshot response missing image data")
    return payload


async def _call_feedback(
    client: httpx.AsyncClient, settings: PipelineSettings, screenshot_payload: dict[str, Any]
) -> dict[str, Any]:
    print("🧠 Analyzing screenshot for feedback...")
    logger.debug("requesting ui feedback from %s", settings.feedback_endpoint)
    try:
        body = {"screenshot_b64": screenshot_payload["image_b64"]}
        response = await client.post(settings.feedback_endpoint, json={"payload": body})
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise PipelineError(f"ui feedback error: {exc.response.text}") from exc
    except httpx.RequestError as exc:
        raise PipelineError(f"ui feedback service unreachable: {exc}") from exc
    payload = response.json()
    feedback = payload.get("feedback")
    if not isinstance(feedback, str) or not feedback.strip():
        raise PipelineError("ui feedback response missing feedback")
    return payload


async def _call_router(
    client: httpx.AsyncClient,
    settings: PipelineSettings,
    feedback_payload: dict[str, Any],
    codex_options: CodexOptions | None = None,
) -> dict[str, Any]:
    feedback = feedback_payload["feedback"]
    print("🚀 Applying feedback with Codex...")
    logger.debug("dispatching feedback to %s", settings.router_endpoint)
    payload: dict[str, Any] = {"payload": {"feedback": feedback}}
    if codex_options:
        payload["payload"]["codex_options"] = codex_options.model_dump(exclude_none=True)
    try:
        response = await client.post(settings.router_endpoint, json=payload)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise PipelineError(f"router error: {exc.response.text}") from exc
    except httpx.RequestError as exc:
        raise PipelineError(f"router service unreachable: {exc}") from exc
    return response.json()


def _store_attempt_artifacts(
    attempt_dir: Path,
    screenshot_payload: dict[str, Any],
    feedback_payload: dict[str, Any],
    router_payload: dict[str, Any],
) -> None:
    print(f"💾 Saving artifacts to {attempt_dir}")
    # Sanitize screenshot payload to avoid logging full base64 string
    sanitized_screenshot = _sanitize_screenshot_payload(screenshot_payload)
    _write_json(attempt_dir / "screenshot.json", sanitized_screenshot)
    _write_json(attempt_dir / "feedback.json", feedback_payload)
    _write_json(attempt_dir / "router.json", router_payload)
    image_b64 = screenshot_payload.get("image_b64")
    if isinstance(image_b64, str):
        _store_image(attempt_dir / "screenshot.png", image_b64)


async def trigger_pipeline(
    settings: PipelineSettings | None = None,
    *,
    demo: bool = False,
    artifacts_dir: Path | None = None,
    codex_options: CodexOptions | None = None,
) -> dict[str, Any]:
    cfg = settings or PipelineSettings()
    root = artifacts_dir or cfg.artifacts_root
    run_dir = _prepare_run_dir(root, demo)
    print(f"📁 Pipeline starting - artifacts will be saved to: {run_dir}")
    async with httpx.AsyncClient(timeout=cfg.request_timeout) as client:
        last_error: PipelineError | None = None
        for attempt in range(1, cfg.max_attempts + 1):
            attempt_dir = run_dir if cfg.max_attempts == 1 else run_dir / f"attempt-{attempt}"
            if attempt_dir != run_dir:
                try:
                    attempt_dir.mkdir(parents=True, exist_ok=False)
                except OSError as exc:
                    raise PipelineError(f"unable to prepare attempt directory {attempt_dir}") from exc
            print(f"🎯 Starting attempt {attempt}/{cfg.max_attempts}")
            try:
                screenshot_payload = await _call_screenshot(client, cfg)
                feedback_payload = await _call_feedback(client, cfg, screenshot_payload)
                router_payload = await _call_router(client, cfg, feedback_payload, codex_options)
                _store_attempt_artifacts(attempt_dir, screenshot_payload, feedback_payload, router_payload)
                print(f"✅ Attempt {attempt} completed successfully!")
                return {
                    "artifacts_dir": str(run_dir),
                    "attempt": attempt,
                    "screenshot": _sanitize_screenshot_payload(screenshot_payload),
                    "feedback": feedback_payload,
                    "router": router_payload,
                }
            except PipelineError as exc:
                last_error = exc
                logger.warning("pipeline attempt %d failed: %s", attempt, str(exc))
                if attempt < cfg.max_attempts:
                    print(f"⏳ Attempt {attempt} failed, retrying in {cfg.retry_backoff_seconds}s...")
                    await asyncio.sleep(cfg.retry_backoff_seconds)
        if last_error:
            raise last_error
        raise PipelineError("pipeline failed without specific error")


def run_pipeline(
    settings: PipelineSettings | None = None,
    *,
    demo: bool = False,
    artifacts_dir: Path | None = None,
    codex_options: CodexOptions | None = None,
) -> dict[str, Any]:
    try:
        return asyncio.run(trigger_pipeline(settings, demo=demo, artifacts_dir=artifacts_dir, codex_options=codex_options))
    except PipelineError as exc:
        logger.error("pipeline failed: %s", str(exc))
        raise


def run_pipeline_iterations(
    iterations: int,
    settings: PipelineSettings | None = None,
    *,
    demo: bool = False,
    artifacts_dir: Path | None = None,
    codex_options: CodexOptions | None = None,
) -> list[dict[str, Any]]:
    if iterations < 1:
        raise ValueError("iterations must be at least 1")
    results: list[dict[str, Any]] = []
    for iteration in range(1, iterations + 1):
        logger.debug("starting pipeline iteration %d/%d", iteration, iterations)
        try:
            result = run_pipeline(settings, demo=demo, artifacts_dir=artifacts_dir, codex_options=codex_options)
        except PipelineError as exc:
            logger.error("pipeline iteration %d/%d failed: %s", iteration, iterations, str(exc))
            raise
        # Sanitize screenshot payload in the result to avoid printing full base64
        if "screenshot" in result and isinstance(result["screenshot"], dict):
            result["screenshot"] = _sanitize_screenshot_payload(result["screenshot"])
        result["iteration"] = iteration
        results.append(result)
        print(f"iteration {iteration} done! ✨")
        logger.debug("completed pipeline iteration %d/%d", iteration, iterations)
    return results


__all__ = ["PipelineError", "run_pipeline", "run_pipeline_iterations", "trigger_pipeline"]
