"""Three-level Room → Structure → Object graph from measured geometry."""

from dataclasses import asdict, dataclass

from s3d_app.solver import ObjectNode, predicate_holds


@dataclass(frozen=True)
class Relation:
    predicate: str
    subject: str
    anchor: str
    score: float


def _plane_gap(node: ObjectNode, structure: dict) -> float:
    normal = structure["normal"]
    offset = structure["offset"]
    center_gap = abs(sum(normal[i] * node.center[i] for i in range(3)) - offset)
    radius = sum(abs(normal[i]) * node.size[i] / 2 for i in range(3))
    return max(0.0, center_gap - radius)


def build_graph(scene_id: str, objects: list[ObjectNode], structures: list[dict],
                *, contact_m: float = 0.25, near_m: float = 1.0) -> dict:
    nodes = [{"id": "room", "level": "room", "scene_id": scene_id}]
    nodes += [{"id": item["id"], "level": "structure", **item} for item in structures]
    nodes += [{"id": str(item.id), "level": "object", **asdict(item)} for item in objects]
    relations: list[Relation] = []
    for structure in structures:
        relations.append(Relation("IN", structure["id"], "room", 1.0))
    for node in objects:
        relations.append(Relation("IN", str(node.id), "room", 1.0))
        nearby_walls = []
        for structure in structures:
            gap = _plane_gap(node, structure)
            if gap <= near_m:
                relations.append(Relation("NEAR", str(node.id), structure["id"],
                                          round(max(0.01, 1 - gap / near_m), 3)))
            elif gap >= near_m * 2:
                relations.append(Relation("FAR", str(node.id), structure["id"], 1.0))
            if structure["kind"] == "floor" and gap <= contact_m:
                relations.append(Relation("ON_FLOOR", str(node.id), structure["id"],
                                          round(1 - gap / max(contact_m, 1e-6), 3)))
            elif structure["kind"] == "wall" and gap <= contact_m:
                nearby_walls.append(structure["id"])
                relations.append(Relation("AGAINST_WALL", str(node.id), structure["id"],
                                          round(1 - gap / max(contact_m, 1e-6), 3)))
        if len(nearby_walls) >= 2:
            relations.append(Relation("IN_CORNER", str(node.id), ",".join(nearby_walls[:2]), 1.0))
    predicates = ("ON", "UNDER", "SUPPORTS", "IN", "CONTAINS", "NEAR", "FAR", "NEXT_TO")
    for subject in objects:
        for anchor in objects:
            if subject.id == anchor.id:
                continue
            for predicate in predicates:
                if predicate_holds(predicate, subject, anchor,
                                   contact_m=contact_m, near_m=near_m):
                    score = min(subject.confidence, anchor.confidence)
                    relations.append(Relation(predicate, str(subject.id), str(anchor.id),
                                              round(score, 3)))
    return {"nodes": nodes, "relations": [asdict(item) for item in relations],
            "thresholds": {"contact_m": contact_m, "near_m": near_m}}


def serialize_node(node: ObjectNode, relations: list[Relation]) -> str:
    related = [f"{item.predicate.lower()}: {item.anchor}"
               for item in relations if item.subject == str(node.id)][:4]
    center = ",".join(f"{value:.2f}" for value in node.center)
    size = ",".join(f"{value:.2f}" for value in node.size)
    suffix = "; ".join(related) or "none"
    return f"[{node.id}] {node.label} ({node.confidence:.2f}) | c=({center}) s=({size}) | {suffix}"
