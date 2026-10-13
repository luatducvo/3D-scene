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
