import asyncio
import logging
import uuid
from functools import partial

from enhancement_core.codex import CodexOptions, CodexRunner, CodexRunnerError
from enhancement_core.config import HostBridgeSettings
from enhancement_core.logging import configure_logging, current_request_id, request_context
from fastapi import Depends, FastAPI, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator

from .dependencies import get_host_settings, get_runner

logger = logging.getLogger(__name__)
configure_logging("host_bridge")
app = FastAPI(
    title="Host Bridge",
    version="0.2.0",
    description="Runs Codex CLI against the configured repository.",
)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    with request_context(request_id):
        response = await call_next(request)
    response.headers["x-request-id"] = request_id
    return response


class HostPayload(BaseModel):
    feedback: str = Field(min_length=1)
    codex_options: CodexOptions | None = None

    @field_validator("feedback")
    @classmethod
    def validate_feedback(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("feedback cannot be empty")
        return stripped


@app.post("/apply-feedback", summary="Execute Codex with the provided feedback")
async def apply_feedback(payload: HostPayload, runner: CodexRunner = Depends(get_runner)):
    request_id = current_request_id() or str(uuid.uuid4())
    print("📨 Processing feedback request...")
    loop = asyncio.get_running_loop()
    try:
        func = partial(runner.run, payload.feedback, codex_options=payload.codex_options)
        result = await loop.run_in_executor(None, func)
    except CodexRunnerError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "message": str(exc),
                "run_id": exc.run_id,
                "exit_code": exc.exit_code,
                "stderr": exc.stderr,
                "log_path": exc.log_path,
            },
        ) from exc
    print("✅ Feedback applied successfully!")
    return result


@app.get("/health", summary="Service readiness probe")
async def health(settings: HostBridgeSettings = Depends(get_host_settings)):
    return {"status": "ok", "repo": str(settings.next_path)}
