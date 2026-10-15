"""CPU dense colored point cloud and projective TSDF fusion with marching cubes extraction."""
import numpy as np
from PIL import Image

from scene_core.contracts import MeshManifest
from scene_core.ports import StageAlgorithm


def write_ply(path, points, colors):
    """Binary little-endian PLY with float32 positions and 8-bit colors, as loaded by the viewer."""
    vertex = np.empty(len(points), dtype=[("x", "<f4"), ("y", "<f4"), ("z", "<f4"),
                                          ("red", "u1"), ("green", "u1"), ("blue", "u1")])
    for index, axis in enumerate("xyz"):
        vertex[axis] = points[:, index]
    for index, channel in enumerate(("red", "green", "blue")):
        vertex[channel] = colors[:, index]
    header = ("ply\nformat binary_little_endian 1.0\n"
              f"element vertex {len(vertex)}\n"
              "property float x\nproperty float y\nproperty float z\n"
              "property uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n")
    with open(path, "wb") as output:
        output.write(header.encode("ascii"))
        output.write(vertex.tobytes())


def voxel_downsample(points, colors, voxel):
    """Average positions and colors of the points falling in each voxel."""
    keys = np.floor(points / voxel).astype(np.int64)
    keys -= keys.min(axis=0)
    extent = keys.max(axis=0) + 1
    # One integer per voxel keeps the unique pass a fast one-dimensional sort.
    flat = (keys[:, 0] * extent[1] + keys[:, 1]) * extent[2] + keys[:, 2]
    _, inverse, counts = np.unique(flat, return_inverse=True, return_counts=True)
    mean = lambda values: np.bincount(inverse, weights=values, minlength=len(counts)) / counts
    return (np.column_stack([mean(points[:, axis]) for axis in range(3)]).astype(np.float32),
            np.column_stack([mean(colors[:, channel].astype(np.float64)) for channel in range(3)]))


def depth_edges(depth, threshold):
    """Pixels whose depth jumps by more than `threshold` (relative) to a 4-neighbor.

    Such pixels interpolate between a foreground object and the background behind it and float in
    the air as streaks ("flying pixels") when seen from another view.
    """
    padded = np.pad(depth, 1, mode="edge")
    neighbors = np.stack([padded[:-2, 1:-1], padded[2:, 1:-1], padded[1:-1, :-2], padded[1:-1, 2:]])
    # Pixels without depth (0) are not neighbors, so masked regions do not erode their border.
    jump = np.where(neighbors > 0, np.abs(neighbors - depth), 0).max(axis=0)
    return jump > threshold * np.maximum(depth, 1e-6)


def colored_points(frames, rgbs, min_confidence, edge_threshold=0):
    """Back-project every confident, non-edge pixel of every aligned Frame into the aligned world."""
    clouds, colors = [], []
    for frame, rgb in zip(frames, rgbs):
        valid = np.isfinite(frame["depth"]) & (frame["depth"] > 0) & np.isfinite(frame["conf"]) & (frame["conf"] >= min_confidence)
        if edge_threshold > 0:
            valid &= ~depth_edges(np.where(valid, frame["depth"], 0), edge_threshold)
        y, x = np.nonzero(valid)
        if not len(y):
            continue
        rays = np.column_stack([x, y, np.ones(len(x))]) @ np.linalg.inv(frame["K"]).T
        camera = rays * frame["depth"][y, x, None]
        clouds.append((camera @ frame["pose"][:3, :3].T + frame["pose"][:3, 3]).astype(np.float32))
        colors.append(rgb[y, x])
    if not clouds:
        raise ValueError("No valid reconstructed depth points")
    return np.concatenate(clouds), np.concatenate(colors)


class TSDFMesh(StageAlgorithm):
    name, stage = "mesh.tsdf", "mesh"
    reads, writes = ["align", "recon"], ["mesh"]
    manifest_type = MeshManifest

    def run(self, workspace, params):
        import trimesh
        from skimage.measure import marching_cubes

        voxel = float(params.get("voxel_size_m", .015))
        truncation = float(params.get("sdf_trunc_m", .05))
        if voxel <= 0 or truncation < voxel:
            raise ValueError("Require positive voxel_size_m and sdf_trunc_m >= voxel_size_m")
        frame_files = sorted(workspace.path("align/frames").glob("*.npz"))
        if not frame_files:
            raise ValueError("No aligned Frames")
        frames, rgbs = [], []
        for path in frame_files:
            with np.load(path, allow_pickle=False) as data:
                frame = dict(data)
            with Image.open(workspace.path(f"recon/rgb/{path.stem}.png")) as image:
                rgb = np.asarray(image.convert("RGB"))
            if rgb.shape[:2] != frame["depth"].shape:
                raise ValueError("RGB and depth must have the same model resolution")
            frames.append(frame)
            rgbs.append(rgb)
        # Keep the confident part of the depth, as Depth Anything 3's own point cloud export does.
        confidence = np.concatenate([frame["conf"][np.isfinite(frame["depth"]) & (frame["depth"] > 0)] for frame in frames])
        confidence = confidence[np.isfinite(confidence)]
        if not len(confidence):
            raise ValueError("No valid reconstructed depth points")
        points_percentile = float(params.get("points_confidence_percentile", 40))
        if not 0 <= points_percentile < 100:
            raise ValueError("Require 0 <= points_confidence_percentile < 100")
        cloud, cloud_colors = colored_points(frames, rgbs, float(np.percentile(confidence, points_percentile)),
                                             float(params.get("points_edge_threshold", .05)))
        # Bound the volume by per-axis percentiles so a few far outliers do not inflate it;
        # depth outside the volume is never integrated.
        percentile = float(params.get("bounds_percentile", 1))
        if not 0 <= percentile < 50:
            raise ValueError("Require 0 <= bounds_percentile < 50")
        low, high = np.percentile(cloud, [percentile, 100 - percentile], axis=0)
        inside = np.all((cloud >= low) & (cloud <= high), axis=1)
        cloud, cloud_colors = cloud[inside], cloud_colors[inside]
        points_voxel = float(params.get("points_voxel_m", .01))
        if points_voxel > 0:
            cloud, cloud_colors = voxel_downsample(cloud, cloud_colors, points_voxel)
        max_points = int(params.get("max_points", 3_000_000))
        if len(cloud) > max_points:
            keep = np.sort(np.random.default_rng(0).choice(len(cloud), max_points, replace=False))
            cloud, cloud_colors = cloud[keep], cloud_colors[keep]
        origin = low - 2 * truncation
        shape = np.ceil((high + 2 * truncation - origin) / voxel).astype(int) + 1
        total = int(np.prod(shape))
        if total > int(params.get("max_voxels", 32_000_000)):
            raise ValueError("TSDF volume exceeds max_voxels; increase voxel_size_m or reject reconstruction outliers")
        sums = np.zeros(total, np.float32)
        weights = np.zeros(total, np.float32)
        colors = np.zeros((total, 3), np.float32)
        for done, (frame, rgb) in enumerate(zip(frames, rgbs)):
            self.progress(done, len(frames), "frame")
            h, w = frame["depth"].shape
            for start in range(0, total, 100_000):
                indices = np.arange(start, min(start + 100_000, total))
                world = np.column_stack(np.unravel_index(indices, tuple(shape))) * voxel + origin
                camera = (world - frame["pose"][:3, 3]) @ frame["pose"][:3, :3]
                projected = camera @ frame["K"].T
                front = camera[:, 2] > 1e-6
                pixels = np.zeros((len(indices), 2), int)
                pixels[front] = np.rint(projected[front, :2] / projected[front, 2:3]).astype(int)
                valid = front & (pixels[:, 0] >= 0) & (pixels[:, 0] < w) & (pixels[:, 1] >= 0) & (pixels[:, 1] < h)
                rows = np.flatnonzero(valid)
                x, y = pixels[rows].T
                depth = frame["depth"][y, x]
                confidence = frame["conf"][y, x]
                sdf = depth - camera[rows, 2]
                keep = np.isfinite(depth) & (depth > 0) & np.isfinite(confidence) & (confidence > float(params.get("min_confidence", 0))) & (sdf >= -truncation)
                chosen = indices[rows[keep]]
                weight = np.clip(confidence[keep], .001, 1)
                sums[chosen] += np.clip(sdf[keep] / truncation, -1, 1) * weight
                weights[chosen] += weight
                colors[chosen] += rgb[y[keep], x[keep]] * weight[:, None]
        self.progress(len(frames), len(frames), "frame")
        tsdf = np.ones(total, np.float32)
        observed = weights > 0
        tsdf[observed] = sums[observed] / weights[observed]
        if not (tsdf.min() < 0 < tsdf.max()):
            raise ValueError("No observed TSDF zero crossing")
        vertices, faces, _, _ = marching_cubes(tsdf.reshape(tuple(shape)), level=0, spacing=(voxel,) * 3, mask=observed.reshape(tuple(shape)))
        sample = np.clip(np.rint(vertices / voxel).astype(int), 0, shape - 1)
        flat = np.ravel_multi_index(sample.T, tuple(shape))
        vertex_colors = np.clip(colors[flat] / np.maximum(weights[flat, None], 1e-8), 0, 255).astype(np.uint8)
        mesh = trimesh.Trimesh(vertices=vertices + origin, faces=faces, vertex_colors=vertex_colors, process=False)
        output = workspace.dir("mesh")
        mesh.export(output / "mesh.glb")
        write_ply(output / "points.ply", cloud, np.clip(np.rint(cloud_colors), 0, 255).astype(np.uint8))
        return MeshManifest(mesh_file="mesh/mesh.glb", points_file="mesh/points.ply",
                            num_faces=len(mesh.faces), num_points=len(cloud))
