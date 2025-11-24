from pydantic import BaseModel, Field, field_validator


class CodexOptions(BaseModel):
    model: str | None = Field(default=None)
    reasoning_effort: str | None = Field(default=None)

    @field_validator("model")
    @classmethod
    def strip_value(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("value cannot be empty")
        return stripped

    @field_validator("reasoning_effort")
    @classmethod
    def validate_reasoning_effort(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("reasoning_effort cannot be empty")
        allowed_values = {"low", "medium", "high"}
        if stripped not in allowed_values:
            raise ValueError(f"reasoning_effort must be one of: {', '.join(sorted(allowed_values))}")
        return stripped

    def as_command_args(self) -> list[str]:
        args: list[str] = []
        if self.model:
            args.extend(["--model", self.model])
        if self.reasoning_effort:
            args.extend(["-c", f"model_reasoning_effort={self.reasoning_effort}"])
        return args


__all__ = ["CodexOptions"]
