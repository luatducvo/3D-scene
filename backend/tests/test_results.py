import os

import numpy as np
import pytest
from scene_core.contracts import STAGES, SceneWorkspace
from scene_core.errors import SceneError
from scene_core.membership import ObjectMembership
from scene_core.registry import Registry
from scene_core.results import EMBEDDING_DIM, SceneResults
from scene_store import SceneStore


@pytest.fixture
def workspace(tmp_path):
    """A Workspace after every fake Stage has run, as the worker fetches it."""
    workspace = SceneWorkspace(tmp_path, "fixture")
    workspace.dir("raw").joinpath("one.jpg").write_bytes(b"synthetic")
    for stage in STAGES:
        Registry().resolve(f"{stage}.fake")().run(workspace, {})
    return workspace


def write_embeddings(workspace, ids, vectors):
    np.savez(
        workspace.path(SceneResults.EMBEDDINGS),
        ids=np.array(ids),
        vectors=np.asarray(vectors, dtype=np.float32),
    )


def test_load_returns_graph_with_one_embedding_per_object(workspace):
    published = SceneResults(workspace).load()
    assert [o.id for o in published.graph.objects] == ["chair-1", "table-1"]
    assert set(published.embeddings) == {"chair-1", "table-1"}
    assert all(v.shape == (EMBEDDING_DIM,) for v in published.embeddings.values())


@pytest.mark.parametrize(
    "ids,vectors,message",
    [
        (["chair-1"], np.zeros((1, EMBEDDING_DIM)), "different ids"),
        (["chair-1", "chair-1"], np.zeros((2, EMBEDDING_DIM)), "different ids"),
        (["chair-1", "table-1"], np.zeros((2, 512)), "shape"),
        (["chair-1", "table-1"], np.full((2, EMBEDDING_DIM), np.nan), "non-finite"),
    ],
)
def test_load_rejects_embeddings_that_disagree_with_the_graph(workspace, ids, vectors, message):
    write_embeddings(workspace, ids, vectors)
    with pytest.raises(SceneError, match=message) as error:
        SceneResults(workspace).load()
    assert error.value.code == "RESULTS_INVALID"


def test_load_reports_missing_results(workspace):
    workspace.path(SceneResults.GRAPH).unlink()
    with pytest.raises(SceneError) as error:
        SceneResults(workspace).load()
    assert error.value.code == "RESULTS_INVALID"


def test_assets_name_existing_viewer_files_only(workspace):
    results = SceneResults(workspace)
    assert results.assets() == {
        "mesh": "mesh/mesh.glb",
        "points": "mesh/points.ply",
        "membership": "graph/membership.bin",
    }
    workspace.path("mesh/points.ply").unlink()
    workspace.path(SceneResults.MEMBERSHIP).unlink()
    assert results.assets()["points"] is None
    assert results.assets()["membership"] is None


def test_membership_is_the_only_public_file_outside_mesh(workspace):
    results = SceneResults(workspace)
    path = results.public_file(SceneResults.MEMBERSHIP)
    assert ObjectMembership.decode(path.read_bytes()).ids == ["chair-1", "table-1"]
    assert results.public_file("mesh/points.ply").is_file()


def test_membership_round_trips_with_aligned_sections():
    membership = ObjectMembership.from_lists(
        ["ghế-1", "b"], [[4, 1, 1], []], [[0], [2, 0]], point_count=5, vertex_count=3
    )
    data = membership.encode()
    assert data[:4] == b"SCMB" and len(data) % 4 == 0
    decoded = ObjectMembership.decode(data)
    assert decoded.ids == ["ghế-1", "b"]
    assert decoded.points(0).tolist() == [1, 4] and decoded.points(1).tolist() == []
    assert decoded.vertices(1).tolist() == [0, 2]
    assert (decoded.point_count, decoded.vertex_count) == (5, 3)


@pytest.mark.parametrize(
    "corrupt",
    [
        lambda data: data[:-4],
        lambda data: data + b"\0\0\0\0",
        lambda data: b"XXXX" + data[4:],
        # point_count 2 makes index 4 out of range.
        lambda data: data[:12] + (2).to_bytes(4, "little") + data[16:],
    ],
)
def test_membership_decode_rejects_malformed_files(corrupt):
    data = ObjectMembership.from_lists(["a"], [[4]], [[]], 5, 0).encode()
    with pytest.raises(ValueError):
        ObjectMembership.decode(corrupt(data))


def test_load_rejects_membership_of_other_objects(workspace):
    workspace.path(SceneResults.MEMBERSHIP).write_bytes(
        ObjectMembership.from_lists(["table-1", "chair-1"], [[], []], [[], []], 1, 1).encode()
    )
    with pytest.raises(SceneError, match="different Objects") as error:
        SceneResults(workspace).load()
    assert error.value.code == "RESULTS_INVALID"


@pytest.mark.parametrize(
    "path",
    [
        "keyframes/0000.jpg",
        "recon/rgb/0000.png",
        "instances/instances.json",
        "raw/one.jpg",
        "graph/scene_graph.json",
        "graph/manifest.json",
        "graph/membership.bin/x",
        "instances/points/chair-1.npy",
        "embeddings/objects.npz",
        "recon/frames/0000.npz",
        "mesh/../raw/one.jpg",
        "mesh\\mesh.glb",
        "mesh/missing.glb",
        "mesh",
    ],
)
def test_only_mesh_files_and_membership_are_public(workspace, path):
    with pytest.raises(SceneError) as error:
        SceneResults(workspace).public_file(path)
    assert error.value.status_code == 404


@pytest.mark.db
def test_embedding_dim_matches_the_objects_embedding_column():
    store = SceneStore(os.environ["TEST_DATABASE_URL"])
    store.migrate()
    with store.connect() as conn:
        column = conn.execute(
            "SELECT format_type(atttypid,atttypmod) AS type FROM pg_attribute "
            "WHERE attrelid='objects'::regclass AND attname='embedding'"
        ).fetchone()
    assert column["type"] == f"vector({EMBEDDING_DIM})"
