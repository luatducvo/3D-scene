"""Mask graph clustering using geometric cross-view visibility consensus."""

import hashlib
import json
from collections import defaultdict

import numpy as np
from PIL import Image
from scene_core.contracts import LiftManifest
from scene_core.errors import SceneError
from scene_core.ports import StageAlgorithm

from .arrays import array_module, to_numpy


def unproject(depth, intrinsics, pose, mask):
    y, x = np.nonzero(mask & np.isfinite(depth) & (depth > 0))
    z = depth[y, x]
    rays = np.column_stack([x, y, np.ones(len(x))]) @ np.linalg.inv(intrinsics).T
    return (rays * z[:, None]) @ pose[:3, :3].T + pose[:3, 3]


def view_support(nodes, frames, tolerance, xp=np, progress=None):
    """support[a, b]: of node a's points that project into node b's Frame and agree with its depth
    within `tolerance`, the share that falls inside b's mask; 0 when none agree, and for two nodes
    of one Frame.

    Each Frame projects every other Frame's points once, and per-node sums replace a projection per
    node pair, so the work grows with Frames times points rather than with node pairs.
    """
    count = len(nodes)
    result = np.zeros((count, count))
    if not count:
        return result
    order = {frame_id: index for index, frame_id in enumerate(frames)}
    node_frame = np.array([order[node["frame"]] for node in nodes])
    sizes = [len(node["points"]) for node in nodes]
    points = xp.asarray(np.concatenate([node["points"] for node in nodes]))
    owner = xp.asarray(np.repeat(np.arange(count), sizes))
    owner_frame = xp.asarray(node_frame)[owner]
    for done, (frame_id, frame) in enumerate(frames.items()):
        if progress:
            progress(done, len(frames))
        members = np.flatnonzero(node_frame == order[frame_id])
        if not len(members):
            continue
        pose, depth = xp.asarray(frame["pose"]), xp.asarray(frame["depth"])
        camera = (points - pose[:3, 3]) @ pose[:3, :3]
        projected = camera @ xp.asarray(frame["K"]).T
        front = (camera[:, 2] > 1e-6) & (owner_frame != order[frame_id])
        z = xp.where(front, projected[:, 2], 1.0)
        x, y = xp.rint(projected[:, 0] / z), xp.rint(projected[:, 1] / z)
        h, w = depth.shape
        rows = xp.flatnonzero(front & (x >= 0) & (x < w) & (y >= 0) & (y < h))
        x, y = x[rows].astype(xp.int64), y[rows].astype(xp.int64)
        observed = depth[y, x]
        agree = (
            xp.isfinite(observed)
            & (observed > 0)
            & (xp.abs(observed - camera[rows, 2]) <= tolerance)
        )
        rows, x, y = rows[agree], x[agree], y[agree]
        agreeing = xp.bincount(owner[rows], minlength=count)
        inside = xp.stack(
            [
                xp.bincount(
                    owner[rows],
                    weights=xp.asarray(nodes[m]["mask"])[y, x].astype(float),
                    minlength=count,
                )
                for m in members
            ],
            axis=1,
        )
        shares = xp.where(agreeing[:, None] > 0, inside / xp.maximum(agreeing, 1)[:, None], 0.0)
        result[:, members] = to_numpy(shares)
    if progress:
        progress(len(frames), len(frames))
    return result


def _agglomerate(affinity, node_frames, threshold, xp=np):
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
    conflict = xp.asarray(seen @ seen.T > 0)
    totals = xp.asarray(affinity, dtype=float).copy()
    sizes = xp.ones(count)
    alive = xp.ones(count, bool)
    members = {i: {i} for i in range(count)}
    upper = xp.triu(xp.ones((count, count), bool), 1)
    while True:
        allowed = upper & alive[:, None] & alive[None, :] & ~conflict
        mean = xp.where(allowed, totals / xp.outer(sizes, sizes), -xp.inf)
        flat = int(xp.argmax(mean))
        if not float(mean.ravel()[flat]) > threshold:
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


def merge_same_label(groups, labels, voxels, threshold):
    """Merge groups with the same label whose voxel sets overlap by more than `threshold` of the
    smaller set, highest overlap first, until no such pair remains; return the merged groups.

    `voxels[i]` holds group i's integer voxel coordinates, shape (N, 3). Groups with different
    labels never merge, so a door handle inside a wardrobe stays its own group. A merged group
    takes the position of its first part, and ties go to the lowest (first, second) pair.
    """
    groups = [set(group) for group in groups]
    cells = [set(map(tuple, np.asarray(keys).tolist())) for keys in voxels]
    bounds = [
        (np.min(keys, axis=0), np.max(keys, axis=0)) if len(keys) else None for keys in voxels
    ]
    alive = [True] * len(groups)
    by_label = defaultdict(list)
    for index, label in enumerate(labels):
        by_label[label].append(index)

    def overlap(i, j):
        if bounds[i] is None or bounds[j] is None:
            return 0.0
        if np.any(bounds[i][0] > bounds[j][1]) or np.any(bounds[j][0] > bounds[i][1]):
            return 0.0
        return len(cells[i] & cells[j]) / min(len(cells[i]), len(cells[j]))

    pairs = {}
    for members in by_label.values():
        for position, i in enumerate(members):
            for j in members[position + 1 :]:
                if (value := overlap(i, j)) > threshold:
                    pairs[i, j] = value
    while pairs:
        first, second = max(pairs, key=lambda pair: (pairs[pair], -pair[0], -pair[1]))
        groups[first] |= groups[second]
        cells[first] |= cells[second]
        bounds[first] = (
            np.minimum(bounds[first][0], bounds[second][0]),
            np.maximum(bounds[first][1], bounds[second][1]),
        )
        alive[second] = False
        pairs = {pair: value for pair, value in pairs.items() if not {first, second} & set(pair)}
        for other in by_label[labels[first]]:
            if other != first and alive[other] and (value := overlap(first, other)) > threshold:
                pairs[min(first, other), max(first, other)] = value
    return [group for group, keep in zip(groups, alive, strict=True) if keep]


def _vote(members):
    votes = defaultdict(float)
    for member in members:
        votes[member["label"]] += member["score"] * int(member["mask"].sum())
    return max(votes, key=votes.get)


class MaskClustering(StageAlgorithm):
    name, stage = "lift.maskclustering", "lift"
    reads, writes = ["segment", "align", "recon"], ["instances"]
    manifest_type = LiftManifest

    def run(self, workspace, params):
        nodes, frames = [], {}
        voxel = float(params.get("voxel_size_m", 0.02))
        if voxel <= 0:
            raise ValueError("voxel_size_m must be positive")
        merge_overlap = float(params.get("merge_overlap", 0.5))
        if not 0 <= merge_overlap <= 1:
            raise SceneError("INVALID_PARAMETERS", "merge_overlap must be in [0, 1]")
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
        xp = array_module(params)
        support = view_support(
            nodes,
            frames,
            float(params.get("depth_tolerance_m", 0.05)),
            xp,
            lambda done, total: self.progress(done, total, "frame"),
        )
        # Two masks agree as much as the weaker of their two directions.
        affinity = np.minimum(support, support.T)
        groups = _agglomerate(
            affinity,
            [node["frame"] for node in nodes],
            float(params.get("consensus_threshold", 0.5)),
            xp,
        )
        # Last clustering step: same-label groups that occupy the same space are one thing, such
        # as a seat seen alone in one Frame and its whole chair in another.
        groups = merge_same_label(
            groups,
            [_vote([nodes[i] for i in group]) for group in groups],
            [
                np.floor(np.concatenate([nodes[i]["points"] for i in group]) / voxel).astype(
                    np.int64
                )
                for group in groups
            ],
            merge_overlap,
        )
        instances = []
        for group in groups:
            members = [nodes[i] for i in sorted(group)]
            num_views = len({node["frame"] for node in members})
            if num_views < int(params.get("min_views", 2)):
                continue
            label = _vote(members)
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
