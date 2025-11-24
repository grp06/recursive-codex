from pathlib import Path
from urllib.parse import urlparse

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_FEEDBACK_PROMPT = """You are a focused UI reviewer. Inspect the landing page screenshot and return exactly one concrete change that would most improve clarity, conversion, or overall UX. Be specific and actionable."""


class RuntimeSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @staticmethod
    def _normalize_path(value: Path | str) -> Path:
        if isinstance(value, Path):
            return value.expanduser()
        return Path(value).expanduser()

    @staticmethod
    def _validate_url(value: str, field_name: str) -> str:
        parsed = urlparse(value.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(f"{field_name} must be an absolute http(s) URL")
        return value.strip()


class ScreenshotSettings(RuntimeSettings):
    target_url: str = Field(default="http://localhost:3000", alias="FRONTEND_SCREENSHOT_URL")
    output_dir: Path = Field(default=Path("screenshots"), alias="FRONTEND_SCREENSHOT_OUTPUT_DIR")
    viewport_width: int = Field(default=1280, ge=320, le=5120, alias="FRONTEND_SCREENSHOT_VIEWPORT_WIDTH")
    viewport_height: int = Field(default=720, ge=320, le=4320, alias="FRONTEND_SCREENSHOT_VIEWPORT_HEIGHT")
    scroll_delay_ms: int = Field(default=400, ge=100, le=2000, alias="FRONTEND_SCREENSHOT_SCROLL_DELAY_MS")
    max_captures: int = Field(default=100, ge=1, le=250, alias="FRONTEND_SCREENSHOT_MAX_CAPTURES")
    nav_timeout_ms: int = Field(default=45000, ge=1000, alias="FRONTEND_SCREENSHOT_NAV_TIMEOUT_MS")

    @field_validator("target_url")
    @classmethod
    def validate_target_url(cls, value: str) -> str:
        return cls._validate_url(value, "FRONTEND_SCREENSHOT_URL")

    @field_validator("output_dir", mode="before")
    @classmethod
    def normalize_output_dir(cls, value: Path | str) -> Path:
        return cls._normalize_path(value)


class FeedbackSettings(RuntimeSettings):
    schema_path: Path = Field(default=Path("config") / "ui_feedback_schema.json", alias="UI_FEEDBACK_SCHEMA_PATH")
    model_name: str = Field(default="gpt-5.1", alias="UI_FEEDBACK_MODEL_NAME")
    max_output_tokens: int = Field(default=2000, ge=256, le=4096, alias="UI_FEEDBACK_MAX_OUTPUT_TOKENS")
    default_user_text: str = Field(default="Here's the landing page screenshot to analyze.", alias="UI_FEEDBACK_DEFAULT_TEXT")
    prompt: str = Field(default=DEFAULT_FEEDBACK_PROMPT, alias="UI_FEEDBACK_PROMPT")
    api_key: str = Field(alias="OPENAI_API_KEY")
    request_timeout: float = Field(default=120.0, gt=0, alias="UI_FEEDBACK_HTTP_TIMEOUT")

    @field_validator("schema_path", mode="before")
    @classmethod
    def normalize_schema_path(cls, value: Path | str) -> Path:
        return cls._normalize_path(value)

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("OPENAI_API_KEY is required")
        return stripped


class RouterSettings(RuntimeSettings):
    bridge_url: str = Field(default="http://host.docker.internal:5600", alias="FRONTEND_ENHANCEMENT_BRIDGE_URL")
    request_timeout: float = Field(default=240.0, gt=0, alias="FRONTEND_ENHANCEMENT_HOST_TIMEOUT")
    max_concurrency: int = Field(default=4, ge=1, alias="ROUTER_MAX_CONCURRENCY")

    @field_validator("bridge_url")
    @classmethod
    def validate_bridge_url(cls, value: str) -> str:
        return cls._validate_url(value, "FRONTEND_ENHANCEMENT_BRIDGE_URL")


class HostBridgeSettings(RuntimeSettings):
    next_path: Path = Field(alias="TARGET_REPO_PATH")
    prompt_prefix: str = Field(
        default="You are the worlds top frontend engineer. Apply the feedback to the target repository.",
        alias="CODEX_INSTRUCTION_PREFIX",
    )
    codex_bin: str = Field(default="codex", alias="FRONTEND_ENHANCEMENT_CODEX_BIN")
    logs_root: Path = Field(default=Path("run_logs") / "codex_runs", alias="FRONTEND_ENHANCEMENT_CODEX_LOG_DIR")
    codex_timeout_seconds: float = Field(default=300.0, gt=0, alias="FRONTEND_ENHANCEMENT_HOST_TIMEOUT")

    @field_validator("next_path", mode="before")
    @classmethod
    def normalize_next_path(cls, value: Path | str) -> Path:
        return cls._normalize_path(value)

    @field_validator("logs_root", mode="before")
    @classmethod
    def normalize_logs_root(cls, value: Path | str) -> Path:
        return cls._normalize_path(value)

    @field_validator("next_path")
    @classmethod
    def validate_next_path_exists(cls, value: Path) -> Path:
        if not value.exists():
            raise ValueError("TARGET_REPO_PATH must point to an existing directory")
        if not value.is_dir():
            raise ValueError("TARGET_REPO_PATH must be a directory")
        return value


class PipelineSettings(RuntimeSettings):
    screenshot_endpoint: str = Field(default="http://localhost:8101/capture", alias="FRONTEND_SCREENSHOTS_URL")
    feedback_endpoint: str = Field(default="http://localhost:8102/feedback", alias="UI_FEEDBACK_SERVICE_URL")
    router_endpoint: str = Field(
        default="http://localhost:8103/apply-feedback", alias="FRONTEND_ENHANCEMENT_ROUTER_URL"
    )
    request_timeout: float = Field(default=240.0, gt=0, alias="PIPELINE_REQUEST_TIMEOUT")
    max_attempts: int = Field(default=3, ge=1, alias="PIPELINE_MAX_ATTEMPTS")
    retry_backoff_seconds: float = Field(default=2.0, ge=0.5, alias="PIPELINE_RETRY_BACKOFF")
    artifacts_root: Path = Field(default=Path("run_logs") / "pipeline_runs", alias="PIPELINE_ARTIFACT_ROOT")
    sample_feedback_text: str = Field(
        default="Tighten hero spacing, raise CTA prominence, and simplify testimonial layout.",
        alias="PIPELINE_SAMPLE_FEEDBACK",
    )

    @field_validator("screenshot_endpoint")
    @classmethod
    def validate_screenshot_endpoint(cls, value: str) -> str:
        return cls._validate_url(value, "FRONTEND_SCREENSHOTS_URL")

    @field_validator("feedback_endpoint")
    @classmethod
    def validate_feedback_endpoint(cls, value: str) -> str:
        return cls._validate_url(value, "UI_FEEDBACK_SERVICE_URL")

    @field_validator("router_endpoint")
    @classmethod
    def validate_router_endpoint(cls, value: str) -> str:
        return cls._validate_url(value, "FRONTEND_ENHANCEMENT_ROUTER_URL")

    @field_validator("artifacts_root", mode="before")
    @classmethod
    def normalize_artifacts_root(cls, value: Path | str) -> Path:
        return cls._normalize_path(value)


__all__ = [
    "DEFAULT_FEEDBACK_PROMPT",
    "FeedbackSettings",
    "HostBridgeSettings",
    "PipelineSettings",
    "RouterSettings",
    "RuntimeSettings",
    "ScreenshotSettings",
]
