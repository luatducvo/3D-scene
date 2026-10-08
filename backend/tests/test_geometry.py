import numpy as np

from s3d_app.geometry import floor_and_walls, visible_vertices, visible_vertices_torch


def test_visibility_uses_depth_and_original_vertex_indices() -> None:
    points = np.array([[0, 0, 2], [1, 0, 2], [0, 0, 3], [0, 0, -1]], dtype=np.float32)
    intrinsic = np.array([[2, 0, 1], [0, 2, 1], [0, 0, 1]], dtype=np.float32)
    depth = np.zeros((3, 3), dtype=np.uint16)
    depth[1, 1] = 2000
    depth[1, 2] = 2000
    assert visible_vertices(points, np.eye(4), intrinsic, depth, 1000).tolist() == [0, 1]
    import torch

    device = "cuda" if torch.cuda.is_available() else "cpu"
    actual = visible_vertices_torch(torch.as_tensor(points, device=device), np.eye(4),
                                    intrinsic, depth, 1000)
    assert actual.tolist() == [0, 1]


def test_structure_finder_recognizes_floor_and_wall() -> None:
    floor = np.array([[x, y, 0] for x in np.linspace(0, 2, 25)
                      for y in np.linspace(0, 2, 25)])
    wall = np.array([[0, y, z] for y in np.linspace(0, 2, 25)
                     for z in np.linspace(0, 2, 25)])
    found = floor_and_walls(np.concatenate((floor, wall)))
    assert found[0]["kind"] == "floor"
    assert any(item["kind"] == "wall" for item in found)


def test_floor_consensus_resists_low_outliers():
    floor = np.array([[x, y, 0] for x in range(25) for y in range(25)], dtype=float)
    outliers = np.array([[0, 0, -10]] * 100, dtype=float)
    assert abs(floor_and_walls(np.concatenate((floor, outliers)))[0]["offset"]) < 0.01
