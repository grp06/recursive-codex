import asyncio
import logging
import uuid
from typing import Any

import httpx
from enhancement_core.codex.options import CodexOptions
from enhancement_core.config import RouterSettings
from enhancement_core.logging import configure_logging, request_context
from fastapi import Depends, FastAPI, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator

from .dependencies import get_http_client, get_router_settings, lifespan

logger = logging.getLogger(__name__)
configure_logging("router_service")
app = FastAPI(
    title="Router Service",
    version="0.2.0",
    description="Fans out feedback payloads to the Codex bridge with concurrency controls.",
    lifespan=lifespan,
)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    with request_context(request_id):
        response = await call_next(request)
    response.headers["x-request-id"] = request_id
    return response


class FeedbackOutput(BaseModel):
    feedback: str = Field(min_length=1)

    @field_validator("feedback")
    @classmethod
    def validate_feedback(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("feedback cannot be empty")
        return stripped


class FeedbackEnvelope(BaseModel):
    output: FeedbackOutput
    codex_options: CodexOptions | None = None


class DirectFeedback(BaseModel):
    feedback: str = Field(min_length=1)
    codex_options: CodexOptions | None = None

    @field_validator("feedback")
    @classmethod
    def validate_feedback(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("feedback cannot be empty")
        return stripped


Payload = FeedbackEnvelope | DirectFeedback


def extract_feedback(entry: Payload) -> tuple[str, CodexOptions | None]:
    if isinstance(entry, FeedbackEnvelope):
        return entry.output.feedback, entry.codex_options
    return entry.feedback, entry.codex_options


async def submit_feedback(
    index: int,
    text: str,
    codex_options: CodexOptions | None,
    client: httpx.AsyncClient,
    settings: RouterSettings,
    semaphore: asyncio.Semaphore,
) -> dict[str, Any]:
    url = f"{settings.bridge_url}/apply-feedback"
    data: dict[str, Any] = {"feedback": text}
    if codex_options:
        data["codex_options"] = codex_options.model_dump(exclude_none=True)
    async with semaphore:
        try:
            response = await client.post(url, json=data)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "codex bridge error",
                extra={"index": index, "status_code": exc.response.status_code, "body": exc.response.text},
            )
            return {
                "index": index,
                "status": "error",
                "error": {
                    "message": "codex bridge error",
                    "status_code": exc.response.status_code,
                    "body": exc.response.text,
                },
            }
        except httpx.RequestError as exc:
            logger.error("codex bridge unreachable", extra={"index": index, "error": str(exc)})
            return {
                "index": index,
                "status": "error",
                "error": {"message": "unable to reach codex bridge", "detail": str(exc)},
            }
    try:
        payload = response.json()
    except ValueError:
        logger.error("bridge returned invalid json", extra={"index": index})
        return {"index": index, "status": "error", "error": {"message": "invalid bridge response"}}
    return {"index": index, "status": "ok", "result": payload}


def normalize_payload(payload: Payload | list[Payload] | tuple[Payload, ...]) -> list[Payload]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, tuple):
        return list(payload)
    return [payload]


@app.post("/apply-feedback", summary="Forward feedback entries to the host bridge")
async def apply_feedback(
    payload: Payload | list[Payload],
    client: httpx.AsyncClient = Depends(get_http_client),
    settings: RouterSettings = Depends(get_router_settings),
):
    entries = normalize_payload(payload)
    if not entries:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"message": "payload cannot be empty"})
    semaphore = asyncio.Semaphore(settings.max_concurrency)
    logger.info("dispatching feedback batch", extra={"count": len(entries)})
    tasks = [
        asyncio.create_task(
            submit_feedback(index, *extract_feedback(entry), client, settings, semaphore)
        )
        for index, entry in enumerate(entries)
    ]
    results = await asyncio.gather(*tasks)
    status_label = "partial-error" if any(result["status"] == "error" for result in results) else "submitted"
    return {"status": status_label, "results": results}


@app.get("/health", summary="Service readiness probe")
async def health(settings: RouterSettings = Depends(get_router_settings)):
    return {"status": "ok", "bridge": settings.bridge_url}
