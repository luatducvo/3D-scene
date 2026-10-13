import json
import numpy as np
import pytest
from scene_core.contracts import SceneWorkspace
from scene_core.domain import SceneObject, OrientedBox, SceneGraphContext
from scene_stages.graph import GeometricGraph, On, Under, Above, Inside, NextTo, Near, AgainstWall


def object_box(name, center, size):
    return SceneObject(id=name, label=name, box=OrientedBox(center=center, size=size))


def test_relation_rules_respect_contact_and_distance_thresholds():
    cup = object_box("cup", (0, 0, 1.1), (.2, .2, .2))
    table = object_box("table", (0, 0, .5), (2, 2, 1))
    context = SceneGraphContext(walls=[{"normal": [1, 0, 0], "offset": -1.1}])
    assert On().evaluate(cup, table, context)
    assert Under().evaluate(table, cup, context)
    assert Above().evaluate(cup, table, context)
    assert not On().evaluate(table, cup, context)
    assert Inside().evaluate(object_box("inner", (0, 0, .5), (.2, .2, .2)), table, context)
    assert Near().evaluate(cup, table, context)
    assert AgainstWall().evaluate(table, table, context)
    assert NextTo().evaluate(table, object_box("chair", (2, 0, .5), (1, 1, 1)), context)
    assert not Near().evaluate(cup, object_box("far", (20, 0, 0), (1, 1, 1)), context)


def test_graph_keeps_instance_id_and_writes_only_graph(tmp_path):
    workspace = SceneWorkspace(tmp_path, "fixture")
    workspace.dir("instances/points")
    np.save(workspace.path("instances/points/cup.npy"), np.array([[x, y, z] for x in (-.1, .1) for y in (-.1, .1) for z in (1, 1.2)]))
    workspace.path("instances/instances.json").write_text(json.dumps([{"id": "cup", "label": "cup", "score": .9, "num_views": 2, "points_file": "instances/points/cup.npy", "best_views": []}]))
    before = workspace.path("instances/instances.json").read_bytes()
    result = GeometricGraph().run(workspace, {"relations": []})
    graph = json.loads(workspace.path("graph/scene_graph.json").read_text())
    assert result.num_objects == 1
    assert graph["objects"][0]["id"] == "cup"
    assert graph["objects"][0]["box"]["center"][2] == pytest.approx(1.1)
    assert workspace.path("instances/instances.json").read_bytes() == before
