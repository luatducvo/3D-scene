"""Objects with oriented boxes from Instances, and their Object Membership."""

import json

import numpy as np
from scene_core.contracts import ObjectsManifest
from scene_core.domain import OBJECT_LIST, SceneObject
from scene_core.errors import SceneError
from scene_core.geometry import fit_box
from scene_core.membership import ObjectMembership
from scene_core.ports import StageAlgorithm
from scene_core.results import SceneResults

from .mesh import read_glb_positions, read_ply_points


def members_within(targets, groups, radius):
    """For each group of points, the sorted indices of `targets` within `radius` of any of them.

    Hashes the group points on a grid of `radius` cells, so every match of a target lies in its own
    cell or one of the 26 around it; distances are then checked exactly. A target may match several
    groups or none."""
    if radius <= 0:
        raise SceneError(
            "INVALID_PARAMETERS", f"The membership radius must be positive, got {radius}"
        )
    targets = np.asarray(targets, dtype=np.float64).reshape(-1, 3)
    groups = [np.asarray(g, dtype=np.float64).reshape(-1, 3) for g in groups]
    empty = [np.zeros(0, np.int64) for _ in groups]
    sizes = [len(g) for g in groups]
    if not len(targets) or not sum(sizes):
        return empty
    points = np.concatenate(groups)
    owner = np.repeat(np.arange(len(groups)), sizes)
    # Only targets near the groups' bounds can match.
    near = np.flatnonzero(
        np.all(
            (targets >= points.min(axis=0) - radius) & (targets <= points.max(axis=0) + radius),
            axis=1,
        )
    )
    if not len(near):
        return empty
    origin = points.min(axis=0) - 2 * radius
    point_cells = np.floor((points - origin) / radius).astype(np.int64)
    target_cells = np.floor((targets[near] - origin) / radius).astype(np.int64)
    extent = np.maximum(point_cells.max(axis=0), target_cells.max(axis=0)) + 2

    def key(cells):
        return (cells[..., 0] * extent[1] + cells[..., 1]) * extent[2] + cells[..., 2]

    order = np.argsort(key(point_cells), kind="stable")
    sorted_keys = key(point_cells)[order]
    # The key is linear in the cell, so a neighbor offset shifts every key by one constant and the
    # queries stay sorted, which keeps searchsorted fast.
    target_keys = key(target_cells)
    by_key = np.argsort(target_keys, kind="stable")
    near, target_keys = near[by_key], target_keys[by_key]
    pairs = []
    for offset in np.array(np.meshgrid(*[(-1, 0, 1)] * 3, indexing="ij")).reshape(3, -1).T:
        keys = target_keys + key(offset)
        low = np.searchsorted(sorted_keys, keys, "left")
        counts = np.searchsorted(sorted_keys, keys, "right") - low
        if not counts.any():
            continue
        target = np.repeat(near, counts)
        first = np.repeat(low - (np.cumsum(counts) - counts), counts)
        candidate = order[first + np.arange(len(target))]
        close = np.sum((targets[target] - points[candidate]) ** 2, axis=1) <= radius * radius
        pairs.append(owner[candidate[close]] * len(targets) + target[close])
    if not pairs:
        return empty
    pairs = np.unique(np.concatenate(pairs))
    groups_of, members = np.divmod(pairs, len(targets))
    starts = np.searchsorted(groups_of, np.arange(len(groups) + 1))
    return [members[starts[i] : starts[i + 1]] for i in range(len(groups))]


class GeometricObjects(StageAlgorithm):
    name, stage = "objects.geometric", "objects"
    reads, writes = ["instances", "mesh"], ["objects"]
    manifest_type = ObjectsManifest

    def run(self, workspace, params):
        radius = float(params.get("membership_radius_m", 0.02))
        if radius <= 0:
            raise SceneError("INVALID_PARAMETERS", "membership_radius_m must be positive")
        instances = json.loads(workspace.path("instances/instances.json").read_text())
        objects, lifted = [], []
        for instance in instances:
            lifted.append(np.load(workspace.path(instance["points_file"]), allow_pickle=False))
            objects.append(
                SceneObject(
                    id=instance["id"],
                    label=instance["label"],
                    box=fit_box(lifted[-1]),
                    best_views=instance.get("best_views", []),
                )
            )
        write_objects(workspace, objects)
        write_membership(
            workspace,
            [obj.id for obj in objects],
            lambda positions: members_within(positions, lifted, radius),
        )
        return ObjectsManifest(num_objects=len(objects))


def write_objects(workspace, objects):
    """Write the Objects file of a Publication, in the order their membership lists them."""
    path = workspace.path(SceneResults.OBJECTS)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(OBJECT_LIST.dump_json(objects, indent=2))


def write_membership(workspace, ids, members_of):
    """Write the Object Membership file for the final Object `ids`. `members_of(positions)` returns,
    per id in order, the indices of `positions` that belong to it; it is asked once for the points
    of the point cloud and once for the vertices of the mesh."""
    points = read_ply_points(workspace.path(SceneResults.ASSETS["points"]))
    vertices = read_glb_positions(workspace.path(SceneResults.ASSETS["mesh"]))
    membership = ObjectMembership.from_lists(
        ids, members_of(points), members_of(vertices), len(points), len(vertices)
    )
    path = workspace.path(SceneResults.MEMBERSHIP)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(membership.encode())
