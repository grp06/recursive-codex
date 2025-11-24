from pathlib import Path

import pytest

from enhancement_core.config_store import (
    EnvStore,
    EnvVersionConflictError,
    PipelineOverridesStore,
    PipelineOverridesVersionError,
)


def test_env_store_preserves_layout(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    path.write_text("FOO=one\n\nBAR=two\n", encoding="utf-8")
    store = EnvStore(path)
    snapshot = store.load()
    assert list(snapshot.values.keys()) == ["FOO", "BAR"]
    updated = store.save({"FOO": "alpha", "BAZ": "new"}, expected_digest=snapshot.digest)
    assert updated.values["FOO"] == "alpha"
    text = path.read_text(encoding="utf-8")
    assert text == "FOO=alpha\n\nBAR=two\n\nBAZ=new\n"


def test_env_store_conflict(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    path.write_text("KEY=one\n", encoding="utf-8")
    store = EnvStore(path)
    snapshot = store.load()
    path.write_text("KEY=two\n", encoding="utf-8")
    with pytest.raises(EnvVersionConflictError):
        store.save({"KEY": "three"}, expected_digest=snapshot.digest)


def test_env_store_overwrite(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    path.write_text("KEY=one\n", encoding="utf-8")
    store = EnvStore(path)
    snapshot = store.load()
    updated = store.overwrite("FOO=bar", expected_digest=snapshot.digest)
    assert updated.values["FOO"] == "bar"
    assert "FOO=bar\n" == path.read_text(encoding="utf-8")


def test_pipeline_overrides_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "config" / "pipeline_overrides.json"
    store = PipelineOverridesStore(path)
    snapshot = store.load()
    assert snapshot.overrides.iterations == 1
    assert snapshot.overrides.demo is False
    updated = store.save(
        {"iterations": 2, "model": "gpt-5.1", "demo": True}, expected_digest=snapshot.digest
    )
    assert updated.overrides.iterations == 2
    assert updated.overrides.model == "gpt-5.1"
    assert updated.overrides.demo is True


def test_pipeline_overrides_conflict(tmp_path: Path) -> None:
    path = tmp_path / "config" / "pipeline_overrides.json"
    store = PipelineOverridesStore(path)
    snapshot = store.load()
    path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(PipelineOverridesVersionError):
        store.save({"iterations": 2}, expected_digest=snapshot.digest)
