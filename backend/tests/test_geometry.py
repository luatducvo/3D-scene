import numpy as np
import pytest
from scene_core.domain import OrientedBox
from scene_core.geometry import (
    box_surface_distance,
    fit_box,
    fit_plane,
    footprint_overlap,
)


def test_rotated_box_and_true_surface_distance():
    box = OrientedBox(center=(0, 0, 1), size=(2, 2, 2), yaw=np.pi / 4)
    other = OrientedBox(center=(4, 0, 1), size=(2, 2, 2), yaw=0)
    assert box_surface_distance(box, other) == pytest.approx(3 - np.sqrt(2))
    assert footprint_overlap(box, box) == pytest.approx(4)
    points = np.array([[x, y, z] for x in (-2, 2) for y in (-1, 1) for z in (0, 3)])
    result = fit_box(points)
    assert sorted(result.size) == pytest.approx([2, 3, 4])
    assert result.center == pytest.approx([0, 0, 1.5])


def test_plane_fit_rejects_outliers():
    rng = np.random.default_rng(42)
    floor = np.column_stack([rng.uniform(-3, 3, (200, 2)), np.zeros(200)])
    points = np.vstack([floor, rng.uniform(-3, 3, (20, 3))])
    normal, offset, inliers = fit_plane(points, threshold=0.01)
    assert abs(normal[2]) == pytest.approx(1)
    assert abs(offset) < 0.01
    assert inliers.sum() >= 200
