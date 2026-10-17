"""Pure Scene Graph transform and independently registered spatial predicates."""

import json
from importlib.metadata import entry_points

import numpy as np
from scene_core.contracts import GraphManifest
from scene_core.domain import Relation, SceneGraph, SceneGraphContext, SceneObject
from scene_core.errors import SceneError
from scene_core.geometry import box_surface_distance, fit_box, footprint, footprint_overlap
from scene_core.membership import ObjectMembership
from scene_core.ports import RelationRule, StageAlgorithm
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


def bounds(box):
    return box.center[2] - box.size[2] / 2, box.center[2] + box.size[2] / 2


def overlap_ratio(a, b):
    area = min(a.box.size[0] * a.box.size[1], b.box.size[0] * b.box.size[1])
    return footprint_overlap(a, b) / area if area > 0 else 0


class SpatialRule(RelationRule):
    def relation(self, a, b, value=None):
        return Relation(
            subject_id=a.id, predicate=self.predicate, object_id=b.id if b else None, value=value
        )


class On(SpatialRule):
    predicate = "on"
    reach = 0.0  # needs overlapping footprints

    def evaluate(self, a, b, context):
        if abs(bounds(a.box)[0] - bounds(b.box)[1]) <= 0.04 and overlap_ratio(a, b) >= 0.3:
            return self.relation(a, b)


class Above(SpatialRule):
    predicate = "above"
    reach = 0.0

    def evaluate(self, a, b, context):
        if (
            bounds(a.box)[0] >= bounds(b.box)[1] - 0.02
            and a.box.center[2] > b.box.center[2]
            and overlap_ratio(a, b) >= 0.2
        ):
            return self.relation(a, b)


class Under(SpatialRule):
    predicate = "under"
    reach = 0.0

    def evaluate(self, a, b, context):
        if Above().evaluate(b, a, context):
            return self.relation(a, b)


class Inside(SpatialRule):
    predicate = "inside"
    reach = 0.0

    def evaluate(self, a, b, context):
        area = a.box.size[0] * a.box.size[1]
        if (
            area > 0
            and footprint_overlap(a, b) >= area * 0.99
            and bounds(a.box)[0] >= bounds(b.box)[0] - 0.01
            and bounds(a.box)[1] <= bounds(b.box)[1] + 0.01
        ):
            return self.relation(a, b)


class NextTo(SpatialRule):
    predicate = "next_to"
    reach = 0.6  # surface distance, never shorter than the horizontal gap

    def evaluate(self, a, b, context):
        vertical_overlap = min(bounds(a.box)[1], bounds(b.box)[1]) - max(
            bounds(a.box)[0], bounds(b.box)[0]
        )
        distance = box_surface_distance(a, b)
        if 0 < distance <= 0.6 and vertical_overlap > 0 and footprint_overlap(a, b) < 0.01:
            return self.relation(a, b, distance)


class Near(SpatialRule):
    predicate = "near"
    reach = 1.0

    def evaluate(self, a, b, context):
        distance = box_surface_distance(a, b)
        if distance <= 1:
            return self.relation(a, b, distance)


class AgainstWall(SpatialRule):
    predicate = "against_wall"

    def evaluate(self, a, b, context):
        for wall in context.walls:
            normal = np.asarray(wall["normal"], float)
            length = np.linalg.norm(normal)
            if length == 0:
                continue
            vertices = np.array([[*xy, z] for xy in footprint(a) for z in bounds(a.box)])
            distance = float(np.min(abs(vertices @ normal + wall["offset"])) / length)
            if distance <= 0.15:
                return self.relation(a, None, distance)


class GeometricGraph(StageAlgorithm):
    name, stage = "graph.geometric", "graph"
    reads, writes = ["instances", "attributes", "align", "mesh"], ["graph"]
    manifest_type = GraphManifest

    def run(self, workspace, params):
        radius = float(params.get("membership_radius_m", 0.02))
        if radius <= 0:
            raise SceneError("INVALID_PARAMETERS", "membership_radius_m must be positive")
        instances = json.loads(workspace.path("instances/instances.json").read_text())
        attributes_path = workspace.path("attributes/attributes.json")
        attributes = json.loads(attributes_path.read_text()) if attributes_path.exists() else {}
        alignment_path = workspace.path("align/manifest.json")
        alignment = json.loads(alignment_path.read_text()) if alignment_path.exists() else {}
        context = SceneGraphContext.model_validate(alignment)
        wall_path = workspace.path("align/walls.json")
        if wall_path.exists():
            context.walls = json.loads(wall_path.read_text())
        objects, lifted = [], []
        for instance in instances:
            attribute = attributes.get(instance["id"], {})
            lifted.append(np.load(workspace.path(instance["points_file"]), allow_pickle=False))
            objects.append(
                SceneObject(
                    id=instance["id"],
                    label=instance["label"],
                    label_vi=attribute.get("label_vi"),
                    box=fit_box(lifted[-1]),
                    attributes=attribute.get("attributes", {}),
                    best_views=instance.get("best_views", []),
                )
            )
        configured = params.get(
            "relations", ["on", "under", "above", "inside", "next_to", "near", "against_wall"]
        )
        available = {ep.name: ep for ep in entry_points(group="scene_relations")}
        rules = [available[name].load()() for name in configured]
        # A footprint lies within its circumscribed circle, so two Objects whose circles are more than
        # a rule's reach apart cannot satisfy it; the polygon geometry then never runs for them.
        centers = np.array([obj.box.center[:2] for obj in objects]).reshape(-1, 2)
        radii = np.array([np.hypot(*obj.box.size[:2]) / 2 for obj in objects])
        gaps = (
            np.linalg.norm(centers[:, None] - centers[None], axis=-1) - radii[:, None] - radii[None]
        )
        relations = []
        for rule in rules:
            for i, a in enumerate(objects):
                # SOLID review (OCP/LSP): dispatch still knows one concrete predicate and supplies
                # a dummy second Object. Let RelationRule declare its Object/room evaluation scope
                # so another room Relation can be registered without changing this loop.
                candidates = (
                    [a]
                    if rule.predicate == "against_wall"
                    else [
                        b
                        for j, b in enumerate(objects)
                        if b.id != a.id and (rule.reach is None or gaps[i, j] <= rule.reach + 1e-6)
                    ]
                )
                for b in candidates:
                    relation = rule.evaluate(a, b, context)
                    if relation:
                        relations.append(relation)
        graph = SceneGraph(
            scene_id=workspace.scene_id,
            floor_z=context.floor_z,
            ceiling_height=context.ceiling_height,
            objects=objects,
            relations=relations,
        )
        workspace.dir("graph").joinpath("scene_graph.json").write_text(
            graph.model_dump_json(indent=2), encoding="utf-8"
        )
        write_membership(
            workspace,
            [obj.id for obj in objects],
            lambda positions: members_within(positions, lifted, radius),
        )
        return GraphManifest(num_objects=len(objects), num_relations=len(relations))


def write_membership(workspace, ids, members_of):
    """Write graph/membership.bin for the final Object `ids`. `members_of(positions)` returns, per
    id in order, the indices of `positions` that belong to it; it is asked once for the points of
    mesh/points.ply and once for the vertices of mesh/mesh.glb."""
    points = read_ply_points(workspace.path(SceneResults.ASSETS["points"]))
    vertices = read_glb_positions(workspace.path(SceneResults.ASSETS["mesh"]))
    membership = ObjectMembership.from_lists(
        ids, members_of(points), members_of(vertices), len(points), len(vertices)
    )
    path = workspace.path(SceneResults.MEMBERSHIP)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(membership.encode())
