import base64
import json
from pathlib import Path

import httpx
import pytest
from enhancement_core.config import PipelineSettings
from enhancement_core.orchestration import pipeline
from typer.testing import CliRunner

from apps.orchestrator_cli import cli as cli_module
from apps.orchestrator_cli.cli import app as cli_app
from enhancement_core.cli import app as cli_impl

pytestmark = pytest.mark.e2e


class FakeResponse:
    def __init__(self, request: httpx.Request, data: dict, status_code: int = 200):
        self._request = request
        self._data = data
        self.status_code = status_code
        self.text = json.dumps(data)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            response = httpx.Response(self.status_code, request=self._request, text=self.text)
            raise httpx.HTTPStatusError("error", request=self._request, response=response)

    def json(self) -> dict:
        return self._data


class FakeAsyncClient:
    def __init__(self, *_, **__):
        self.calls: list[dict] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url: str, json=None):
        self.calls.append({"url": url, "json": json})
        request = httpx.Request("POST", url)
        if url.endswith("/capture"):
            image = base64.b64encode(b"demo").decode()
            return FakeResponse(request, {"image_b64": image})
        if url.endswith("/feedback"):
            return FakeResponse(request, {"feedback": "Tighten copy"})
        return FakeResponse(request, {"status": "ok"})


@pytest.mark.asyncio
async def test_trigger_pipeline_creates_artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline.httpx, "AsyncClient", FakeAsyncClient)
    settings = PipelineSettings(
        FRONTEND_SCREENSHOTS_URL="http://svc:8101/capture",
        UI_FEEDBACK_SERVICE_URL="http://svc:8102/feedback",
        FRONTEND_ENHANCEMENT_ROUTER_URL="http://svc:8103/apply-feedback",
        PIPELINE_ARTIFACT_ROOT=tmp_path,
        PIPELINE_MAX_ATTEMPTS=1,
    )
    result = await pipeline.trigger_pipeline(settings, demo=True, artifacts_dir=tmp_path)
    run_dir = Path(result["artifacts_dir"])
    assert run_dir.exists()
    screenshot_path = run_dir / "screenshot.png"
    if not screenshot_path.exists():
        screenshot_path = run_dir / "attempt-1" / "screenshot.png"
    assert screenshot_path.exists()
    assert result["feedback"]["feedback"] == "Tighten copy"


def test_cli_pipeline_run_outputs_payload(monkeypatch):
    sample = {"status": "ok", "artifacts_dir": "runs/1"}
    monkeypatch.setattr(cli_impl, "run_pipeline", lambda *args, **kwargs: sample)
    monkeypatch.setattr(
        cli_impl,
        "_get_pipeline_settings",
        lambda env_file: PipelineSettings(PIPELINE_ARTIFACT_ROOT="run_logs/pipeline_runs"),
    )
    runner = CliRunner()
    result = runner.invoke(cli_app, ["pipeline", "run", "--demo"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"


def test_cli_pipeline_run_supports_iterations(monkeypatch):
    call_count = {"value": 0}

    def fake_run_pipeline(settings, *, demo=False, artifacts_dir=None, codex_options=None):
        call_count["value"] += 1
        idx = call_count["value"]
        return {"status": f"ok-{idx}", "artifacts_dir": f"runs/{idx}"}

    monkeypatch.setattr(cli_impl, "run_pipeline", fake_run_pipeline)
    monkeypatch.setattr(pipeline, "run_pipeline", fake_run_pipeline)
    monkeypatch.setattr(
        cli_impl,
        "_get_pipeline_settings",
        lambda env_file: PipelineSettings(PIPELINE_ARTIFACT_ROOT="run_logs/pipeline_runs"),
    )
    runner = CliRunner()
    result = runner.invoke(cli_app, ["pipeline", "run", "--iterations", "2"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["iteration_count"] == 2
    assert [item["iteration"] for item in payload["iterations"]] == [1, 2]
    assert [item["status"] for item in payload["iterations"]] == ["ok-1", "ok-2"]
    assert call_count["value"] == 2


def test_cli_pipeline_run_accepts_codex_model(monkeypatch):
    captured: dict[str, object] = {}

    def fake_run_pipeline(settings, *, demo=False, artifacts_dir=None, codex_options=None):
        captured["codex_options"] = codex_options
        return {"status": "ok", "artifacts_dir": "runs/1"}

    monkeypatch.setattr(cli_impl, "run_pipeline", fake_run_pipeline)
    monkeypatch.setattr(
        cli_impl,
        "_get_pipeline_settings",
        lambda env_file: PipelineSettings(PIPELINE_ARTIFACT_ROOT="run_logs/pipeline_runs"),
    )
    runner = CliRunner()
    result = runner.invoke(
        cli_app,
        [
            "pipeline",
            "run",
            "--model",
            "gpt-4.1-mini",
        ],
    )
    assert result.exit_code == 0
    assert captured["codex_options"].model == "gpt-4.1-mini"
