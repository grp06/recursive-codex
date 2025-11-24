import json
from types import SimpleNamespace

import pytest
from enhancement_core.config import FeedbackSettings
from enhancement_core.feedback import generate as feedback_module
from enhancement_core.feedback.generate import FeedbackError, build_input, parse_payload, request_feedback


@pytest.fixture
def schema_file(tmp_path):
    path = tmp_path / "schema.json"
    payload = {"type": "object", "properties": {"feedback": {"type": "string"}}, "required": ["feedback"]}
    path.write_text(json.dumps(payload))
    return path


@pytest.fixture
def feedback_settings(schema_file):
    return FeedbackSettings(
        schema_path=schema_file,
        OPENAI_API_KEY="sk-test",
        UI_FEEDBACK_DEFAULT_TEXT="",
    )


def test_build_input_requires_payload(feedback_settings):
    with pytest.raises(FeedbackError):
        build_input(feedback_settings, None, None)


def test_build_input_includes_text_and_image(feedback_settings):
    result = build_input(feedback_settings, "dGVzdA==", "Hello")
    assert result[0]["content"][0]["text"] == "Hello"
    assert result[0]["content"][1]["image_url"].startswith("data:image/png;base64,")


def test_request_feedback_parses_response(monkeypatch, feedback_settings):
    created_clients: list = []

    class DummyResponses:
        def __init__(self):
            self.kwargs = None

        def create(self, **kwargs):
            self.kwargs = kwargs
            return SimpleNamespace(
                output_text=json.dumps({"feedback": "Ship it"}),
                id="resp-1",
                model="gpt-test",
                usage=SimpleNamespace(total_tokens=128),
            )

    class DummyClient:
        def __init__(self, api_key):
            self.api_key = api_key
            self.responses = DummyResponses()
            created_clients.append(self)

    monkeypatch.setattr(feedback_module, "OpenAI", DummyClient)
    response = request_feedback(b"image-bytes", "Tighten hero", feedback_settings)
    assert response.feedback == "Ship it"
    assert response.response_id == "resp-1"
    assert response.total_tokens == 128
    sent = created_clients[0].responses.kwargs
    assert sent["input"][0]["content"][0]["text"] == "Tighten hero"


def test_parse_payload_requires_feedback_field():
    with pytest.raises(FeedbackError):
        parse_payload(json.dumps({}))
