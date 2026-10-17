from scene_core.config import ComputeConfig


def test_compute_config_expands_environment_and_tolerates_unset_values(tmp_path, monkeypatch):
    monkeypatch.setenv("COMPUTE_TOKEN", "")
    monkeypatch.setenv("MODAL_COMPUTE_URL", "https://modal.example")
    monkeypatch.delenv("VAST_URL", raising=False)
    config = ComputeConfig.load("backend/config/compute.yaml")
    assert config.targets["modal"].url == "https://modal.example"
    assert config.targets["modal"].token == ""
    assert config.targets["vast"].url is None
    path = tmp_path / "compute.yaml"
    path.write_text("targets:\n  x:\n    backend: http\n    url: ${MISSING_URL}\n    headers: {Authorization: Bearer ${MISSING_KEY}}\n")
    target = ComputeConfig.load(path).targets["x"]
    assert target.url is None and target.headers == {"Authorization": "Bearer"}


def test_pipeline_targets_come_from_environment(monkeypatch):
    from scene_core.config import PipelineConfig
    monkeypatch.setenv("GPU_TARGET", "vast")
    real = PipelineConfig.load("backend/config/pipeline.yaml").stages
    assert {stage.target for stage in real.values()} == {"vast"}
    assert real["ingest"].params["max_keyframes"] == 80
    assert real["ingest"].params["quality_filter"] is False
    fake = PipelineConfig.load("backend/config/pipeline.fake-gpu.yaml").stages
    assert {stage.target for stage in fake.values()} == {"vast"}
