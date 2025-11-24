import base64
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, cast

from enhancement_core.config import FeedbackSettings
from openai import OpenAI, OpenAIError

logger = logging.getLogger(__name__)


class FeedbackError(RuntimeError):
    pass


@dataclass
class FeedbackResponse:
    feedback: str
    model: str | None
    response_id: str | None
    total_tokens: int | None


def load_schema(settings: FeedbackSettings) -> dict:
    path = settings.schema_path
    if not path.exists():
        raise FeedbackError(f"structured output schema missing at {path}")
    schema_text = path.read_text().strip()
    if not schema_text:
        raise FeedbackError("structured output schema is empty")
    try:
        return json.loads(schema_text)
    except json.JSONDecodeError as exc:
        raise FeedbackError("structured output schema is invalid JSON") from exc


def encode_bytes(data: bytes) -> str:
    if not data:
        raise FeedbackError("screenshot bytes are empty")
    return base64.b64encode(data).decode("utf-8")


def build_input(settings: FeedbackSettings, image_b64: Optional[str], user_text: Optional[str]) -> list[dict]:
    text_source = user_text
    if not text_source and image_b64:
        text_source = settings.default_user_text
    text = (text_source or "").strip()
    content = []
    if text:
        content.append({"type": "input_text", "text": text})
    if image_b64:
        content.append({"type": "input_image", "image_url": f"data:image/png;base64,{image_b64}"})
    if not content:
        raise FeedbackError("neither screenshot nor text provided")
    return [{"role": "user", "content": content}]


def parse_payload(raw: str) -> str:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise FeedbackError("model returned invalid JSON output") from exc
    feedback = parsed.get("feedback")
    if not isinstance(feedback, str) or not feedback.strip():
        raise FeedbackError("structured output missing feedback value")
    return feedback.strip()


def request_feedback(
    image_data: Optional[bytes], user_text: Optional[str], settings: FeedbackSettings | None = None
) -> FeedbackResponse:
    cfg = settings or FeedbackSettings()
    schema = load_schema(cfg)
    image_b64 = encode_bytes(image_data) if image_data else None
    client = OpenAI(api_key=cfg.api_key)
    responses = cast(Any, client.responses)
    logger.info("requesting UI feedback via %s", cfg.model_name)
    try:
        response = responses.create(
            model=cfg.model_name,
            instructions=cfg.prompt,
            input=build_input(cfg, image_b64, user_text),
            text={
                "format": {
                    "type": "json_schema",
                    "name": "ui_feedback",
                    "schema": schema,
                }
            },
            max_output_tokens=cfg.max_output_tokens,
        )
    except OpenAIError as exc:
        logger.exception("responses api call failed")
        raise FeedbackError("Responses API call failed") from exc
    payload = getattr(response, "output_text", None)
    if not payload:
        raise FeedbackError("model returned empty output")
    logger.info("received structured UI feedback", extra={"response_id": getattr(response, "id", None)})
    model_used = getattr(response, "model", cfg.model_name)
    usage = getattr(response, "usage", None)
    total_tokens = getattr(usage, "total_tokens", None) if usage else None
    feedback_text = parse_payload(payload)
    return FeedbackResponse(
        feedback=feedback_text,
        model=model_used,
        response_id=getattr(response, "id", None),
        total_tokens=total_tokens,
    )


def generate_feedback(
    screenshot_path: Path, user_text: Optional[str] = None, settings: FeedbackSettings | None = None
) -> str:
    if not screenshot_path.exists():
        raise FeedbackError(f"screenshot not found at {screenshot_path}")
    data = screenshot_path.read_bytes()
    if not data:
        raise FeedbackError("screenshot is empty")
    return request_feedback(data, user_text, settings).feedback


def generate_feedback_from_bytes(
    data: bytes, user_text: Optional[str] = None, settings: FeedbackSettings | None = None
) -> str:
    if not data:
        raise FeedbackError("screenshot bytes are empty")
    return request_feedback(data, user_text, settings).feedback


def generate_feedback_from_text(user_text: str, settings: FeedbackSettings | None = None) -> str:
    text = (user_text or "").strip()
    if not text:
        raise FeedbackError("text feedback cannot be empty")
    return request_feedback(None, text, settings).feedback


__all__ = [
    "FeedbackError",
    "FeedbackResponse",
    "generate_feedback",
    "generate_feedback_from_bytes",
    "generate_feedback_from_text",
    "request_feedback",
]
