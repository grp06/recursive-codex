import json
import logging
import os
import time
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

_configured = False
_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


class JsonFormatter(logging.Formatter):
    def __init__(self, service_name: str | None = None):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = _request_id.get()
        if request_id and "request_id" not in payload:
            payload["request_id"] = request_id
        if self.service_name:
            payload["service"] = self.service_name
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        for key, value in record.__dict__.items():
            if key.startswith("_"):
                continue
            if key in payload:
                continue
            try:
                json.dumps(value)
            except TypeError:
                continue
            payload[key] = value
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(service_name: str | None = None) -> None:
    global _configured
    if _configured:
        return
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter(service_name))
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)
    root.addHandler(handler)

    # Suppress noisy httpx HTTP request logs
    httpx_logger = logging.getLogger("httpx")
    httpx_logger.setLevel(logging.WARNING)

    _configured = True


@contextmanager
def request_context(request_id: str | None):
    token = _request_id.set(request_id)
    try:
        yield
    finally:
        _request_id.reset(token)


def current_request_id() -> str | None:
    return _request_id.get()


__all__ = ["configure_logging", "current_request_id", "request_context"]
