import pytest
from pydantic import ValidationError

from s3d_app.solver import ObjectNode, Program, Viewpoint, solve


def test_program_rejects_undeclared_variable() -> None:
    with pytest.raises(ValidationError, match="Undeclared anchor"):
        Program(intent="ground", vars={"t": "chair"}, constraints=[["NEAR", "t", "a"]],
                target="t")


def test_solver_finds_and_counts_objects_and_relaxes_weak_relation() -> None:
    nodes = [
        ObjectNode(1, "chair", 0.9, (0, 0, 0.5), (0.5, 0.5, 1)),
        ObjectNode(2, "chair", 0.8, (4, 0, 0.5), (0.5, 0.5, 1)),
        ObjectNode(3, "desk", 0.95, (0.8, 0, 0.5), (0.8, 0.8, 1)),
    ]
    near = Program(intent="ground", vars={"t": "chair", "d": "desk"},
                   constraints=[["NEAR", "t", "d"]], target="t")
    assert solve(near, nodes).solutions[0]["t"] == 1
    count = Program(intent="count", vars={"t": "chair"}, target="t")
    assert solve(count, nodes).count == 2
    contradictory = Program(intent="ground", vars={"t": "chair", "d": "desk"},
                            constraints=[["FAR", "t", "d"], ["NEAR", "t", "d"]],
                            target="t")
    result = solve(contradictory, nodes)
    assert "NEAR" in result.relaxed
    assert result.solutions[0]["t"] == 2


def test_viewpoint_flips_left_and_right() -> None:
    nodes = [
        ObjectNode(1, "chair", 0.9, (-1, 0, 0.5), (0.5, 0.5, 1)),
        ObjectNode(2, "chair", 0.9, (1, 0, 0.5), (0.5, 0.5, 1)),
        ObjectNode(3, "desk", 0.9, (0, 0, 0.5), (0.5, 0.5, 1)),
    ]
    program = Program(intent="ground", vars={"t": "chair", "d": "desk"},
                      constraints=[["LEFT", "t", "d"]], target="t")
    north = solve(program, nodes, Viewpoint((0, -4, 1), (0, 1, 0)))
    south = solve(program, nodes, Viewpoint((0, 4, 1), (0, -1, 0)))
    assert north.solutions[0]["t"] == 1
    assert south.solutions[0]["t"] == 2


def test_camera_inside_anchor_uses_room_center() -> None:
    nodes = [
        ObjectNode(1, "chair", 0.9, (-1, 0, 0.5), (0.5, 0.5, 1)),
        ObjectNode(2, "desk", 0.9, (0, 0, 0.5), (0.5, 0.5, 1)),
        ObjectNode(3, "cabinet", 0.9, (0, -8, 0.5), (0.5, 0.5, 1)),
    ]
    program = Program(intent="ground", vars={"t": "chair", "d": "desk"},
                      constraints=[["LEFT", "t", "d"]], target="t")
    inside = solve(program, nodes, Viewpoint((0, 0, 0.5), (0, -1, 0)))
    fallback = solve(program, nodes, None)
    assert inside.solutions == fallback.solutions


def test_program_viewpoint_overrides_viewer_camera() -> None:
    nodes = [ObjectNode(1, "chair", 0.9, (-1, 0, 0.5), (0.5, 0.5, 1)),
             ObjectNode(2, "chair", 0.9, (1, 0, 0.5), (0.5, 0.5, 1)),
             ObjectNode(3, "desk", 0.9, (0, 0, 0.5), (0.5, 0.5, 1))]
    program = Program(intent="ground", vars={"t": "chair", "a": "desk"}, target="t",
                      constraints=[["LEFT", "t", "a"]], viewpoint=(0, 4, 1, 0, -1, 0))
    result = solve(program, nodes, Viewpoint((0, -4, 1), (0, 1, 0)))
    assert result.solutions[0]["t"] == 2


def test_primary_label_precedes_another_objects_alternative():
    bed = ObjectNode(1, "bed", 0.9, (0, 0, 0), (2, 1, 1))
    bag = ObjectNode(2, "backpack", 0.8, (1, 0, 0), (0.5, 0.5, 0.5), alt_labels=("bed",))
    program = Program(intent="ground", vars={"t": "bed"}, target="t")
    assert solve(program, [bed, bag]).solutions == [{"t": 1}]
    assert solve(program, [bag]).solutions == [{"t": 2}]


def test_from_door_viewpoint_is_resolved_from_measured_coordinates():
    from s3d_app.ask import apply_explicit_viewpoint

    program = Program(intent="ground", vars={"t": "chair", "a": "bed"}, target="t",
                      constraints=[["LEFT", "t", "a"]])
    records = [{"label": "door", "center": [0, -4, 1], "confidence": 1},
               {"label": "bed", "center": [0, 0, 0.5], "confidence": 1}]
    apply_explicit_viewpoint(program, "the chair left of the bed from the door", records)
    assert program.viewpoint == (0, -4, 1, 0, 4, -0.5)
