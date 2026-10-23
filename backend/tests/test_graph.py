import json

import numpy as np
import pytest
from scene_core.contracts import SceneWorkspace
from scene_core.domain import OrientedBox, SceneGraphContext, SceneObject
from scene_core.errors import SceneError
from scene_core.membership import ObjectMembership
from scene_core.results import SceneResults
from scene_stages.graph import (
    Above,
    AgainstWall,
    GeometricGraph,
    Inside,
    Near,
    NextTo,
    On,
    Under,
    members_within,
)
from scene_stages.mesh import (
    GLTF_FLOAT,
    pack_glb,
    read_glb_positions,
    read_ply_points,
    write_ply,
)


def write_glb(path, vertices):
    """A binary glTF with one primitive holding only POSITION, as a mesh Algorithm writes it."""
    binary = np.asarray(vertices, dtype="<f4").tobytes()
    doc = {
        "asset": {"version": "2.0"},
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}],
        "buffers": [{"byteLength": len(binary)}],
        "bufferViews": [{"buffer": 0, "byteLength": len(binary)}],
        "accessors": [
            {"bufferView": 0, "componentType": GLTF_FLOAT, "count": len(vertices), "type": "VEC3"}
        ],
    }
    path.write_bytes(pack_glb(doc, binary))


def write_mesh(workspace, points, vertices):
    workspace.dir("mesh")
    write_ply(workspace.path("mesh/points.ply"), points, np.zeros((len(points), 3), np.uint8))
    write_glb(workspace.path("mesh/mesh.glb"), vertices)


def write_instances(workspace, lifted):
    workspace.dir("instances/points")
    instances = []
    for name, points in lifted.items():
        np.save(workspace.path(f"instances/points/{name}.npy"), np.asarray(points, float))
        instances.append(
            {
                "id": name,
                "label": name,
                "score": 0.9,
                "num_views": 2,
                "points_file": f"instances/points/{name}.npy",
                "best_views": [],
            }
        )
    workspace.path("instances/instances.json").write_text(json.dumps(instances))
    write_graph_inputs(workspace)


def write_graph_inputs(workspace):
    """The align outputs graph reads besides instances and mesh, all empty."""
    workspace.dir("align").joinpath("manifest.json").write_text(
        json.dumps({"world_to_aligned": np.eye(4).tolist(), "floor_z": 0})
    )
    workspace.path("align/walls.json").write_text("[]")


def grid(low, high, step=0.02):
    axes = [np.arange(a, b + step / 2, step) for a, b in zip(low, high, strict=True)]
    return np.stack(np.meshgrid(*axes, indexing="ij"), axis=-1).reshape(-1, 3)


def test_membership_lists_a_point_under_every_object_within_the_radius(tmp_path):
    """A handle inside a wardrobe: its points belong to both; far points belong to neither."""
    workspace = SceneWorkspace(tmp_path, "fixture")
    write_instances(
        workspace,
        {
            "wardrobe": grid((0, 0, 0), (1, 0.6, 2)),
            "handle": grid((0.9, 0.58, 1), (0.96, 0.62, 1.1)),
        },
    )
    shared = [0.92, 0.6, 1.05]  # on both Objects' lift points
    wardrobe_only = [0.2, 0.3, 0.5]
    edge = [1.0 + 0.019, 0.3, 0.5]  # 1.9 cm beyond the wardrobe's outermost lift point
    beyond = [1.0 + 0.021, 0.3, 0.5]  # 2.1 cm beyond it
    far = [3, 3, 1]
    write_mesh(
        workspace,
        np.array([shared, wardrobe_only, edge, beyond, far]),
        np.array([far, shared, beyond]),
    )
    GeometricGraph().run(workspace, {"relations": [], "membership_radius_m": 0.02})
    membership = ObjectMembership.decode(workspace.path(SceneResults.MEMBERSHIP).read_bytes())
    assert membership.ids == ["wardrobe", "handle"]
    assert (membership.point_count, membership.vertex_count) == (5, 3)
    assert membership.points(0).tolist() == [0, 1, 2]
    assert membership.points(1).tolist() == [0]
    assert membership.vertices(0).tolist() == [1]
    assert membership.vertices(1).tolist() == [1]
    np.testing.assert_allclose(
        read_glb_positions(workspace.path("mesh/mesh.glb")), [far, shared, beyond], rtol=1e-6
    )


def test_members_within_matches_a_brute_force_search():
    rng = np.random.default_rng(3)
    targets = rng.uniform(0, 1, (3000, 3))
    groups = [rng.uniform(0, 1, (n, 3)) for n in (0, 1, 40, 200)]
    found = members_within(targets, groups, 0.05)
    for group, members in zip(groups, found, strict=True):
        if not len(group):
            assert not len(members)
            continue
        distance = np.linalg.norm(targets[:, None] - group[None], axis=-1).min(axis=1)
        assert members.tolist() == np.flatnonzero(distance <= 0.05).tolist()


def test_graph_without_walls_fails(tmp_path):
    workspace = SceneWorkspace(tmp_path, "fixture")
    write_instances(workspace, {"cup": grid((0, 0, 1), (0.1, 0.1, 1.1))})
    write_mesh(workspace, np.zeros((1, 3)), np.zeros((3, 3)))
    workspace.path("align/walls.json").unlink()
    with pytest.raises(FileNotFoundError, match=r"walls\.json"):
        GeometricGraph().run(workspace, {"relations": []})


def test_a_non_positive_membership_radius_is_invalid_parameters(tmp_path):
    with pytest.raises(SceneError, match="membership_radius_m") as error:
        GeometricGraph().run(SceneWorkspace(tmp_path, "bad"), {"membership_radius_m": 0})
    assert error.value.code == "INVALID_PARAMETERS"
    with pytest.raises(SceneError) as error:
        members_within(np.zeros((1, 3)), [np.zeros((1, 3))], -1)
    assert error.value.code == "INVALID_PARAMETERS"


@pytest.mark.parametrize(
    "name,content",
    [
        ("points.ply", b"not a ply"),
        ("points.ply", b"ply\nformat ascii 1.0\nelement vertex 1\nend_header\n"),
        ("mesh.glb", b"not a glb at all, but long enough"),
        ("mesh.glb", None),
    ],
)
def test_unreadable_mesh_assets_are_asset_unreadable(tmp_path, name, content):
    path = tmp_path / name
    if content is not None:
        path.write_bytes(content)
    read = read_ply_points if name.endswith(".ply") else read_glb_positions
    with pytest.raises(SceneError) as error:
        read(path)
    assert error.value.code == "ASSET_UNREADABLE"


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
    write_mesh(workspace, np.zeros((1, 3)), np.zeros((3, 3)))
    write_graph_inputs(workspace)
    before = workspace.path("instances/instances.json").read_bytes()
    result = GeometricGraph().run(workspace, {"relations": []})
    graph = json.loads(workspace.path("graph/scene_graph.json").read_text())
    assert result.num_objects == 1
    assert graph["objects"][0]["id"] == "cup"
    assert graph["objects"][0]["box"]["center"][2] == pytest.approx(1.1)
    assert workspace.path("instances/instances.json").read_bytes() == before
