import pytest
from enhancement_core.codex.options import CodexOptions
from enhancement_core.config import PipelineSettings
from enhancement_core.orchestration import pipeline


def test_run_pipeline_iterations_repeats_runs(monkeypatch):
    calls: list[dict] = []

    def fake_run_pipeline(settings, *, demo=False, artifacts_dir=None, codex_options=None):
        calls.append({
            "settings": settings,
            "demo": demo,
            "artifacts_dir": artifacts_dir,
            "codex_options": codex_options,
        })
        return {"artifacts_dir": f"runs/{len(calls)}"}

    monkeypatch.setattr(pipeline, "run_pipeline", fake_run_pipeline)
    settings = PipelineSettings(PIPELINE_ARTIFACT_ROOT="run_logs/pipeline_runs")
    options = CodexOptions(model="gpt-4.1")
    results = pipeline.run_pipeline_iterations(3, settings, demo=True, codex_options=options)
    assert len(results) == 3
    assert [item["iteration"] for item in results] == [1, 2, 3]
    assert all(call["settings"] is settings for call in calls)
    assert all(call["demo"] is True for call in calls)
    assert all(call["artifacts_dir"] is None for call in calls)
    assert all(call["codex_options"] is options for call in calls)


def test_run_pipeline_iterations_rejects_invalid_counts():
    settings = PipelineSettings(PIPELINE_ARTIFACT_ROOT="run_logs/pipeline_runs")
    with pytest.raises(ValueError):
        pipeline.run_pipeline_iterations(0, settings)
