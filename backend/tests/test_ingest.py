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


def test_a_prepared_jpeg_is_kept_byte_for_byte_and_others_are_reencoded(tmp_path):
    workspace = SceneWorkspace(tmp_path, "once")
    raw = workspace.dir("raw")
    rng = np.random.default_rng(9)

    def photo(name, size=(64, 48), **save):
        Image.fromarray(rng.integers(30, 220, (size[1], size[0], 3), dtype=np.uint8)).save(
            raw / name, **save
        )

    photo("1-prepared.jpg", quality=95)
    exif = Image.Exif()
    exif[0x8825] = {2: (10.0, 0.0, 0.0)}  # GPS
    photo("2-gps.jpg", exif=exif)
    photo("3-large.jpg", size=(200, 100))
    photo("4-comment.jpg", comment=b"camera serial")
    photo("5-lossless.png")
    OpenCVIngest().run(workspace, {"min_keyframes": 5, "long_side": 100})
    keyframes = [workspace.path(f"keyframes/{i:04d}.jpg") for i in range(5)]
    assert keyframes[0].read_bytes() == (raw / "1-prepared.jpg").read_bytes()
    for keyframe, name in zip(keyframes[1:4], ("2-gps", "3-large", "4-comment"), strict=True):
        assert keyframe.read_bytes() != (raw / f"{name}.jpg").read_bytes()
    with Image.open(keyframes[1]) as kept:
        assert not kept.getexif()
    with Image.open(keyframes[2]) as kept:
        assert kept.size == (100, 50)
    with Image.open(keyframes[3]) as kept:
        assert "comment" not in kept.info
    with Image.open(keyframes[4]) as kept:
        assert kept.format == "JPEG"


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
    kept = [
        np.asarray(Image.open(workspace.path(f"keyframes/{i:04d}.jpg")), float).mean()
        for i in range(3)
    ]
    assert np.allclose(kept, [shades[1], shades[2], shades[10]], atol=2)
