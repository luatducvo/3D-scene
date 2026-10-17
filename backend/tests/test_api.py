import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from scene_api.main import create_app
from scene_core.config import ComputeConfig, PipelineConfig, TargetConfig
from scene_target import open_target_workspace
from scene_worker.runner import Worker

pytestmark = pytest.mark.db


@pytest.fixture
def client(tmp_path):
    with TestClient(
        create_app(database_url=os.environ["TEST_DATABASE_URL"], data_dir=tmp_path)
    ) as client:
        yield client


def worker(client):
    return Worker(
        os.environ["TEST_DATABASE_URL"],
        client.app.state.data_dir,
        PipelineConfig.load(Path(__file__).parents[1] / "config/pipeline.fake.yaml"),
        ComputeConfig(),
    )


def uploaded(client):
    scene = client.post("/api/v1/scenes", json={"name": "Test room"}).json()["id"]
    prefix = f"/api/v1/scenes/{scene}"
    assert client.get(prefix).json()["status"] == "created"
    assert any(s["id"] == scene for s in client.get("/api/v1/scenes").json())
    for name in ("one.jpg", "two.jpg"):
        assert (
            client.post(
                prefix + "/uploads", files={"files": (name, b"synthetic", "image/jpeg")}
            ).status_code
            == 200
        )
    assert client.get(prefix).json()["status"] == "uploaded"
    return prefix


def test_scene_upload_delete(client):
    prefix = uploaded(client)
    raw = sorted(
        p.name
        for p in (
            client.app.state.data_dir / "target" / "scenes" / prefix.rsplit("/", 1)[1] / "raw"
        ).iterdir()
    )
    assert [name.rsplit("-", 1)[0] for name in raw] == ["one", "two"]
    assert (
        client.post(
            prefix + "/uploads", files={"files": ("bad.txt", b"x", "text/plain")}
        ).status_code
        == 415
    )
    assert client.delete(prefix).status_code == 204
    assert client.get(prefix).json()["error"]["code"] == "SCENE_NOT_FOUND"


def test_pipeline_publish_and_rerun(client):
    prefix = uploaded(client)
    runner = worker(client)
    assert client.post(prefix + "/process", json={}).status_code == 202
    for method, path, kwargs in (
        (client.post, "/process", {"json": {}}),
        (client.delete, "", {}),
        (client.post, "/uploads", {"files": {"files": ("two.jpg", b"fake", "image/jpeg")}}),
    ):
        response = method(prefix + path, **kwargs)
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "SCENE_BUSY"
    assert runner.run_once()
    detail = client.get(prefix).json()
    assert detail["status"] == "ready", detail
    assert [s["status"] for s in detail["stage_runs"]] == ["done"] * 9
    objects = client.get(prefix + "/objects").json()
    assert [o["id"] for o in objects] == ["chair-1", "table-1"]
    assert objects[0]["best_views"][0]["image_url"].startswith("http://testserver/")
    assert client.get(detail["assets"]["mesh_url"]).content.startswith(b"glTF")
    assert client.get(objects[0]["best_views"][0]["image_url"]).status_code == 200
    for private in ("raw/private.jpg", "keyframes/0000.jpg", "instances/instances.json"):
        assert client.get(prefix + "/files/" + private).status_code == 404
    assert (
        client.post(
            prefix + "/uploads", files={"files": ("two.jpg", b"fake", "image/jpeg")}
        ).json()["error"]["code"]
        == "SCENE_LOCKED"
    )
    client.post(prefix + "/process", json={})
    assert client.get(prefix).json()["stage_runs"] == []  # the previous Job's Stage Runs are gone
    runner.run_once()
    rerun = client.get(prefix).json()
    assert [s["status"] for s in rerun["stage_runs"]] == ["done"] * 9
    # A new publication gets new URLs; the previous one is removed.
    assert rerun["assets"]["mesh_url"] != detail["assets"]["mesh_url"]
    assert client.get(detail["assets"]["mesh_url"]).status_code == 404
    assert client.get(rerun["assets"]["mesh_url"]).content.startswith(b"glTF")
    assert len(client.get(prefix + "/objects").json()) == 2


def test_progress_replay_and_search(client):
    prefix = uploaded(client)
    client.post(prefix + "/process", json={})
    worker(client).run_once()
    response = client.get(prefix + "/events")
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.text.count("event: stage") == 9
    assert '"ready"' in response.text
    assert (
        client.get(prefix + "/search", params={"q": "cái ghế"}).json()[0]["object"]["id"]
        == "chair-1"
    )
    assert client.get(prefix + "/search", params={"q": "unknown"}).json() == []
    assert client.get(prefix + "/search", params={"q": ""}).json() == []


def test_grounded_qa_stream_and_history(client):
    from scene_api.qa import ScriptedLLM

    prefix = uploaded(client)
    client.post(prefix + "/process", json={})
    worker(client).run_once()
    client.app.state.llm = ScriptedLLM(
        [
            {
                "tool_calls": [
                    {
                        "id": "1",
                        "function": {"name": "count_objects", "arguments": '{"label":"chair"}'},
                    }
                ]
            },
            {"content": "Có 1 ghế trong phòng.", "object_ids": ["chair-1"]},
        ]
    )
    response = client.post(prefix + "/queries", json={"question": "Có bao nhiêu ghế?"})
    assert response.status_code == 200
    assert "event: tool" in response.text and "event: delta" in response.text
    assert "event: final" in response.text and "chair-1" in response.text
    assert "Có 1 ghế" in response.text
    messages = client.get(prefix + "/messages").json()
    assert [m["role"] for m in messages] == ["user", "assistant"]
    client.app.state.llm = ScriptedLLM([])
    assert "event: error" in client.post(prefix + "/queries", json={"question": "fails"}).text
    assert len(client.get(prefix + "/messages").json()) == 2
    assert messages[1]["content"]["object_ids"] == ["chair-1"]


def call(name, arguments, id="1"):
    import json

    return {
        "tool_calls": [{"id": id, "function": {"name": name, "arguments": json.dumps(arguments)}}]
    }


def test_spatial_tools_return_measured_values(client):
    import json

    from scene_api.qa import ScriptedLLM

    prefix = uploaded(client)
    client.post(prefix + "/process", json={})
    worker(client).run_once()
    client.app.state.llm = ScriptedLLM(
        [
            call("measure_distance", {"a_id": "chair-1", "b_id": "table-1"}),
            call("measure_distance", {"a_id": "chair-1", "b_id": "table-1", "mode": "center"}),
            call("get_relations", {"object_id": "chair-1", "predicate": "near"}),
            call("relative_direction", {"a_id": "chair-1", "b_id": "table-1"}),
            {"content": "0.25 m", "object_ids": ["chair-1", "table-1"]},
        ]
    )
    camera = {"position": [1.5, -3, 1], "target": [1.5, 1, 1]}
    text = client.post(prefix + "/queries", json={"question": "How far?", "camera": camera}).text
    assert text.count("event: tool") == 4
    final = json.loads(text.split("event: final\ndata: ")[1].split("\n")[0])
    assert final["object_ids"] == ["chair-1", "table-1"]
    assert [e["object_id"] for e in final["evidence"]] == ["chair-1", "table-1"]
    from scene_api.qa import SceneTools

    objects = client.get(prefix + "/objects").json()
    tools = SceneTools(
        objects,
        [{"subject_id": "chair-1", "predicate": "near", "object_id": "table-1", "value": 0.25}],
        {},
        lambda q: [],
        camera,
    )
    assert (
        tools.execute("measure_distance", {"a_id": "chair-1", "b_id": "table-1"})["distance_m"]
        == 0.25
    )
    assert (
        tools.execute("measure_distance", {"a_id": "chair-1", "b_id": "table-1", "mode": "center"})[
            "distance_m"
        ]
        == 1.005
    )
    assert (
        tools.execute("get_relations", {"object_id": "chair-1", "predicate": "near"})["relations"][
            0
        ]["object_id"]
        == "table-1"
    )
    assert (
        tools.execute("relative_direction", {"a_id": "chair-1", "b_id": "table-1"})["direction"]
        == "left"
    )
    # The table faces +x, so the chair at smaller x is behind it from the table's own front.
    assert (
        tools.execute(
            "relative_direction", {"a_id": "chair-1", "b_id": "table-1", "viewpoint": "object"}
        )["direction"]
        == "behind"
    )
    assert tools.execute("get_object", {"object_id": "missing"}) == {
        "error": "'Unknown object id missing'"
    }


def test_question_rules(client):
    from scene_api.qa import ScriptedLLM

    prefix = uploaded(client)
    assert (
        client.post(prefix + "/queries", json={"question": "?"}).json()["error"]["code"]
        == "SCENE_NOT_READY"
    )
    client.post(prefix + "/process", json={})
    worker(client).run_once()
    client.app.state.llm = ScriptedLLM([call("get_room_info", {}, str(i)) for i in range(6)])
    text = client.post(prefix + "/queries", json={"question": "Loop forever"}).text
    assert text.count("event: tool") == 6 and "QA_STEP_LIMIT" in text


def remote(tmp_path, compute_client, **overrides):
    """A TargetWorkspace on an HTTP Target served by an in-memory scene-compute app."""
    target = TargetConfig(
        **{
            "backend": "http",
            "url": "http://testserver",
            "chunk_size": 512,
            "poll_interval": 0.001,
            **overrides,
        }
    )
    pipeline = PipelineConfig.load(
        Path(__file__).parents[1] / "config/pipeline.fake.yaml"
    ).model_copy(update={"target": "remote"})
    return open_target_workspace(
        tmp_path / "local",
        pipeline,
        ComputeConfig(targets={"remote": target}),
        client=compute_client,
    )


def test_a_failed_upload_keeps_none_of_its_files_on_the_target(tmp_path):
    import httpx
    from scene_compute.server import create_app as create_compute_app

    class BrokenUpload(TestClient):
        def request(self, method, url, **kwargs):
            if method == "PUT" and "/raw/broken-" in str(url):
                raise httpx.ConnectError("tunnel closed")
            return super().request(method, url, **kwargs)

    with BrokenUpload(create_compute_app(tmp_path / "remote", chunk_bytes=512)) as compute:
        target = remote(tmp_path, compute, startup_timeout=0.2)
        with TestClient(
            create_app(
                database_url=os.environ["TEST_DATABASE_URL"],
                data_dir=tmp_path / "local",
                target=target,
            )
        ) as client:
            scene = client.post("/api/v1/scenes", json={"name": "Test room"}).json()["id"]
            prefix = f"/api/v1/scenes/{scene}"
            files = [
                ("files", (f"{name}.jpg", name.encode() * 300, "image/jpeg"))
                for name in ("first", "broken", "last")
            ]
            response = client.post(prefix + "/uploads", files=files)
            assert response.json()["error"]["code"] == "COMPUTE_UNAVAILABLE"
            assert target.list_inputs(scene) == []


def test_delete_removes_the_target_workspace_and_tolerates_an_unreachable_target(tmp_path):
    from scene_compute.server import create_app as create_compute_app

    with TestClient(create_compute_app(tmp_path / "remote", chunk_bytes=512)) as compute:
        target = remote(tmp_path, compute)
        with TestClient(
            create_app(
                database_url=os.environ["TEST_DATABASE_URL"],
                data_dir=tmp_path / "local",
                target=target,
            )
        ) as client:
            prefix = uploaded(client)
            scene = prefix.rsplit("/", 1)[1]
            assert (tmp_path / "remote" / "scenes" / scene / "raw").is_dir()
            assert client.delete(prefix).status_code == 204
            assert not (tmp_path / "remote" / "scenes" / scene).exists()
    down = PipelineConfig.load(Path(__file__).parents[1] / "config/pipeline.fake.yaml").model_copy(
        update={"target": "down"}
    )
    compute = ComputeConfig(
        targets={
            "down": TargetConfig(
                backend="http", url="http://127.0.0.1:9", startup_timeout=0.2, poll_interval=0.05
            )
        }
    )
    with TestClient(
        create_app(
            database_url=os.environ["TEST_DATABASE_URL"],
            data_dir=tmp_path,
            pipeline=down,
            compute=compute,
        )
    ) as client:
        scene = client.post("/api/v1/scenes", json={"name": "Unreachable"}).json()["id"]
        assert client.delete(f"/api/v1/scenes/{scene}").status_code == 204


def test_worker_refuses_to_start_without_configured_gpu_targets(tmp_path, monkeypatch):
    for name in ("GPU_TARGET", "VAST_URL"):
        monkeypatch.delenv(name, raising=False)
    config = Path(__file__).parents[1] / "config"

    def start():
        return Worker(
            os.environ["TEST_DATABASE_URL"],
            tmp_path,
            PipelineConfig.load(config / "pipeline.fake-gpu.yaml"),
            ComputeConfig.load(config / "compute.yaml"),
        )

    with pytest.raises(ValueError, match="GPU_TARGET"):
        start()
    monkeypatch.setenv("GPU_TARGET", "vast")
    with pytest.raises(ValueError, match=r"vast.*URL"):
        start()


def test_whole_pipeline_runs_on_the_gpu_host_and_returns_only_results(tmp_path):
    from scene_compute.server import create_app as create_compute_app

    local, remote_root = tmp_path / "local", tmp_path / "remote"
    with TestClient(create_compute_app(remote_root, chunk_bytes=512)) as compute:
        target = remote(tmp_path, compute)
        runner = Worker(os.environ["TEST_DATABASE_URL"], local, target=target)
        with TestClient(
            create_app(database_url=os.environ["TEST_DATABASE_URL"], data_dir=local, target=target)
        ) as client:
            prefix = uploaded(client)
            scene = prefix.rsplit("/", 1)[1]
            assert not (local / "scenes" / scene).exists()
            assert len(list((remote_root / "scenes" / scene / "raw").iterdir())) == 2
            (remote_root / "scenes" / scene / "segment").mkdir(parents=True)
            (remote_root / "scenes" / scene / "segment" / "stale.npz").write_bytes(b"old")
            for _ in range(2):
                client.post(prefix + "/process", json={})
                runner.run_once()
                detail = client.get(prefix).json()
                assert detail["status"] == "ready", detail
                assert [s["status"] for s in detail["stage_runs"]] == ["done"] * 9
            assert not (remote_root / "scenes" / scene / "segment" / "stale.npz").exists()
            assert len(list((remote_root / "scenes" / scene / "raw").iterdir())) == 2
            [version] = list((local / "scenes" / scene).iterdir())
            assert f"/publications/{version.name}/" in detail["assets"]["mesh_url"]
            workspace = version
            assert sorted(p.name for p in workspace.iterdir()) == [
                "embeddings",
                "graph",
                "mesh",
                "recon",
            ]
            assert [p.name for p in (workspace / "recon").iterdir()] == ["rgb"]
            assert_failed_reprocess_keeps_results(client, runner, prefix, detail)


def test_a_failed_reprocess_keeps_results_on_the_in_process_target(client):
    prefix = uploaded(client)
    runner = worker(client)
    client.post(prefix + "/process", json={})
    runner.run_once()
    detail = client.get(prefix).json()
    assert detail["status"] == "ready"
    assert_failed_reprocess_keeps_results(client, runner, prefix, detail)


def assert_failed_reprocess_keeps_results(client, runner, prefix, detail):
    """A Job failing at its last Stage leaves the earlier mesh, Frame images and Objects in place."""
    mesh = client.get(detail["assets"]["mesh_url"]).content
    runner.target.pipeline.stages["graph"].params = {"fail": "deliberate failure"}
    client.post(prefix + "/process", json={})
    runner.run_once()
    failed = client.get(prefix).json()
    assert failed["status"] == "failed" and failed["failure"]["code"] == "FAKE_STAGE_FAILED"
    assert failed["assets"]["mesh_url"] and client.get(failed["assets"]["mesh_url"]).content == mesh
    objects = client.get(prefix + "/objects").json()
    assert len(objects) == 2
    assert client.get(objects[0]["best_views"][0]["image_url"]).status_code == 200
    runner.target.pipeline.stages["graph"].params = {}


def test_search_reports_unavailable_compute_target(client, monkeypatch):
    prefix = uploaded(client)
    client.post(prefix + "/process", json={})
    worker(client).run_once()
    monkeypatch.delenv("GPU_TARGET", raising=False)
    compute = ComputeConfig.model_validate(
        {
            "targets": {
                "cpu": {},
                "down": {
                    "backend": "http",
                    "url": "http://127.0.0.1:9",
                    "startup_timeout": 0.2,
                    "poll_interval": 0.1,
                },
            }
        }
    )
    for target in (None, "down"):
        if target:
            monkeypatch.setenv("GPU_TARGET", target)
        pipeline = PipelineConfig.load(Path(__file__).parents[1] / "config/pipeline.fake-gpu.yaml")
        with TestClient(
            create_app(
                database_url=os.environ["TEST_DATABASE_URL"],
                data_dir=client.app.state.data_dir,
                pipeline=pipeline,
                compute=compute,
            )
        ) as other:
            response = other.get(prefix + "/search", params={"q": "chair"})
        assert response.status_code == 503, target
        assert response.json()["error"]["code"] == "COMPUTE_UNAVAILABLE"


def test_worker_start_fails_jobs_interrupted_by_a_restart(client):
    prefix = uploaded(client)
    runner = worker(client)
    assert client.post(prefix + "/process", json={}).status_code == 202
    job = runner.store.claim()
    runner.store.stage_started(job, "attributes", "attributes.fake")  # a worker died mid-Stage
    worker(client).recover_interrupted()
    detail = client.get(prefix).json()
    assert detail["status"] == "failed"
    assert (
        detail["failure"]["code"] == "WORKER_INTERRUPTED"
        and detail["failure"]["stage"] == "attributes"
    )
    assert next(s for s in detail["stage_runs"] if s["stage"] == "attributes")["status"] == "failed"
    assert client.post(prefix + "/process", json={}).status_code == 202
    assert runner.run_once() and client.get(prefix).json()["status"] == "ready"


def test_stage_progress_is_throttled_stored_and_replayed(client):
    prefix = uploaded(client)
    scene = prefix.rsplit("/", 1)[1]
    runner = worker(client)
    runner.target.pipeline.stages["mesh"].params["progress_steps"] = 500
    client.post(prefix + "/process", json={})
    runner.run_once()
    with runner.store.connect() as conn:
        events = [
            r["data"]
            for r in conn.execute(
                "SELECT data FROM scene_events WHERE scene_id=%s AND event='progress' ORDER BY id",
                (scene,),
            ).fetchall()
        ]
    mesh = [e for e in events if e["stage"] == "mesh"]
    assert [(e["done"], e["total"], e["unit"]) for e in mesh] == [
        (0, 500, "step"),
        (500, 500, "step"),
    ]
    runs = {s["stage"]: s for s in client.get(prefix).json()["stage_runs"]}
    assert runs["mesh"]["progress"] == {"done": 500, "total": 500, "unit": "step"}
    assert all(s["started_at"] for s in runs.values())
    import json

    replay = [
        json.loads(line[6:])
        for line in client.get(prefix + "/events").text.splitlines()
        if line.startswith("data: ")
    ]
    mesh_replay = [e for e in replay if e.get("stage") == "mesh"]
    assert (
        [e["type"] for e in mesh_replay] == ["stage", "progress"]
        and mesh_replay[0]["started_at"]
        and "progress" not in mesh_replay[0]
    )
    assert (mesh_replay[1]["done"], mesh_replay[1]["total"], mesh_replay[1]["unit"]) == (
        500,
        500,
        "step",
    )


def test_unpublished_scenes_do_not_serve_flat_result_folders(client):
    scene = client.post("/api/v1/scenes", json={"name": "Old"}).json()["id"]
    flat_results = client.app.state.data_dir / "scenes" / scene / "mesh"
    flat_results.mkdir(parents=True)
    (flat_results / "mesh.glb").write_bytes(b"glTF-old")
    assert client.get(f"/api/v1/scenes/{scene}").json()["assets"] == {
        "mesh_url": None,
        "points_url": None,
    }
    assert (
        client.get(f"/api/v1/scenes/{scene}/publications/legacy/files/mesh/mesh.glb").status_code
        == 404
    )
    assert (
        client.get(
            f"/api/v1/scenes/{scene}/publications/..%2F..%2Fraw/files/mesh/mesh.glb"
        ).status_code
        == 404
    )


def test_answers_may_only_state_numbers_a_tool_returned(client):
    from scene_api.qa import ScriptedLLM

    prefix = uploaded(client)
    client.post(prefix + "/process", json={})
    worker(client).run_once()
    unsupported = {"content": "The sofa is 999 meters long.", "object_ids": []}
    client.app.state.llm = ScriptedLLM([unsupported, unsupported])
    text = client.post(prefix + "/queries", json={"question": "How long is the sofa?"}).text
    assert "QA_UNGROUNDED" in text and "event: final" not in text
    # After the corrective message the model measures, and the measured answer is accepted.
    client.app.state.llm = ScriptedLLM(
        [
            unsupported,
            call("measure_distance", {"a_id": "chair-1", "b_id": "table-1"}),
            {"content": "About 25 cm (0.25 m).", "object_ids": ["chair-1"]},
        ]
    )
    text = client.post(prefix + "/queries", json={"question": "How far?"}).text
    assert "event: final" in text and "0.25 m" in text
    # A final_answer next to another tool call runs that tool first, then is checked against its result.
    both = {
        "tool_calls": [
            {
                "id": "1",
                "function": {
                    "name": "measure_distance",
                    "arguments": '{"a_id":"chair-1","b_id":"table-1"}',
                },
            },
            {
                "id": "2",
                "function": {
                    "name": "final_answer",
                    "arguments": '{"answer":"0.25 m","object_ids":["chair-1","table-1"]}',
                },
            },
        ]
    }
    client.app.state.llm = ScriptedLLM([both])
    text = client.post(prefix + "/queries", json={"question": "How far?"}).text
    assert text.count("event: tool") == 1 and "event: final" in text
