import pytest

from s3d_app.scene_graph import build_graph
from s3d_app.solver import ObjectNode, Program, predicate_holds, solve

TABLE = ObjectNode(1, "table", 1, (0, 0, 0.5), (2, 2, 1))
BOX = ObjectNode(2, "box", 1, (0, 0, 1.25), (0.5, 0.5, 0.5))
UNDER = ObjectNode(3, "box", 1, (0, 0, -0.5), (0.5, 0.5, 0.5))
CABINET = ObjectNode(4, "cabinet", 1, (0, 0, 1), (3, 3, 2))
INSIDE = ObjectNode(5, "box", 1, (0, 0, 1), (0.5, 0.5, 0.5))
NEIGHBOR = ObjectNode(6, "chair", 1, (1.5, 0, 0.5), (0.5, 0.5, 1))
DISTANT = ObjectNode(7, "chair", 1, (5, 0, 0.5), (0.5, 0.5, 1))


@pytest.mark.parametrize("predicate,subject,anchor", [
    ("ON", BOX, TABLE), ("UNDER", UNDER, TABLE), ("SUPPORTS", TABLE, BOX),
    ("IN", INSIDE, CABINET), ("CONTAINS", CABINET, INSIDE),
    ("NEAR", NEIGHBOR, TABLE), ("FAR", DISTANT, TABLE), ("NEXT_TO", NEIGHBOR, TABLE),
])
def test_measured_object_relations(predicate, subject, anchor):
    assert predicate_holds(predicate, subject, anchor)


def test_structure_constraints_use_graph_nodes_and_precomputed_edges():
    chair = ObjectNode(3, "chair", 1, (0.2, 0.2, 0.5), (0.4, 0.4, 1))
    structures = [{"id": "floor", "kind": "floor", "normal": [0, 0, 1], "offset": 0},
                  {"id": "wall-1", "kind": "wall", "normal": [1, 0, 0], "offset": 0},
                  {"id": "wall-2", "kind": "wall", "normal": [0, 1, 0], "offset": 0}]
    graph = build_graph("scene", [chair], structures)
    nodes = [chair, ObjectNode("floor", "floor", 1, (1, 1, 0), (2, 2, 0.03)),
             ObjectNode("wall-1", "wall", 1, (0, 1, 1), (0.03, 2, 2)),
             ObjectNode("wall-2", "wall", 1, (1, 0, 1), (2, 0.03, 2))]
    for predicate, label in (("ON_FLOOR", "floor"), ("AGAINST_WALL", "wall"), ("IN_CORNER", "wall")):
        program = Program(intent="ground", vars={"t": "chair", "a": label}, target="t",
                          constraints=[[predicate, "t", "a"]])
        result = solve(program, nodes, graph=graph)
        assert result.count == 1 and result.relaxed is None
    wall_count = solve(Program(intent="count", vars={"t": "wall"}, target="t"), nodes, graph=graph)
    assert wall_count.count == 2


def test_not_negates_color_and_geometry():
    red = ObjectNode(1, "chair", 1, (0, 0, 0), (0.5, 0.5, 1), "red")
    blue = ObjectNode(2, "chair", 1, (5, 0, 0), (0.5, 0.5, 1), "blue")
    desk = ObjectNode(3, "desk", 1, (0.5, 0, 0), (0.5, 0.5, 1))
    color = Program(intent="ground", vars={"t": "chair"}, target="t", constraints=[["NOT", "t", "COLOR:red"]])
    relation = Program(intent="ground", vars={"t": "chair", "a": "desk"}, target="t",
                       constraints=[["NOT", "t", "NEAR:a"]])
    assert solve(color, [red, blue, desk]).solutions == [{"t": 2}]
    assert solve(relation, [red, blue, desk]).solutions == [{"t": 2, "a": 3}]
