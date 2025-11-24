import importlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def _bootstrap_root(tmp_path: Path) -> Path:
    root = tmp_path / "config-ui-project"
    root.mkdir()
    (root / "config").mkdir()
    schema_src = Path("config/frontend_config_schema.json")
    overrides_src = Path("config/pipeline_overrides.json")
    (root / "config/frontend_config_schema.json").write_text(schema_src.read_text(encoding="utf-8"), encoding="utf-8")
    (root / "config/pipeline_overrides.json").write_text(overrides_src.read_text(encoding="utf-8"), encoding="utf-8")
    env_example = Path(".env.example").read_text(encoding="utf-8")
    (root / ".env.example").write_text(env_example, encoding="utf-8")
    target_repo = root / "demo"
    target_repo.mkdir()
    env_path = root / ".env"
    env_path.write_text(
        "\n".join(
            [
                "OPENAI_API_KEY=test-key",
                f"TARGET_REPO_PATH={target_repo}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return root


@pytest.fixture()
def config_ui_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root = _bootstrap_root(tmp_path)
    monkeypatch.setenv("CONFIG_UI_PROJECT_ROOT", str(root))
    monkeypatch.setenv("CONFIG_UI_SKIP_HOST_PATH_CHECK", "0")
    import apps.config_ui.config as config_mod
    import apps.config_ui.dependencies as deps_mod
    import apps.config_ui.app as app_mod

    importlib.reload(config_mod)
    importlib.reload(deps_mod)
    importlib.reload(app_mod)
    client = TestClient(app_mod.app)
    try:
        yield client, root
    finally:
        client.close()


def test_read_config_returns_snapshot(config_ui_client):
    client, _ = config_ui_client
    response = client.get("/api/config")
    assert response.status_code == 200
    payload = response.json()
    assert "schema" in payload
    assert payload["values"]["OPENAI_API_KEY"] is None
    assert payload["secrets"]["OPENAI_API_KEY"]["present"] is True
    assert payload["defaults"]["PIPELINE_REQUEST_TIMEOUT"] == "240"


def test_update_config_writes_env_and_cli(config_ui_client):
    client, root = config_ui_client
    initial = client.get("/api/config").json()
    payload = {
        "values": {
            "PIPELINE_MAX_ATTEMPTS": 5,
            "iterations": 3,
        },
        "versions": {
            "env": initial["versions"]["env"]["digest"],
            "overrides": initial["versions"]["overrides"]["digest"],
        },
    }
    response = client.put("/api/config", json=payload)
    assert response.status_code == 200
    updated = response.json()
    assert updated["values"]["PIPELINE_MAX_ATTEMPTS"] == "5"
    overrides_path = root / "config" / "pipeline_overrides.json"
    overrides = json.loads(overrides_path.read_text(encoding="utf-8"))
    assert overrides["iterations"] == 3
    env_text = (root / ".env").read_text(encoding="utf-8")
    assert "PIPELINE_MAX_ATTEMPTS=5" in env_text


def test_update_config_validates_host_path(config_ui_client):
    client, root = config_ui_client
    initial = client.get("/api/config").json()
    payload = {
        "values": {
            "TARGET_REPO_PATH": str(root / "missing"),
        },
        "versions": {
            "env": initial["versions"]["env"]["digest"],
            "overrides": initial["versions"]["overrides"]["digest"],
        },
    }
    response = client.put("/api/config", json=payload)
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert any("TARGET_REPO_PATH" in err["message"] for err in detail["errors"])


def test_validate_endpoint_returns_ok(config_ui_client):
    client, _ = config_ui_client
    payload = {"values": {"PIPELINE_REQUEST_TIMEOUT": 360}}
    response = client.post("/api/config/validate", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
