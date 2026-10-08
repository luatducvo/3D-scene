import hashlib
import json

import pytest

from s3d_app.models import pull_models


def test_model_pull_skips_verified_and_rejects_corruption(tmp_path) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"model")
    lock = tmp_path / "models.lock"
    lock.write_text(json.dumps({"format_version": 1, "models": [{
        "name": "model.bin", "url": source.as_uri(),
        "sha256": hashlib.sha256(b"model").hexdigest(),
    }]}))
    destination = tmp_path / "models"
    assert pull_models(lock, destination) == ["model.bin"]
    assert pull_models(lock, destination) == []
    (destination / "model.bin").write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        pull_models(lock, destination)
