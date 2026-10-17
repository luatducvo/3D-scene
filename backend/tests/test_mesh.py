import numpy as np
from PIL import Image
from scene_core.contracts import SceneWorkspace
from scene_stages.mesh import TSDFMesh


def test_tsdf_mesh_from_metric_depth_is_a_colored_surface(tmp_path):
    import trimesh

    workspace = SceneWorkspace(tmp_path, "mesh")
    depth = np.ones((32, 32), np.float32)
    np.savez(
        workspace.dir("align/frames") / "0000.npz",
        depth=depth,
        conf=np.ones_like(depth),
        pose=np.eye(4),
        K=np.array([[32, 0, 16], [0, 32, 16], [0, 0, 1]]),
    )
    Image.new("RGB", (32, 32), (200, 50, 20)).save(workspace.dir("recon/rgb") / "0000.png")
    manifest = TSDFMesh().run(workspace, {"voxel_size_m": 0.04, "sdf_trunc_m": 0.08})
    mesh = trimesh.load(workspace.path(manifest.mesh_file), force="mesh")
    assert manifest.num_faces > 100
    assert abs(np.median(mesh.vertices[:, 2]) - 1) < 0.08
    assert workspace.path(manifest.points_file).is_file()


def test_tsdf_volume_ignores_sparse_far_outliers(tmp_path):
    import pytest
    import trimesh

    workspace = SceneWorkspace(tmp_path, "outliers")
    depth = np.ones((32, 32), np.float32)
    depth[0, :3] = 50  # under 1 % of the points, tens of meters away
    np.savez(
        workspace.dir("align/frames") / "0000.npz",
        depth=depth,
        conf=np.ones_like(depth),
        pose=np.eye(4),
        K=np.array([[32, 0, 16], [0, 32, 16], [0, 0, 1]]),
    )
    Image.new("RGB", (32, 32), (200, 50, 20)).save(workspace.dir("recon/rgb") / "0000.png")
    # The edge filter alone would drop these isolated outliers; check the bounds on their own.
    params = {
        "voxel_size_m": 0.04,
        "sdf_trunc_m": 0.08,
        "max_voxels": 200_000,
        "points_edge_threshold": 0,
    }
    with pytest.raises(ValueError, match="max_voxels"):
        TSDFMesh().run(workspace, {**params, "bounds_percentile": 0})
    manifest = TSDFMesh().run(workspace, params)
    mesh = trimesh.load(workspace.path(manifest.mesh_file), force="mesh")
    assert manifest.num_faces > 100
    assert np.abs(mesh.vertices[:, :2]).max() < 1


def _ply_vertices(path):
    data = path.read_bytes()
    header, body = data.split(b"end_header\n", 1)
    assert b"format binary_little_endian" in header and b"property uchar red" in header
    count = int(header.split(b"element vertex ")[1].split(b"\n")[0])
    return np.frombuffer(
        body,
        dtype=[
            ("x", "<f4"),
            ("y", "<f4"),
            ("z", "<f4"),
            ("red", "u1"),
            ("green", "u1"),
            ("blue", "u1"),
        ],
        count=count,
    )


def test_point_cloud_is_dense_colored_and_confident(tmp_path):
    workspace = SceneWorkspace(tmp_path, "points")
    depth = np.ones((32, 32), np.float32)
    confidence = np.full_like(depth, 5)
    confidence[:, :8] = 1  # the least confident quarter is left out of the cloud
    np.savez(
        workspace.dir("align/frames") / "0000.npz",
        depth=depth,
        conf=confidence,
        pose=np.eye(4),
        K=np.array([[32, 0, 16], [0, 32, 16], [0, 0, 1]]),
    )
    Image.new("RGB", (32, 32), (200, 50, 20)).save(workspace.dir("recon/rgb") / "0000.png")
    params = {
        "voxel_size_m": 0.04,
        "sdf_trunc_m": 0.08,
        "bounds_percentile": 0,
        "points_voxel_m": 0,
    }
    manifest = TSDFMesh().run(workspace, params)
    vertices = _ply_vertices(workspace.path(manifest.points_file))
    assert manifest.num_points == len(vertices) == 32 * 24
    assert np.all(vertices["x"] >= (8 - 16) / 32 - 1e-6)
    assert np.allclose(vertices["z"], 1)
    assert np.all((vertices["red"] == 200) & (vertices["green"] == 50) & (vertices["blue"] == 20))
    manifest = TSDFMesh().run(workspace, {**params, "points_voxel_m": 0.1})
    assert 0 < manifest.num_points < 32 * 24


def test_point_cloud_drops_flying_pixels_at_depth_edges(tmp_path):
    workspace = SceneWorkspace(tmp_path, "edges")
    depth = np.full((32, 32), 3, np.float32)
    depth[8:24, 8:24] = 1  # a box in front of a wall
    np.savez(
        workspace.dir("align/frames") / "0000.npz",
        depth=depth,
        conf=np.ones_like(depth),
        pose=np.eye(4),
        K=np.array([[32, 0, 16], [0, 32, 16], [0, 0, 1]]),
    )
    Image.new("RGB", (32, 32), (200, 50, 20)).save(workspace.dir("recon/rgb") / "0000.png")
    params = {
        "voxel_size_m": 0.04,
        "sdf_trunc_m": 0.08,
        "bounds_percentile": 0,
        "points_voxel_m": 0,
    }
    assert TSDFMesh().run(workspace, {**params, "points_edge_threshold": 0}).num_points == 32 * 32
    manifest = TSDFMesh().run(workspace, params)
    vertices = _ply_vertices(workspace.path(manifest.points_file))
    # Both sides of the 16x16 box outline go: its inner ring, and the outer ring without the four
    # corners, which only touch the box diagonally.
    assert manifest.num_points == 32 * 32 - (16 * 16 - 14 * 14) - (18 * 18 - 16 * 16 - 4)
    assert set(np.round(vertices["z"], 3)) == {1, 3}
