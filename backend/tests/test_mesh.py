import numpy as np
from PIL import Image
from scene_core.contracts import SceneWorkspace
from scene_stages.mesh import TSDFMesh


def test_tsdf_mesh_from_metric_depth_is_a_colored_surface(tmp_path):
    import trimesh
    workspace = SceneWorkspace(tmp_path, "mesh")
    depth = np.ones((32, 32), np.float32)
    np.savez(workspace.dir("align/frames") / "0000.npz", depth=depth, conf=np.ones_like(depth), pose=np.eye(4), K=np.array([[32, 0, 16], [0, 32, 16], [0, 0, 1]]))
    Image.new("RGB", (32, 32), (200, 50, 20)).save(workspace.dir("recon/rgb") / "0000.png")
    manifest = TSDFMesh().run(workspace, {"voxel_size_m": .04, "sdf_trunc_m": .08})
    mesh = trimesh.load(workspace.path(manifest.mesh_file), force="mesh")
    assert manifest.num_faces > 100
    assert abs(np.median(mesh.vertices[:, 2]) - 1) < .08
    assert workspace.path(manifest.points_file).is_file()


def test_tsdf_volume_ignores_sparse_far_outliers(tmp_path):
    import pytest
    import trimesh
    workspace = SceneWorkspace(tmp_path, "outliers")
    depth = np.ones((32, 32), np.float32)
    depth[0, :3] = 50  # under 1 % of the points, tens of meters away
    np.savez(workspace.dir("align/frames") / "0000.npz", depth=depth, conf=np.ones_like(depth), pose=np.eye(4), K=np.array([[32, 0, 16], [0, 32, 16], [0, 0, 1]]))
    Image.new("RGB", (32, 32), (200, 50, 20)).save(workspace.dir("recon/rgb") / "0000.png")
    params = {"voxel_size_m": .04, "sdf_trunc_m": .08, "max_voxels": 200_000}
    with pytest.raises(ValueError, match="max_voxels"):
        TSDFMesh().run(workspace, {**params, "bounds_percentile": 0})
    manifest = TSDFMesh().run(workspace, params)
    mesh = trimesh.load(workspace.path(manifest.mesh_file), force="mesh")
    assert manifest.num_faces > 100
    assert np.abs(mesh.vertices[:, :2]).max() < 1
