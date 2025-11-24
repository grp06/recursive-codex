from dataclasses import dataclass

from enhancement_core.config import FeedbackSettings


@dataclass
class FeedbackServiceConfig:
    settings: FeedbackSettings


def get_config() -> FeedbackServiceConfig:
    return FeedbackServiceConfig(settings=FeedbackSettings())


__all__ = ["FeedbackServiceConfig", "get_config"]
