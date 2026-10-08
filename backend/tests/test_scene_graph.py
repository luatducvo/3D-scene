from s3d_app.scene_graph import Relation, build_graph, serialize_node
from s3d_app.solver import ObjectNode


def test_graph_contains_room_structure_and_geometric_relations() -> None:
    floor = {"id": "floor", "kind": "floor", "normal": [0, 0, 1], "offset": 0}
    wall = {"id": "wall-1", "kind": "wall", "normal": [1, 0, 0], "offset": 0}
    table = ObjectNode(1, "table", 0.9, (1, 0, 0.5), (1, 1, 1))
    box = ObjectNode(2, "box", 0.8, (1, 0, 1.25), (0.3, 0.3, 0.5))
    chair = ObjectNode(3, "chair", 0.7, (0.2, 0, 0.5), (0.4, 0.4, 1))
    graph = build_graph("scene0000_00", [table, box, chair], [floor, wall])
    assert sum(node["level"] == "room" for node in graph["nodes"]) == 1
    relationships = {(item["predicate"], item["subject"], item["anchor"])
                     for item in graph["relations"]}
    assert ("ON", "2", "1") in relationships
    assert ("ON_FLOOR", "1", "floor") in relationships
    assert ("AGAINST_WALL", "3", "wall-1") in relationships


def test_short_node_serialization() -> None:
    node = ObjectNode(42, "office chair", 0.81, (1.21, 0.43, 0.52), (0.61, 0.60, 1.02))
    line = serialize_node(node, [Relation("NEAR", "42", "7", 0.8)])
    assert line == "[42] office chair (0.81) | c=(1.21,0.43,0.52) s=(0.61,0.60,1.02) | near: 7"
