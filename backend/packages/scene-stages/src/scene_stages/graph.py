"""Pure Scene Graph transform and independently registered spatial predicates."""

import json
from importlib.metadata import entry_points

import numpy as np
from scene_core.contracts import GraphManifest
from scene_core.domain import Relation, SceneGraph, SceneGraphContext, SceneObject
from scene_core.geometry import box_surface_distance, fit_box, footprint, footprint_overlap
from scene_core.ports import RelationRule, StageAlgorithm


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

    def evaluate(self, a, b, context):
        if abs(bounds(a.box)[0] - bounds(b.box)[1]) <= 0.04 and overlap_ratio(a, b) >= 0.3:
            return self.relation(a, b)


class Above(SpatialRule):
    predicate = "above"

    def evaluate(self, a, b, context):
        if (
            bounds(a.box)[0] >= bounds(b.box)[1] - 0.02
            and a.box.center[2] > b.box.center[2]
            and overlap_ratio(a, b) >= 0.2
        ):
            return self.relation(a, b)


class Under(SpatialRule):
    predicate = "under"

    def evaluate(self, a, b, context):
        if Above().evaluate(b, a, context):
            return self.relation(a, b)


class Inside(SpatialRule):
    predicate = "inside"

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

    def evaluate(self, a, b, context):
        vertical_overlap = min(bounds(a.box)[1], bounds(b.box)[1]) - max(
            bounds(a.box)[0], bounds(b.box)[0]
        )
        distance = box_surface_distance(a, b)
        if 0 < distance <= 0.6 and vertical_overlap > 0 and footprint_overlap(a, b) < 0.01:
            return self.relation(a, b, distance)


class Near(SpatialRule):
    predicate = "near"

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
    reads, writes = ["instances", "attributes", "align"], ["graph"]
    manifest_type = GraphManifest

    def run(self, workspace, params):
        instances = json.loads(workspace.path("instances/instances.json").read_text())
        attributes_path = workspace.path("attributes/attributes.json")
        attributes = json.loads(attributes_path.read_text()) if attributes_path.exists() else {}
        alignment_path = workspace.path("align/manifest.json")
        alignment = json.loads(alignment_path.read_text()) if alignment_path.exists() else {}
        context = SceneGraphContext.model_validate(alignment)
        wall_path = workspace.path("align/walls.json")
        if wall_path.exists():
            context.walls = json.loads(wall_path.read_text())
        objects = []
        for instance in instances:
            attribute = attributes.get(instance["id"], {})
            objects.append(
                SceneObject(
                    id=instance["id"],
                    label=instance["label"],
                    label_vi=attribute.get("label_vi"),
                    box=fit_box(
                        np.load(workspace.path(instance["points_file"]), allow_pickle=False)
                    ),
                    attributes=attribute.get("attributes", {}),
                    best_views=instance.get("best_views", []),
                )
            )
        configured = params.get(
            "relations", ["on", "under", "above", "inside", "next_to", "near", "against_wall"]
        )
        available = {ep.name: ep for ep in entry_points(group="scene_relations")}
        rules = [available[name].load()() for name in configured]
        relations = []
        for rule in rules:
            for a in objects:
                # SOLID review (OCP/LSP): dispatch still knows one concrete predicate and supplies
                # a dummy second Object. Let RelationRule declare its Object/room evaluation scope
                # so another room Relation can be registered without changing this loop.
                candidates = (
                    [a]
                    if rule.predicate == "against_wall"
                    else [b for b in objects if b.id != a.id]
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
        return GraphManifest(num_objects=len(objects), num_relations=len(relations))
