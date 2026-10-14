"""CPU projective TSDF fusion with color integration and marching cubes extraction."""
import numpy as np
from PIL import Image

from scene_core.contracts import MeshManifest
from scene_core.ports import StageAlgorithm
from .lift import unproject


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
        clouds = []
        for path in frame_files:
            with np.load(path, allow_pickle=False) as frame:
                valid = np.isfinite(frame["depth"]) & (frame["depth"] > 0) & (frame["conf"] > float(params.get("min_confidence", 0)))
                cloud = unproject(frame["depth"], frame["K"], frame["pose"], valid)
                if len(cloud):
                    clouds.append(cloud[::max(1, len(cloud) // 10000)])
        if not clouds:
            raise ValueError("No valid reconstructed depth points")
        cloud = np.concatenate(clouds)
        # Bound the volume by per-axis percentiles so a few far outliers do not inflate it;
        # depth outside the volume is never integrated.
        percentile = float(params.get("bounds_percentile", 1))
        if not 0 <= percentile < 50:
            raise ValueError("Require 0 <= bounds_percentile < 50")
        low, high = np.percentile(cloud, [percentile, 100 - percentile], axis=0)
        cloud = cloud[np.all((cloud >= low) & (cloud <= high), axis=1)]
        origin = low - 2 * truncation
        shape = np.ceil((high + 2 * truncation - origin) / voxel).astype(int) + 1
        total = int(np.prod(shape))
        if total > int(params.get("max_voxels", 32_000_000)):
            raise ValueError("TSDF volume exceeds max_voxels; increase voxel_size_m or reject reconstruction outliers")
        sums = np.zeros(total, np.float32)
        weights = np.zeros(total, np.float32)
        colors = np.zeros((total, 3), np.float32)
        for done, path in enumerate(frame_files):
            self.progress(done, len(frame_files), "frame")
            with np.load(path, allow_pickle=False) as data:
                frame = dict(data)
            with Image.open(workspace.path(f"recon/rgb/{path.stem}.png")) as image:
                rgb = np.asarray(image.convert("RGB"))
            h, w = frame["depth"].shape
            if rgb.shape[:2] != (h, w):
                raise ValueError("RGB and depth must have the same model resolution")
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
        self.progress(len(frame_files), len(frame_files), "frame")
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
        trimesh.PointCloud(cloud).export(output / "points.ply")
        return MeshManifest(mesh_file="mesh/mesh.glb", points_file="mesh/points.ply", num_faces=len(mesh.faces))
