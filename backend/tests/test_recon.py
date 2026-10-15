import contextlib
import sys
import types

import numpy as np
import pytest
from PIL import Image
from scene_core.contracts import SceneWorkspace
from scene_core.errors import SceneError
from scene_stages import gpu


class FakeDepthAnything3:
    """Stands in for depth_anything_3.api.DepthAnything3 with its documented Prediction fields."""
    is_metric = 1

    @classmethod
    def from_pretrained(cls, model_id):
        model = cls()
        model.model_id = model_id
        return model

    def to(self, device):
        return self

    def eval(self):
        return self

    def inference(self, images, **kwargs):
        self.calls = getattr(self, "calls", []) + [(images, kwargs)]
        count, height, width = len(images), 6, 8
        extrinsics = np.tile(np.eye(4)[:3], (count, 1, 1))
        extrinsics[:, :3, 3] = [[-index, 0, 0] for index in range(count)]  # camera i sits at x = i
        confidence = np.tile(np.linspace(1, 2, width, dtype=np.float32), (count, height, 1))
        return types.SimpleNamespace(
            depth=np.full((count, height, width), 2, np.float32), conf=confidence,
            extrinsics=extrinsics.astype(np.float32),
            intrinsics=np.tile(np.array([[8, 0, 4], [0, 8, 3], [0, 0, 1]], np.float32), (count, 1, 1)),
            processed_images=np.full((count, height, width, 3), 90, np.uint8),
            is_metric=self.is_metric, scale_factor=None)


@pytest.fixture
def fake_da3(monkeypatch):
    api = types.ModuleType("depth_anything_3.api")
    api.DepthAnything3 = FakeDepthAnything3
    monkeypatch.setitem(sys.modules, "depth_anything_3", types.ModuleType("depth_anything_3"))
    monkeypatch.setitem(sys.modules, "depth_anything_3.api", api)
    monkeypatch.setattr(gpu, "_cuda", lambda: types.SimpleNamespace(inference_mode=contextlib.nullcontext))
    return api


def _workspace(tmp_path, count):
    workspace = SceneWorkspace(tmp_path, "recon")
    for index in range(count):
        Image.new("RGB", (16, 12), (index, 0, 0)).save(workspace.dir("keyframes") / f"{index:04d}.jpg")
    return workspace


def test_da3_writes_camera_to_world_frames_in_one_pass(tmp_path, fake_da3):
    workspace = _workspace(tmp_path, 3)
    algorithm = gpu.DepthAnything3Reconstruction()
    algorithm.setup()
    manifest = algorithm.run(workspace, {"confidence_percentile": 25, "process_res": 504})
    assert manifest.frame_ids == ["0000", "0001", "0002"]
    assert manifest.image_size == (8, 6) and manifest.metric_scale == 1
    images, kwargs = algorithm.model.calls[0]
    assert len(algorithm.model.calls) == 1 and len(images) == 3
    assert kwargs["process_res"] == 504 and kwargs["use_ray_pose"] is True
    with np.load(workspace.path("recon/frames/0002.npz")) as frame:
        assert np.allclose(frame["pose"][:3, 3], [2, 0, 0])
        assert frame["K"].shape == (3, 3)
        # The least confident quarter of pixels is masked out with zero depth and confidence.
        assert (frame["depth"][:, :2] == 0).all() and (frame["conf"][:, :2] == 0).all()
        assert np.allclose(frame["depth"][:, 2:], 2)
    assert np.asarray(Image.open(workspace.path("recon/rgb/0001.png"))).shape == (6, 8, 3)


def test_da3_refuses_relative_depth(tmp_path, fake_da3, monkeypatch):
    monkeypatch.setattr(FakeDepthAnything3, "is_metric", 0)
    algorithm = gpu.DepthAnything3Reconstruction()
    algorithm.setup()
    with pytest.raises(SceneError) as error:
        algorithm.run(_workspace(tmp_path, 2), {})
    assert error.value.code == "INVALID_MODEL_OUTPUT"
