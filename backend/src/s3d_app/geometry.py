"""S2: aligned structures and depth-tested vertex visibility."""

import json
import os
import sys

import numpy as np
from PIL import Image
from plyfile import PlyData

from s3d_app.pipeline import artifact_dir


def floor_and_walls(points: np.ndarray, *, seed: int = 0) -> list[dict]:
    """Find a horizontal floor and up to four vertical planes without labels."""
    if len(points) < 3:
        return []
    floor_z = float(np.quantile(points[:, 2], 0.05))
    floor_mask = np.abs(points[:, 2] - floor_z) < 0.07
    structures = []
    if floor_mask.sum() >= 3:
        structures.append({"id": "floor", "kind": "floor", "normal": [0.0, 0.0, 1.0],
                           "offset": floor_z, "vertices": int(floor_mask.sum())})
    candidates = points[points[:, 2] > floor_z + 0.2]
    if len(candidates) < 100:
        return structures
    rng = np.random.default_rng(seed)
    remaining = candidates.copy()
    for number in range(4):
        if len(remaining) < 100:
            break
        sample = remaining[rng.choice(len(remaining), min(len(remaining), 5000), replace=False)]
        best_normal = None
        best_offset = 0.0
        best_count = 0
        for _ in range(250):
            pair = sample[rng.choice(len(sample), 2, replace=False), :2]
            edge = pair[1] - pair[0]
            norm = np.linalg.norm(edge)
            if norm < 0.3:
                continue
            normal = np.array([-edge[1], edge[0]]) / norm
            offset = float(normal @ pair[0])
            inliers = np.abs(sample[:, :2] @ normal - offset) < 0.06
            count = int(inliers.sum())
            if count > best_count and np.ptp(sample[inliers, 2]) > 0.7:
                best_normal, best_offset, best_count = normal, offset, count
        if best_normal is None or best_count < max(30, len(sample) * 0.025):
            break
        inliers = np.abs(remaining[:, :2] @ best_normal - best_offset) < 0.06
        wall_points = remaining[inliers]
        structures.append({"id": f"wall-{number + 1}", "kind": "wall",
                           "normal": [float(best_normal[0]), float(best_normal[1]), 0.0],
                           "offset": best_offset, "vertices": int(inliers.sum()),
                           "min": wall_points.min(axis=0).tolist(),
                           "max": wall_points.max(axis=0).tolist()})
        remaining = remaining[~inliers]
    return structures


def visible_vertices(points: np.ndarray, pose: np.ndarray, intrinsic: np.ndarray,
                     depth: np.ndarray, depth_shift: float,
                     tolerance: float = 0.1) -> np.ndarray:
    """Return source mesh vertex indices whose projection agrees with depth."""
    camera = (points - pose[:3, 3]) @ pose[:3, :3]
    forward = camera[:, 2] > 0.01
    indices = np.flatnonzero(forward)
    if not len(indices):
        return np.empty(0, dtype=np.int32)
    xyz = camera[indices]
    u = np.rint(intrinsic[0, 0] * xyz[:, 0] / xyz[:, 2] + intrinsic[0, 2]).astype(np.int32)
    v = np.rint(intrinsic[1, 1] * xyz[:, 1] / xyz[:, 2] + intrinsic[1, 2]).astype(np.int32)
    inside = (u >= 0) & (v >= 0) & (u < depth.shape[1]) & (v < depth.shape[0])
    indices = indices[inside]
    xyz = xyz[inside]
    observed = depth[v[inside], u[inside]].astype(np.float32) / depth_shift
    agrees = (observed > 0) & (np.abs(observed - xyz[:, 2]) < tolerance)
    return indices[agrees].astype(np.int32)


def visible_vertices_torch(points, pose: np.ndarray, intrinsic: np.ndarray,
                           depth: np.ndarray, depth_shift: float,
                           tolerance: float = 0.1) -> np.ndarray:
    import torch

    pose_tensor = torch.as_tensor(pose, dtype=points.dtype, device=points.device)
    camera = (points - pose_tensor[:3, 3]) @ pose_tensor[:3, :3]
    indices = torch.nonzero(camera[:, 2] > 0.01).flatten()
    xyz = camera[indices]
    u = torch.round(intrinsic[0, 0] * xyz[:, 0] / xyz[:, 2] + intrinsic[0, 2]).long()
    v = torch.round(intrinsic[1, 1] * xyz[:, 1] / xyz[:, 2] + intrinsic[1, 2]).long()
    inside = (u >= 0) & (v >= 0) & (u < depth.shape[1]) & (v < depth.shape[0])
    indices, xyz, u, v = indices[inside], xyz[inside], u[inside], v[inside]
    depth_tensor = torch.as_tensor(depth.astype(np.float32), device=points.device) / depth_shift
    observed = depth_tensor[v, u]
    agrees = (observed > 0) & (torch.abs(observed - xyz[:, 2]) < tolerance)
    return indices[agrees].cpu().numpy().astype(np.int32)


def run(scene_id: str) -> None:
    import torch

    source = artifact_dir(scene_id, "S1")
    target = artifact_dir(scene_id, "S2")
    if all((target / filename).is_file() for filename in ("geometry.npz", "structures.json", "metrics.json")):
        return
    mesh = PlyData.read(source / "mesh/vh_clean_2.ply")
    vertex = mesh["vertex"].data
    points = np.column_stack((vertex["x"], vertex["y"], vertex["z"])).astype(np.float32)
    device = os.getenv("S3D_GEOMETRY_DEVICE", "cuda")
    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable for S2 visibility")
    gpu_points = torch.as_tensor(points, device=device)
    superpoints = np.load(source / "mesh/superpoints.npy", allow_pickle=False)
    calibration = json.loads((source / "calib/intrinsics.json").read_text())
    intrinsic = np.asarray(calibration["depth"]["intrinsic"], dtype=np.float64)
    offsets = [0]
    indices = []
    frame_ids = []
    for path in sorted((source / "frames/depth").glob("*.png")):
        fid = int(path.stem)
        depth = np.asarray(Image.open(path))
        pose = np.loadtxt(source / "frames/pose" / f"{path.stem}.txt")
        visible = visible_vertices_torch(gpu_points, pose, intrinsic, depth,
                                         calibration["depth_shift"])
        indices.append(visible)
        offsets.append(offsets[-1] + len(visible))
        frame_ids.append(fid)
    target.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(target / "geometry.npz", points=points, superpoints=superpoints,
                        frame_ids=np.asarray(frame_ids, dtype=np.int32),
                        visibility_offsets=np.asarray(offsets, dtype=np.int64),
                        visibility_indices=np.concatenate(indices) if indices else np.empty(0, np.int32))
    (target / "structures.json").write_text(json.dumps(floor_and_walls(points), indent=2))
    (target / "metrics.json").write_text(json.dumps({"device": device,
        "peak_torch_reserved_mb": round(torch.cuda.max_memory_reserved() / 1048576)
        if device == "cuda" else 0}))


if __name__ == "__main__":
    run(sys.argv[1])
