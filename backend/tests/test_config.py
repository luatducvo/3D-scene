from scene_core.config import ComputeConfig


def test_compute_config_expands_environment_and_tolerates_unset_values(tmp_path, monkeypatch):
    monkeypatch.setenv("COMPUTE_TOKEN", "")
    monkeypatch.setenv("MODAL_RECON_URL", "https://recon.example")
    monkeypatch.delenv("MODAL_PERCEPTION_URL", raising=False)
    config = ComputeConfig.load("backend/config/compute.yaml")
    assert config.targets["modal_recon"].url == "https://recon.example"
    assert config.targets["modal_recon"].token == ""
    assert config.targets["modal_perception"].url is None
    path = tmp_path / "compute.yaml"
    path.write_text("targets:\n  x:\n    backend: http\n    url: ${MISSING_URL}\n    headers: {Authorization: Bearer ${MISSING_KEY}}\n")
    target = ComputeConfig.load(path).targets["x"]
    assert target.url is None and target.headers == {"Authorization": "Bearer"}
