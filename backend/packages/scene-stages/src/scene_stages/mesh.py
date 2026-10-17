"""Dense colored point cloud and projective TSDF fusion with marching cubes extraction.

The point cloud and the TSDF run on NumPy or, with `device: cuda`, on CuPy; marching cubes runs on the CPU.
"""

import json
import struct

import numpy as np
from PIL import Image
from scene_core.contracts import MeshManifest
from scene_core.ports import StageAlgorithm

from .arrays import array_module, to_numpy


def write_ply(path, points, colors):
    """Binary little-endian PLY with float32 positions and 8-bit colors, as loaded by the viewer."""
    vertex = np.empty(
        len(points),
        dtype=[
            ("x", "<f4"),
            ("y", "<f4"),
            ("z", "<f4"),
            ("red", "u1"),
            ("green", "u1"),
            ("blue", "u1"),
        ],
    )
    for index, axis in enumerate("xyz"):
        vertex[axis] = points[:, index]
    for index, channel in enumerate(("red", "green", "blue")):
        vertex[channel] = colors[:, index]
    header = (
        "ply\nformat binary_little_endian 1.0\n"
        f"element vertex {len(vertex)}\n"
        "property float x\nproperty float y\nproperty float z\n"
        "property uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n"
    )
    with open(path, "wb") as output:
        output.write(header.encode("ascii"))
        output.write(vertex.tobytes())


_PLY_TYPES = {
    "char": "i1",
    "int8": "i1",
    "uchar": "u1",
    "uint8": "u1",
    "short": "<i2",
    "int16": "<i2",
    "ushort": "<u2",
    "uint16": "<u2",
    "int": "<i4",
    "int32": "<i4",
    "uint": "<u4",
    "uint32": "<u4",
    "float": "<f4",
    "float32": "<f4",
    "double": "<f8",
    "float64": "<f8",
}


def read_ply_points(path):
    """Positions (N, 3) of the vertex element of a binary little-endian PLY, in file order."""
    with open(path, "rb") as source:
        if source.readline().strip() != b"ply":
            raise ValueError("Not a PLY file")
        fields, count, element = [], None, None
        while True:
            line = source.readline()
            if not line:
                raise ValueError("PLY header has no end_header")
            words = line.decode("ascii").split()
            if not words or words[0] in ("comment", "obj_info"):
                continue
            if words[0] == "end_header":
                break
            if words[0] == "format" and words[1] != "binary_little_endian":
                raise ValueError("Only binary little-endian PLY is supported")
            if words[0] == "element":
                element = words[1]
                if element == "vertex":
                    count = int(words[2])
                elif count is None:
                    raise ValueError("The PLY vertex element must come first")
            if words[0] == "property" and element == "vertex":
                if words[1] == "list" or words[1] not in _PLY_TYPES:
                    raise ValueError(f"Unsupported PLY vertex property: {line.decode().strip()}")
                fields.append((words[2], _PLY_TYPES[words[1]]))
        if count is None:
            raise ValueError("PLY has no vertex element")
        vertex = np.fromfile(source, dtype=np.dtype(fields), count=count)
    if len(vertex) != count:
        raise ValueError("PLY vertex data is truncated")
    return np.stack([vertex[axis] for axis in "xyz"], axis=1).astype(np.float64)


def read_glb_positions(path):
    """POSITION values (N, 3) of every primitive of every mesh of a binary glTF, concatenated in
    `meshes` then `primitives` order. Node transforms are not applied: mesh Algorithms write
    positions in the aligned frame."""
    with open(path, "rb") as source:
        data = source.read()
    if len(data) < 20 or struct.unpack_from("<I", data)[0] != 0x46546C67:
        raise ValueError("Not a binary glTF file")
    chunks, position = {}, 12
    while position + 8 <= len(data):
        length, kind = struct.unpack_from("<II", data, position)
        chunks.setdefault(kind, data[position + 8 : position + 8 + length])
        position += 8 + length
    if 0x4E4F534A not in chunks:
        raise ValueError("Binary glTF has no JSON chunk")
    doc = json.loads(chunks[0x4E4F534A])
    binary = chunks.get(0x004E4942, b"")
    positions = []
    for mesh in doc.get("meshes", []):
        for primitive in mesh["primitives"]:
            accessor = doc["accessors"][primitive["attributes"]["POSITION"]]
            if accessor["componentType"] != 5126 or accessor["type"] != "VEC3":
                raise ValueError("glTF POSITION must be float VEC3")
            view = doc["bufferViews"][accessor["bufferView"]]
            if view.get("buffer", 0) != 0 or "sparse" in accessor:
                raise ValueError("glTF POSITION must live in the GLB binary chunk")
            start = view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
            stride = view.get("byteStride", 12)
            count = accessor["count"]
            if count and start + stride * (count - 1) + 12 > len(binary):
                raise ValueError("glTF POSITION data is truncated")
            rows = np.ndarray((count, 3), "<f4", binary, start, (stride, 4))
            positions.append(rows.astype(np.float64))
    return np.concatenate(positions) if positions else np.zeros((0, 3))


def voxel_downsample(points, colors, voxel, xp=np):
    """Average positions and colors of the points falling in each voxel."""
    keys = xp.floor(points / voxel).astype(xp.int64)
    keys -= keys.min(axis=0)
    extent = keys.max(axis=0) + 1
    # One integer per voxel keeps the unique pass a fast one-dimensional sort.
    flat = (keys[:, 0] * extent[1] + keys[:, 1]) * extent[2] + keys[:, 2]
    _, inverse, counts = xp.unique(flat, return_inverse=True, return_counts=True)
    inverse = inverse.ravel()

    def mean(values):
        return xp.bincount(inverse, weights=values, minlength=len(counts)) / counts

    return (
        xp.stack([mean(points[:, axis]) for axis in range(3)], axis=1).astype(xp.float32),
        xp.stack([mean(colors[:, channel].astype(xp.float64)) for channel in range(3)], axis=1),
    )


def depth_edges(depth, threshold, xp=np):
    """Pixels whose depth jumps by more than `threshold` (relative) to a 4-neighbor.

    Such pixels interpolate between a foreground object and the background behind it and float in
    the air as streaks ("flying pixels") when seen from another view.
    """
    padded = xp.pad(depth, 1, mode="edge")
    neighbors = xp.stack([padded[:-2, 1:-1], padded[2:, 1:-1], padded[1:-1, :-2], padded[1:-1, 2:]])
    # Pixels without depth (0) are not neighbors, so masked regions do not erode their border.
    jump = xp.where(neighbors > 0, xp.abs(neighbors - depth), 0).max(axis=0)
    return jump > threshold * xp.maximum(depth, 1e-6)


def colored_points(frames, rgbs, min_confidence, edge_threshold=0, xp=np):
    """Back-project every confident, non-edge pixel of every aligned Frame into the aligned world.

    `frames` and `rgbs` hold arrays of module `xp`."""
    clouds, colors = [], []
    for frame, rgb in zip(frames, rgbs, strict=True):
        valid = (
            xp.isfinite(frame["depth"])
            & (frame["depth"] > 0)
            & xp.isfinite(frame["conf"])
            & (frame["conf"] >= min_confidence)
        )
        if edge_threshold > 0:
            valid &= ~depth_edges(xp.where(valid, frame["depth"], 0), edge_threshold, xp)
        y, x = xp.nonzero(valid)
        if not len(y):
            continue
        rays = xp.stack([x, y, xp.ones(len(x))], axis=1) @ xp.linalg.inv(frame["K"]).T
        camera = rays * frame["depth"][y, x, None]
        clouds.append((camera @ frame["pose"][:3, :3].T + frame["pose"][:3, 3]).astype(xp.float32))
        colors.append(rgb[y, x])
    if not clouds:
        raise ValueError("No valid reconstructed depth points")
    return xp.concatenate(clouds), xp.concatenate(colors)


class TSDFMesh(StageAlgorithm):
    name, stage = "mesh.tsdf", "mesh"
    reads, writes = ["align", "recon"], ["mesh"]
    manifest_type = MeshManifest

    def run(self, workspace, params):
        import trimesh
        from skimage.measure import marching_cubes

        voxel = float(params.get("voxel_size_m", 0.015))
        truncation = float(params.get("sdf_trunc_m", 0.05))
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
        confidence = np.concatenate(
            [frame["conf"][np.isfinite(frame["depth"]) & (frame["depth"] > 0)] for frame in frames]
        )
        confidence = confidence[np.isfinite(confidence)]
        if not len(confidence):
            raise ValueError("No valid reconstructed depth points")
        points_percentile = float(params.get("points_confidence_percentile", 40))
        if not 0 <= points_percentile < 100:
            raise ValueError("Require 0 <= points_confidence_percentile < 100")
        xp = array_module(params)
        # Frames move to the array module once; every pass below reads them there.
        device_frames = [
            {key: xp.asarray(frame[key]) for key in ("depth", "conf", "pose", "K")}
            for frame in frames
        ]
        device_rgbs = [xp.asarray(rgb) for rgb in rgbs]
        cloud, cloud_colors = colored_points(
            device_frames,
            device_rgbs,
            float(np.percentile(confidence, points_percentile)),
            float(params.get("points_edge_threshold", 0.05)),
            xp,
        )
        # Bound the volume by per-axis percentiles so a few far outliers do not inflate it;
        # depth outside the volume is never integrated.
        percentile = float(params.get("bounds_percentile", 1))
        if not 0 <= percentile < 50:
            raise ValueError("Require 0 <= bounds_percentile < 50")
        low, high = (
            to_numpy(bound).astype(float)
            for bound in xp.percentile(cloud, xp.asarray([percentile, 100 - percentile]), axis=0)
        )
        inside = xp.all((cloud >= xp.asarray(low)) & (cloud <= xp.asarray(high)), axis=1)
        cloud, cloud_colors = cloud[inside], cloud_colors[inside]
        points_voxel = float(params.get("points_voxel_m", 0.01))
        if points_voxel > 0:
            cloud, cloud_colors = voxel_downsample(cloud, cloud_colors, points_voxel, xp)
        max_points = int(params.get("max_points", 3_000_000))
        if len(cloud) > max_points:
            keep = np.sort(np.random.default_rng(0).choice(len(cloud), max_points, replace=False))
            cloud, cloud_colors = cloud[xp.asarray(keep)], cloud_colors[xp.asarray(keep)]
        origin = low - 2 * truncation
        shape = np.ceil((high + 2 * truncation - origin) / voxel).astype(int) + 1
        total = int(np.prod(shape))
        if total > int(params.get("max_voxels", 32_000_000)):
            raise ValueError(
                "TSDF volume exceeds max_voxels; increase voxel_size_m or reject reconstruction outliers"
            )
        # Voxels per integration pass; a GPU takes millions at once, the CPU's memory bounds it too.
        chunk = int(params.get("chunk_voxels", 2_000_000))
        if chunk < 1:
            raise ValueError("chunk_voxels must be positive")
        min_confidence = float(params.get("min_confidence", 0))
        sums = xp.zeros(total, xp.float32)
        weights = xp.zeros(total, xp.float32)
        colors = xp.zeros((total, 3), xp.float32)
        grid_shape = xp.asarray(shape)
        device_origin = xp.asarray(origin)
        for done, (frame, rgb) in enumerate(zip(device_frames, device_rgbs, strict=True)):
            self.progress(done, len(frames), "frame")
            h, w = frame["depth"].shape
            for start in range(0, total, chunk):
                indices = xp.arange(start, min(start + chunk, total))
                cell = xp.stack(
                    [
                        indices // (grid_shape[1] * grid_shape[2]),
                        (indices // grid_shape[2]) % grid_shape[1],
                        indices % grid_shape[2],
                    ],
                    axis=1,
                )
                world = cell * voxel + device_origin
                camera = (world - frame["pose"][:3, 3]) @ frame["pose"][:3, :3]
                projected = camera @ frame["K"].T
                front = camera[:, 2] > 1e-6
                z = xp.where(front, projected[:, 2], 1.0)
                x, y = xp.rint(projected[:, 0] / z), xp.rint(projected[:, 1] / z)
                rows = xp.flatnonzero(front & (x >= 0) & (x < w) & (y >= 0) & (y < h))
                x, y = x[rows].astype(xp.int64), y[rows].astype(xp.int64)
                depth = frame["depth"][y, x]
                confidence = frame["conf"][y, x]
                sdf = depth - camera[rows, 2]
                keep = (
                    xp.isfinite(depth)
                    & (depth > 0)
                    & xp.isfinite(confidence)
                    & (confidence > min_confidence)
                    & (sdf >= -truncation)
                )
                chosen = indices[rows[keep]]
                weight = xp.clip(confidence[keep], 0.001, 1)
                sums[chosen] += xp.clip(sdf[keep] / truncation, -1, 1) * weight
                weights[chosen] += weight
                colors[chosen] += rgb[y[keep], x[keep]] * weight[:, None]
        self.progress(len(frames), len(frames), "frame")
        tsdf = xp.ones(total, xp.float32)
        observed = weights > 0
        tsdf[observed] = sums[observed] / weights[observed]
        tsdf, observed, weights, colors = (
            to_numpy(array) for array in (tsdf, observed, weights, colors)
        )
        cloud, cloud_colors = to_numpy(cloud), to_numpy(cloud_colors)
        if not (tsdf.min() < 0 < tsdf.max()):
            raise ValueError("No observed TSDF zero crossing")
        vertices, faces, _, _ = marching_cubes(
            tsdf.reshape(tuple(shape)),
            level=0,
            spacing=(voxel,) * 3,
            mask=observed.reshape(tuple(shape)),
        )
        sample = np.clip(np.rint(vertices / voxel).astype(int), 0, shape - 1)
        flat = np.ravel_multi_index(sample.T, tuple(shape))
        vertex_colors = np.clip(
            colors[flat] / np.maximum(weights[flat, None], 1e-8), 0, 255
        ).astype(np.uint8)
        mesh = trimesh.Trimesh(
            vertices=vertices + origin, faces=faces, vertex_colors=vertex_colors, process=False
        )
        output = workspace.dir("mesh")
        mesh.export(output / "mesh.glb")
        write_ply(
            output / "points.ply", cloud, np.clip(np.rint(cloud_colors), 0, 255).astype(np.uint8)
        )
        return MeshManifest(
            mesh_file="mesh/mesh.glb",
            points_file="mesh/points.ply",
            num_faces=len(mesh.faces),
            num_points=len(cloud),
        )
