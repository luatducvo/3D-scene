"""Mask graph clustering using geometric cross-view visibility consensus."""

import hashlib
import json
from collections import defaultdict

import numpy as np
from PIL import Image
from scene_core.contracts import LiftManifest
from scene_core.ports import StageAlgorithm


def unproject(depth, intrinsics, pose, mask):
    y, x = np.nonzero(mask & np.isfinite(depth) & (depth > 0))
    z = depth[y, x]
    rays = np.column_stack([x, y, np.ones(len(x))]) @ np.linalg.inv(intrinsics).T
    return (rays * z[:, None]) @ pose[:3, :3].T + pose[:3, 3]


def support(points, frame, mask, tolerance):
    camera = (points - frame["pose"][:3, 3]) @ frame["pose"][:3, :3]
    projected = camera @ frame["K"].T
    front = camera[:, 2] > 1e-6
    pixels = np.zeros((len(points), 2), dtype=int)
    pixels[front] = np.rint(projected[front, :2] / projected[front, 2:3]).astype(int)
    h, w = mask.shape
    visible = (
        front & (pixels[:, 0] >= 0) & (pixels[:, 0] < w) & (pixels[:, 1] >= 0) & (pixels[:, 1] < h)
    )
    indices = np.flatnonzero(visible)
    if not len(indices):
        return 0.0
    x, y = pixels[indices].T
    valid_depth = np.isfinite(frame["depth"][y, x]) & (frame["depth"][y, x] > 0)
    consistent = valid_depth & (abs(frame["depth"][y, x] - camera[indices, 2]) <= tolerance)
    if not consistent.any():
        return 0.0
    return float(mask[y[consistent], x[consistent]].mean())


def _agglomerate(affinity, node_frames, threshold):
    """Greedily merge the pair of groups with the highest mean pairwise affinity above threshold.

    Groups sharing a Frame never merge. Each group is stored at the index of its lowest member and
    keeps the summed affinity to every other group, so a merge updates one row instead of
    rescanning every member pair. Ties go to the lowest (first, second) group index.
    """
    count = len(node_frames)
    if not count:
        return []
    frame_ids = {frame: index for index, frame in enumerate(dict.fromkeys(node_frames))}
    seen = np.zeros((count, len(frame_ids)))
    seen[np.arange(count), [frame_ids[frame] for frame in node_frames]] = 1
    conflict = seen @ seen.T > 0
    totals = affinity.astype(float).copy()
    sizes = np.ones(count)
    alive = np.ones(count, bool)
    members = {i: {i} for i in range(count)}
    upper = np.triu(np.ones((count, count), bool), 1)
    while True:
        allowed = upper & alive[:, None] & alive[None, :] & ~conflict
        mean = np.where(allowed, totals / np.outer(sizes, sizes), -np.inf)
        flat = int(np.argmax(mean))
        if not mean.flat[flat] > threshold:
            break
        first, second = divmod(flat, count)
        totals[first] += totals[second]
        totals[:, first] += totals[:, second]
        totals[first, first] = 0
        sizes[first] += sizes[second]
        conflict[first] |= conflict[second]
        conflict[:, first] |= conflict[:, second]
        alive[second] = False
        members[first] |= members.pop(second)
    return [members[i] for i in sorted(members)]


class MaskClustering(StageAlgorithm):
    name, stage = "lift.maskclustering", "lift"
    reads, writes = ["segment", "align", "recon"], ["instances"]
    manifest_type = LiftManifest

    def run(self, workspace, params):
        nodes, frames = [], {}
        voxel = float(params.get("voxel_size_m", 0.02))
        if voxel <= 0:
            raise ValueError("voxel_size_m must be positive")
        for masks_file in sorted(workspace.path("segment/masks").glob("*.npz")):
            frame_id = masks_file.stem
            with np.load(
                workspace.path(f"align/frames/{frame_id}.npz"), allow_pickle=False
            ) as data:
                frames[frame_id] = dict(data)
            frame = frames[frame_id]
            with np.load(masks_file, allow_pickle=False) as data:
                for index, (mask, label, score) in enumerate(
                    zip(data["masks"], data["labels"], data["scores"], strict=True)
                ):
                    mask = np.asarray(mask, dtype=bool)
                    points = unproject(frame["depth"], frame["K"], frame["pose"], mask)
                    if len(points) < int(params.get("min_points", 8)):
                        continue
                    _, unique = np.unique(
                        np.floor(points / voxel).astype(np.int64), axis=0, return_index=True
                    )
                    nodes.append(
                        {
                            "frame": frame_id,
                            "index": index,
                            "mask": mask,
                            "label": str(label),
                            "score": float(score),
                            "points": points[unique],
                        }
                    )
        affinity = np.zeros((len(nodes), len(nodes)))
        for i, a in enumerate(nodes):
            self.progress(i, len(nodes), "mask")
            for j in range(i + 1, len(nodes)):
                b = nodes[j]
                if a["frame"] == b["frame"]:
                    continue
                forward = support(
                    a["points"],
                    frames[b["frame"]],
                    b["mask"],
                    float(params.get("depth_tolerance_m", 0.05)),
                )
                reverse = support(
                    b["points"],
                    frames[a["frame"]],
                    a["mask"],
                    float(params.get("depth_tolerance_m", 0.05)),
                )
                affinity[i, j] = affinity[j, i] = min(forward, reverse)
        self.progress(len(nodes), len(nodes), "mask")
        groups = _agglomerate(
            affinity,
            [node["frame"] for node in nodes],
            float(params.get("consensus_threshold", 0.5)),
        )
        instances = []
        for group in groups:
            members = [nodes[i] for i in sorted(group)]
            num_views = len({node["frame"] for node in members})
            if num_views < int(params.get("min_views", 2)):
                continue
            votes = defaultdict(float)
            for member in members:
                votes[member["label"]] += member["score"] * int(member["mask"].sum())
            label = max(votes, key=votes.get)
            identity = ";".join(f"{node['frame']}:{node['index']}" for node in members)
            instance_id = "obj-" + hashlib.sha256(identity.encode()).hexdigest()[:16]
            points = np.concatenate([member["points"] for member in members])
            _, unique = np.unique(
                np.floor(points / voxel).astype(np.int64), axis=0, return_index=True
            )
            np.save(workspace.dir("instances/points") / f"{instance_id}.npy", points[unique])
            best_views = []
            ranked = sorted(
                members, key=lambda node: node["score"] * node["mask"].sum(), reverse=True
            )[: int(params.get("num_best_views", 3))]
            for index, member in enumerate(ranked):
                y, x = np.nonzero(member["mask"])
                with Image.open(workspace.path(f"recon/rgb/{member['frame']}.png")) as image:
                    pad = max(2, int(0.1 * max(x.max() - x.min(), y.max() - y.min())))
                    bbox = [
                        max(0, int(x.min()) - pad),
                        max(0, int(y.min()) - pad),
                        min(image.width, int(x.max()) + pad + 1),
                        min(image.height, int(y.max()) + pad + 1),
                    ]
                    image.crop(bbox).save(
                        workspace.dir("instances/crops") / f"{instance_id}_{index}.jpg"
                    )
                best_views.append(
                    {"frame_id": member["frame"], "bbox": bbox, "score": member["score"]}
                )
            instances.append(
                {
                    "id": instance_id,
                    "label": label,
                    "score": max(member["score"] for member in members),
                    "num_views": num_views,
                    "points_file": f"instances/points/{instance_id}.npy",
                    "best_views": best_views,
                }
            )
        workspace.dir("instances").joinpath("instances.json").write_text(
            json.dumps(instances, indent=2), encoding="utf-8"
        )
        return LiftManifest(num_instances=len(instances), instances_file="instances/instances.json")
