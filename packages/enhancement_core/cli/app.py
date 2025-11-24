import io
import json
from pathlib import Path
from typing import Optional

import httpx
import typer
from contextlib import redirect_stdout
from enhancement_core.codex.options import CodexOptions
from enhancement_core.codex.runner import CodexRunner, CodexRunnerError
from enhancement_core.config import HostBridgeSettings, PipelineSettings
from enhancement_core.config_store import (
    PipelineOverrides,
    PipelineOverridesError,
    PipelineOverridesStore,
)
from enhancement_core.logging import configure_logging
from enhancement_core.orchestration.pipeline import PipelineError, run_pipeline, run_pipeline_iterations
from pydantic import ValidationError

app = typer.Typer(add_completion=False, help="Toolkit orchestration utilities")
pipeline_app = typer.Typer(help="Full pipeline commands")
app.add_typer(pipeline_app, name="pipeline")
_overrides_store = PipelineOverridesStore()


class _StderrTee(io.StringIO):
    def write(self, s: str) -> int:  # type: ignore[override]
        if s:
            typer.echo(s, err=True, nl=False)
        return super().write(s)

    def writelines(self, lines) -> None:  # type: ignore[override]
        for line in lines:
            self.write(line)


def _health_url(endpoint: str) -> str:
    if endpoint.endswith("/capture") or endpoint.endswith("/feedback") or endpoint.endswith("/apply-feedback"):
        base = endpoint.rsplit("/", 1)[0]
        return f"{base}/health"
    return endpoint


def _ensure_logging() -> None:
    configure_logging("orchestrator_cli")


def _settings_kwargs(env_file: Optional[Path]) -> dict:
    if env_file:
        return {"_env_file": env_file}
    return {}


def _get_pipeline_settings(env_file: Optional[Path]) -> PipelineSettings:
    return PipelineSettings(**_settings_kwargs(env_file))


def _get_host_settings(env_file: Optional[Path]) -> HostBridgeSettings:
    return HostBridgeSettings(**_settings_kwargs(env_file))


def _load_pipeline_overrides() -> PipelineOverrides:
    try:
        return _overrides_store.load().overrides
    except PipelineOverridesError as exc:
        typer.echo(f"warning: unable to load pipeline overrides: {exc}", err=True)
        return PipelineOverrides()


@app.callback()
def main(
    ctx: typer.Context,
    env_file: Optional[Path] = typer.Option(None, help="Optional .env file to load before commands run"),
) -> None:
    ctx.ensure_object(dict)
    ctx.obj["env_file"] = env_file


@app.command()
def doctor(
    ctx: typer.Context, timeout: float = typer.Option(5.0, help="HTTP timeout for service health checks")
) -> None:
    _ensure_logging()
    env_file = ctx.obj.get("env_file")
    issues: list[str] = []
    try:
        pipeline_settings = _get_pipeline_settings(env_file)
    except ValidationError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    endpoints = {
        "screenshot": pipeline_settings.screenshot_endpoint,
        "feedback": pipeline_settings.feedback_endpoint,
        "router": pipeline_settings.router_endpoint,
    }
    with httpx.Client(timeout=timeout) as client:
        for name, endpoint in endpoints.items():
            url = _health_url(endpoint)
            try:
                response = client.get(url)
                response.raise_for_status()
                typer.echo(f"{name}: healthy ({url})")
            except httpx.HTTPError as exc:
                message = f"{name}: {exc}"
                typer.echo(message, err=True)
                issues.append(message)
    try:
        host_settings = _get_host_settings(env_file)
        runner = CodexRunner(host_settings)
        typer.echo(f"target repo: {runner.ensure_repo()}")
        typer.echo(f"codex binary: {runner.resolve_binary()}")
    except (CodexRunnerError, ValidationError, ValueError) as exc:
        message = str(exc)
        typer.echo(message, err=True)
        issues.append(message)
    if issues:
        raise typer.Exit(code=1)


@pipeline_app.command("run")
def pipeline_run(
    ctx: typer.Context,
    demo: Optional[bool] = typer.Option(
        None,
        "--demo/--no-demo",
        help="Label the pipeline artifacts as a demo run",
    ),
    artifacts_dir: Optional[Path] = typer.Option(
        None, "--artifacts-dir", help="Override the root directory for run artifacts"
    ),
    iterations: Optional[int] = typer.Option(
        None, "--iterations", "-i", min=1, help="Number of times to repeat the pipeline"
    ),
    model: Optional[str] = typer.Option(None, "--model", help="Override the Codex model for this run"),
    model_reasoning_effort: Optional[str] = typer.Option(
        None, "--model-reasoning-effort", help="Override the Codex reasoning effort for this run (low, medium, high)"
    ),
) -> None:
    _ensure_logging()
    env_file = ctx.obj.get("env_file")
    try:
        settings = _get_pipeline_settings(env_file)
    except ValidationError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    overrides = _load_pipeline_overrides()
    effective_demo = overrides.demo if demo is None else demo
    effective_iterations = overrides.iterations if iterations is None else iterations
    effective_artifacts_dir = artifacts_dir
    if effective_artifacts_dir is None and overrides.artifacts_dir:
        effective_artifacts_dir = Path(overrides.artifacts_dir)
    effective_model = model if model is not None else overrides.model
    effective_reasoning = (
        model_reasoning_effort if model_reasoning_effort is not None else overrides.model_reasoning_effort
    )
    codex_options = None
    if effective_model or effective_reasoning:
        try:
            codex_options = CodexOptions(model=effective_model, reasoning_effort=effective_reasoning)
        except ValidationError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc
    log_buffer = _StderrTee()
    try:
        with redirect_stdout(log_buffer):
            if effective_iterations == 1:
                result = run_pipeline(
                    settings,
                    demo=effective_demo,
                    artifacts_dir=effective_artifacts_dir,
                    codex_options=codex_options,
                )
            else:
                runs = run_pipeline_iterations(
                    effective_iterations,
                    settings,
                    demo=effective_demo,
                    artifacts_dir=effective_artifacts_dir,
                    codex_options=codex_options,
                )
    except (PipelineError, ValueError) as exc:
        typer.echo(f"pipeline failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    if effective_iterations == 1:
        if "router" in result and "results" in result["router"]:
            for router_result in result["router"]["results"]:
                if router_result.get("status") == "ok" and "result" in router_result:
                    stdout = router_result["result"].get("stdout", "")
                    if stdout:
                        typer.echo(stdout, err=True)
                        break
        typer.echo(json.dumps(result))
    else:
        for run_result in runs:
            if "router" in run_result and "results" in run_result["router"]:
                for router_result in run_result["router"]["results"]:
                    if router_result.get("status") == "ok" and "result" in router_result:
                        stdout = router_result["result"].get("stdout", "")
                        if stdout:
                            typer.echo(stdout, err=True)
                            break
        summary = {
            "iteration_count": len(runs),
            "iterations": runs,
        }
        typer.echo(json.dumps(summary))


@pipeline_app.command("sample-feedback")
def sample_feedback(
    ctx: typer.Context, timeout: float = typer.Option(30.0, help="HTTP timeout for router request")
) -> None:
    _ensure_logging()
    env_file = ctx.obj.get("env_file")
    try:
        settings = _get_pipeline_settings(env_file)
    except ValidationError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    payload = {"payload": {"feedback": settings.sample_feedback_text}}
    with httpx.Client(timeout=timeout) as client:
        try:
            response = client.post(settings.router_endpoint, json=payload)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            typer.echo(f"router request failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc
    try:
        body = response.json()
    except ValueError:
        typer.echo(response.text)
    else:
        typer.echo(json.dumps(body, indent=2))


__all__ = [
    "app",
    "pipeline_app",
    "doctor",
    "pipeline_run",
    "sample_feedback",
    "_get_pipeline_settings",
]
