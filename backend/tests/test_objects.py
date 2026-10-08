import numpy as np

from s3d_app.objects import best_frames, dominant_color


def test_dominant_color_keeps_bright_saturated_red():
    pixels = np.asarray([[255, 12, 20], [230, 10, 20], [251, 20, 22],
                         [245, 245, 245]], dtype=np.uint8)
    name, swatch = dominant_color(pixels)
    assert name == "red"
    assert swatch[0] > 200 and swatch[1] < 30


def test_best_frames_count_visible_vertices():
    instance_ids = np.asarray([1, 0, 1, 0, 1], dtype=np.int32)
    frame_ids = np.asarray([0, 10, 20], dtype=np.int32)
    offsets = np.asarray([0, 2, 5, 7], dtype=np.int64)
    indices = np.asarray([0, 1, 0, 2, 4, 1, 3], dtype=np.int32)
    assert best_frames(instance_ids, frame_ids, offsets, indices, 1) == [10, 0]
