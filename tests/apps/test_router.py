import json

import httpx
import pytest
from enhancement_core.config import RouterSettings
from fastapi.testclient import TestClient

from apps.router_service.app import app
from apps.router_service.dependencies import get_http_client, get_router_settings


class FakeResponse:
    def __init__(self, data: dict, status_code: int = 200):
        self._data = data
        self.status_code = status_code
        self.text = json.dumps(data)
        self._request = httpx.Request("POST", "http://bridge/apply-feedback")

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            response = httpx.Response(self.status_code, request=self._request, text=self.text)
            raise httpx.HTTPStatusError("bridge error", request=self._request, response=response)

    def json(self) -> dict:
        return self._data


class DummyAsyncClient:
    def __init__(self, responses: list[FakeResponse]):
        self.responses = responses
        self.calls: list[dict] = []

    async def post(self, url: str, json=None):
        self.calls.append({"url": url, "json": json})
        return self.responses.pop(0)


@pytest.fixture(autouse=True)
def reset_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def setup_test_client(dummy_client: DummyAsyncClient, settings: RouterSettings) -> TestClient:
    app.dependency_overrides[get_http_client] = lambda: dummy_client
    app.dependency_overrides[get_router_settings] = lambda: settings
    return TestClient(app)


def test_apply_feedback_dispatches_batch_payloads():
    responses = [FakeResponse({"status": "ok", "run": 1}), FakeResponse({"status": "ok", "run": 2})]
    client = DummyAsyncClient(responses)
    settings = RouterSettings(bridge_url="http://bridge", max_concurrency=2)
    with setup_test_client(client, settings) as test_client:
        payload = [
            {"output": {"feedback": "First"}},
            {"feedback": "Second", "codex_options": {"reasoning_effort": "medium"}},
        ]
        response = test_client.post("/apply-feedback", json={"payload": payload})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "submitted"
    assert len(body["results"]) == 2
    assert client.calls[0]["json"] == {"feedback": "First"}
    assert client.calls[1]["json"] == {
        "feedback": "Second",
        "codex_options": {"reasoning_effort": "medium"},
    }


def test_apply_feedback_reports_partial_failures():
    responses = [FakeResponse({"status": "ok"}), FakeResponse({"detail": "bad"}, status_code=502)]
    client = DummyAsyncClient(responses)
    settings = RouterSettings(bridge_url="http://bridge", max_concurrency=1)
    with setup_test_client(client, settings) as test_client:
        payload = [{"feedback": "Good"}, {"feedback": "Better"}]
        response = test_client.post("/apply-feedback", json={"payload": payload})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "partial-error"
    assert body["results"][1]["status"] == "error"
