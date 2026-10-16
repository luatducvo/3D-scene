import numpy as np
import pytest
from PIL import Image, ImageFilter
from scene_core.contracts import SceneWorkspace
from scene_core.errors import SceneError
from scene_stages.ingest import OpenCVIngest


def test_quality_report_metadata_and_minimum(tmp_path):
    workspace = SceneWorkspace(tmp_path, "ingest")
    raw = workspace.dir("raw")
    rng = np.random.default_rng(4)
    image = Image.fromarray(rng.integers(30, 220, (96, 96, 3), dtype=np.uint8))
    exif = Image.Exif()
    exif[274] = 6
    image.save(raw / "01-good.jpg", exif=exif)
    (raw / "02-copy.jpg").write_bytes((raw / "01-good.jpg").read_bytes())
    image.filter(ImageFilter.GaussianBlur(15)).save(raw / "03-blur.jpg")
    Image.new("RGB", (96, 96), (0, 0, 0)).save(raw / "04-dark.jpg")
    result = OpenCVIngest().run(workspace, {"min_keyframes": 1})
    assert result.num_keyframes == 1
    assert result.rejected["duplicate"] == ["02-copy.jpg"]
    assert result.rejected["blur"] == ["03-blur.jpg"]
    assert result.rejected["exposure"] == ["04-dark.jpg"]
    assert not Image.open(workspace.path("keyframes/0000.jpg")).getexif()
    with pytest.raises(SceneError) as error:
        OpenCVIngest().run(workspace, {"min_keyframes": 10})
    assert error.value.code == "NOT_ENOUGH_KEYFRAMES"
    assert error.value.details["rejection_counts"]["duplicate"] == 1
    unfiltered = OpenCVIngest().run(workspace, {"min_keyframes": 4, "quality_filter": False})
    assert unfiltered.num_keyframes == 4
    assert not any(unfiltered.rejected.values())


def test_keyframes_follow_capture_order(tmp_path):
    workspace = SceneWorkspace(tmp_path, "order")
    raw = workspace.dir("raw")
    rng = np.random.default_rng(7)
    shades = {}
    for frame in (10, 2, 1):
        image = Image.fromarray(rng.integers(30, 220, (64, 64, 3), dtype=np.uint8))
        image.save(raw / f"frame-{frame}-a1b2c3d4.png")
        shades[frame] = np.asarray(image, float).mean()
    OpenCVIngest().run(workspace, {"min_keyframes": 3})
    kept = [np.asarray(Image.open(workspace.path(f"keyframes/{i:04d}.jpg")), float).mean() for i in range(3)]
    assert np.allclose(kept, [shades[1], shades[2], shades[10]], atol=2)
