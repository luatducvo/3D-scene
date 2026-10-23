import numpy as np
import pytest
from scene_core.geometry import (
    fit_box,
    fit_plane,
)


def test_box_fit_encloses_the_points():
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
