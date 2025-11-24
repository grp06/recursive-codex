import base64
import binascii
import logging
import uuid
from typing import Optional

import httpx
from enhancement_core.config import FeedbackSettings
from enhancement_core.feedback import FeedbackError, request_feedback
from enhancement_core.logging import configure_logging, request_context
from fastapi import Body, Depends, FastAPI, HTTPException, Request, status
from pydantic import BaseModel, field_validator, model_validator

from .dependencies import get_feedback_settings, get_http_client, lifespan

logger = logging.getLogger(__name__)
configure_logging("feedback_service")
app = FastAPI(
    title="Feedback Service",
    version="0.2.0",
    description="Generates structured UI guidance from screenshots or text.",
    lifespan=lifespan,
)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    with request_context(request_id):
        response = await call_next(request)
    response.headers["x-request-id"] = request_id
    return response


class FeedbackRequest(BaseModel):
    screenshot_b64: Optional[str] = None
    screenshot_url: Optional[str] = None
    text: Optional[str] = None

    @field_validator("text")
    @classmethod
    def clean_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        stripped = value.strip()
        return stripped or None

    @field_validator("screenshot_url")
    @classmethod
    def validate_url(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        parsed = value.strip()
        if not parsed.startswith("http"):
            raise ValueError("screenshot_url must be http or https")
        return parsed

    @model_validator(mode="after")
    def validate_payload(self):
        if not (self.screenshot_b64 or self.screenshot_url or self.text):
            raise ValueError("screenshot or text input required")
        return self


def decode_payload(value: str) -> bytes:
    try:
        return base64.b64decode(value)
    except binascii.Error as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail={"message": "screenshot_b64 is not valid base64"}
        ) from exc


async def fetch_url(client: httpx.AsyncClient, url: str) -> bytes:
    try:
        response = await client.get(url)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_424_FAILED_DEPENDENCY,
            detail={"message": f"unable to download screenshot: {exc.response.status_code}"},
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_424_FAILED_DEPENDENCY, detail={"message": f"unable to download screenshot: {exc}"}
        ) from exc
    return response.content


@app.post("/feedback", summary="Generate UI feedback with optional metadata")
async def feedback_endpoint(
    payload: FeedbackRequest = Body(..., embed=False),
    settings: FeedbackSettings = Depends(get_feedback_settings),
    client: httpx.AsyncClient = Depends(get_http_client),
):
    logger.info(
        "feedback request received",
        extra={
            "has_b64": bool(payload.screenshot_b64),
            "has_url": bool(payload.screenshot_url),
            "has_text": bool(payload.text),
        },
    )
    image_bytes = None
    if payload.screenshot_b64:
        image_bytes = decode_payload(payload.screenshot_b64)
        logger.info("decoded screenshot payload", extra={"size": len(image_bytes)})
    elif payload.screenshot_url:
        image_bytes = await fetch_url(client, payload.screenshot_url)
        logger.info("downloaded screenshot", extra={"bytes": len(image_bytes)})
    try:
        response = request_feedback(image_bytes, payload.text, settings)
    except FeedbackError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail={"message": str(exc)}) from exc
    logger.info(
        "ui feedback ready",
        extra={"response_id": response.response_id, "model": response.model, "tokens_used": response.total_tokens},
    )
    return {
        "feedback": response.feedback,
        "model": response.model,
        "tokens_used": response.total_tokens,
        "response_id": response.response_id,
    }


@app.get("/health", summary="Service readiness probe")
async def health(settings: FeedbackSettings = Depends(get_feedback_settings)):
    return {"status": "ok", "model": settings.model_name}
