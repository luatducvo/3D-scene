import json

import numpy as np
import pytest
from scene_core.contracts import SceneWorkspace
from scene_core.domain import OrientedBox, SceneGraphContext, SceneObject
from scene_stages.graph import Above, AgainstWall, GeometricGraph, Inside, Near, NextTo, On, Under


def object_box(name, center, size):
    return SceneObject(id=name, label=name, box=OrientedBox(center=center, size=size))


def test_relation_rules_respect_contact_and_distance_thresholds():
    cup = object_box("cup", (0, 0, 1.1), (0.2, 0.2, 0.2))
    table = object_box("table", (0, 0, 0.5), (2, 2, 1))
    context = SceneGraphContext(walls=[{"normal": [1, 0, 0], "offset": -1.1}])
    assert On().evaluate(cup, table, context)
    assert Under().evaluate(table, cup, context)
    assert Above().evaluate(cup, table, context)
    assert not On().evaluate(table, cup, context)
    assert Inside().evaluate(object_box("inner", (0, 0, 0.5), (0.2, 0.2, 0.2)), table, context)
    assert Near().evaluate(cup, table, context)
    assert AgainstWall().evaluate(table, table, context)
    assert NextTo().evaluate(table, object_box("chair", (2, 0, 0.5), (1, 1, 1)), context)
    assert not Near().evaluate(cup, object_box("far", (20, 0, 0), (1, 1, 1)), context)


def test_no_rule_holds_for_a_pair_beyond_its_reach():
    """The graph skips such pairs, so this is what keeps the skip from losing Relations."""
    rng = np.random.default_rng(5)
    context = SceneGraphContext()
    checked = 0
    for _ in range(3000):
        a, b = (
            SceneObject(
                id=name,
                label=name,
                box=OrientedBox(
                    center=tuple(rng.uniform([-2, -2, 0], [2, 2, 2])),
                    size=tuple(rng.uniform(0.05, 1.5, 3)),
                    yaw=float(rng.uniform(0, np.pi)),
                ),
            )
            for name in ("a", "b")
        )
        gap = (
            np.linalg.norm(np.subtract(a.box.center[:2], b.box.center[:2]))
            - np.hypot(*a.box.size[:2]) / 2
            - np.hypot(*b.box.size[:2]) / 2
        )
        for rule in (On(), Above(), Under(), Inside(), NextTo(), Near()):
            if gap > rule.reach:
                checked += 1
                assert rule.evaluate(a, b, context) is None, (rule.predicate, gap)
    assert checked > 1000


def test_graph_keeps_instance_id_and_writes_only_graph(tmp_path):
    workspace = SceneWorkspace(tmp_path, "fixture")
    workspace.dir("instances/points")
    np.save(
        workspace.path("instances/points/cup.npy"),
        np.array([[x, y, z] for x in (-0.1, 0.1) for y in (-0.1, 0.1) for z in (1, 1.2)]),
    )
    workspace.path("instances/instances.json").write_text(
        json.dumps(
            [
                {
                    "id": "cup",
                    "label": "cup",
                    "score": 0.9,
                    "num_views": 2,
                    "points_file": "instances/points/cup.npy",
                    "best_views": [],
                }
            ]
        )
    )
    before = workspace.path("instances/instances.json").read_bytes()
    result = GeometricGraph().run(workspace, {"relations": []})
    graph = json.loads(workspace.path("graph/scene_graph.json").read_text())
    assert result.num_objects == 1
    assert graph["objects"][0]["id"] == "cup"
    assert graph["objects"][0]["box"]["center"][2] == pytest.approx(1.1)
    assert workspace.path("instances/instances.json").read_bytes() == before
