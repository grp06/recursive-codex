from pathlib import Path

import pytest
from enhancement_core.codex.runner import CodexRunnerError
from enhancement_core.config import HostBridgeSettings
from fastapi.testclient import TestClient

from apps.host_bridge.app import app
from apps.host_bridge.dependencies import get_host_settings, get_runner


@pytest.fixture(autouse=True)
def reset_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def make_settings(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    return HostBridgeSettings(next_path=repo)


def test_apply_feedback_returns_runner_payload(tmp_path):
    runner_calls: list[dict] = []

    class DummyRunner:
        def run(self, feedback: str, codex_options=None):
            runner_calls.append({"feedback": feedback, "options": codex_options})
            return {"run_id": "abc", "stdout": "ok"}

    settings = make_settings(tmp_path)
    app.dependency_overrides[get_host_settings] = lambda: settings
    app.dependency_overrides[get_runner] = lambda: DummyRunner()
    with TestClient(app) as client:
        response = client.post("/apply-feedback", json={"feedback": "Ship it", "codex_options": {"model": "gpt-4.1"}})
    assert response.status_code == 200
    assert runner_calls[0]["feedback"] == "Ship it"
    assert runner_calls[0]["options"].model == "gpt-4.1"
    assert response.json()["run_id"] == "abc"


def test_apply_feedback_surfaces_runner_errors(tmp_path):
    class FailingRunner:
        def run(self, feedback: str, codex_options=None):
            raise CodexRunnerError("failed", run_id="r1", exit_code=2, stderr="boom", log_path="/tmp/log")

    settings = make_settings(tmp_path)
    app.dependency_overrides[get_host_settings] = lambda: settings
    app.dependency_overrides[get_runner] = lambda: FailingRunner()
    with TestClient(app) as client:
        response = client.post("/apply-feedback", json={"feedback": "Bad"})
    assert response.status_code == 502
    detail = response.json()["detail"]
    assert detail["run_id"] == "r1"
    assert detail["exit_code"] == 2


def test_health_returns_repo_path(tmp_path):
    settings = make_settings(tmp_path)
    app.dependency_overrides[get_host_settings] = lambda: settings
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert Path(response.json()["repo"]) == settings.next_path
