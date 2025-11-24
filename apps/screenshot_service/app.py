import base64
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from enhancement_core.config import ScreenshotSettings
from enhancement_core.logging import configure_logging, request_context
from enhancement_core.screenshots.capture import ScreenshotError
from fastapi import Depends, FastAPI, HTTPException, Request, status

from .dependencies import ScreenshotCaptureRunner, get_capture_runner, get_settings, lifespan

configure_logging("screenshot_service")
app = FastAPI(
    title="Screenshot Service",
    version="0.2.0",
    description="Captures stitched screenshots for the enhancement pipeline.",
    lifespan=lifespan,
)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    with request_context(request_id):
        response = await call_next(request)
    response.headers["x-request-id"] = request_id
    return response


def _cleanup(path: Path | None) -> None:
    if path is None:
        return
    run_dir = path.parent
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
    try:
        shutil.rmtree(run_dir, ignore_errors=True)
    except OSError:
        pass


def _serialize(path: Path) -> dict:
    timestamp = datetime.now(timezone.utc).isoformat()
    payload = path.read_bytes()
    image_b64 = base64.b64encode(payload).decode("utf-8")
    return {
        "status": "success",
        "path": str(path),
        "filename": path.name,
        "timestamp": timestamp,
        "image_b64": image_b64,
        "size_bytes": len(payload),
    }


@app.post("/capture", summary="Capture and stitch the configured URL")
async def capture(runner: ScreenshotCaptureRunner = Depends(get_capture_runner)):
    path: Path | None = None
    try:
        path = await runner.capture()
        return _serialize(path)
    except ScreenshotError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail={"message": str(exc)}) from exc
    finally:
        _cleanup(path)


@app.get("/health", summary="Service readiness probe")
async def health(settings: ScreenshotSettings = Depends(get_settings)):
    return {"status": "ok", "target": settings.target_url}
