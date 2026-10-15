import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from scene_api.main import create_app
from scene_worker.runner import Worker
from scene_core.config import PipelineConfig,ComputeConfig

@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(database_url=os.environ["TEST_DATABASE_URL"],data_dir=tmp_path)) as client:yield client

def worker(client):
    return Worker(os.environ["TEST_DATABASE_URL"],client.app.state.data_dir,PipelineConfig.load(Path(__file__).parents[1]/"config/pipeline.fake.yaml"),ComputeConfig())
def uploaded(client):
    scene=client.post("/api/v1/scenes",json={"name":"Test room"}).json()["id"]
    prefix=f"/api/v1/scenes/{scene}"
    assert client.get(prefix).json()["status"]=="created"
    assert any(s["id"]==scene for s in client.get("/api/v1/scenes").json())
    for name in ("one.jpg","two.jpg"):
        assert client.post(prefix+"/uploads",files={"files":(name,b"synthetic","image/jpeg")}).status_code==200
    assert client.get(prefix).json()["status"]=="uploaded"
    return prefix

def test_scene_upload_delete(client):
    prefix=uploaded(client)
    raw=sorted(p.name for p in (client.app.state.data_dir/"scenes"/prefix.rsplit("/",1)[1]/"raw").iterdir())
    assert [name.rsplit("-",1)[0] for name in raw]==["one","two"]
    assert client.post(prefix+"/uploads",files={"files":("bad.txt",b"x","text/plain")}).status_code==415
    assert client.delete(prefix).status_code==204
    assert client.get(prefix).json()["error"]["code"]=="SCENE_NOT_FOUND"

def test_pipeline_publish_and_rerun(client):
    prefix=uploaded(client);runner=worker(client)
    assert client.post(prefix+"/process",json={}).status_code==202
    for method,path,kwargs in ((client.post,"/process",{"json":{}}),(client.delete,"",{}),(client.post,"/uploads",{"files":{"files":("two.jpg",b"fake","image/jpeg")}})):
        response=method(prefix+path,**kwargs)
        assert response.status_code==409
        assert response.json()["error"]["code"]=="SCENE_BUSY"
    assert runner.run_once()
    detail=client.get(prefix).json()
    assert detail["status"]=="ready",detail
    assert [s["status"] for s in detail["stage_runs"]]==["done"]*9
    objects=client.get(prefix+"/objects").json()
    assert [o["id"] for o in objects]==["chair-1","table-1"]
    assert objects[0]["best_views"][0]["image_url"].startswith("http://testserver/")
    assert client.get(detail["assets"]["mesh_url"]).content.startswith(b"glTF")
    assert client.get(prefix+"/files/raw/private.jpg").status_code==403
    assert client.post(prefix+"/uploads",files={"files":("two.jpg",b"fake","image/jpeg")}).json()["error"]["code"]=="SCENE_LOCKED"
    client.post(prefix+"/process",json={});runner.run_once()
    assert [s["status"] for s in client.get(prefix).json()["stage_runs"]]==["skipped"]*9
    client.post(prefix+"/process",json={"from_stage":"mesh"});runner.run_once()
    assert [s["status"] for s in client.get(prefix).json()["stage_runs"]]==["skipped"]*3+["done"]*6
    assert len(client.get(prefix+"/objects").json())==2

def test_progress_replay_and_search(client):
    prefix=uploaded(client)
    client.post(prefix+"/process",json={});worker(client).run_once()
    response=client.get(prefix+"/events")
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.text.count("event: stage")==9
    assert '"ready"' in response.text
    assert client.get(prefix+"/search",params={"q":"cái ghế"}).json()[0]["object"]["id"]=="chair-1"
    assert client.get(prefix+"/search",params={"q":"unknown"}).json()==[]
    assert client.get(prefix+"/search",params={"q":""}).json()==[]


def test_grounded_qa_stream_and_history(client):
    from scene_api.qa import ScriptedLLM
    prefix=uploaded(client);client.post(prefix+"/process",json={});worker(client).run_once()
    client.app.state.llm=ScriptedLLM([
      {"tool_calls":[{"id":"1","function":{"name":"count_objects","arguments":"{\"label\":\"chair\"}"}}]},
      {"content":"Có 1 ghế trong phòng.","object_ids":["chair-1"]}
    ])
    response=client.post(prefix+"/queries",json={"question":"Có bao nhiêu ghế?"})
    assert response.status_code==200
    assert "event: tool" in response.text and "event: delta" in response.text
    assert "event: final" in response.text and "chair-1" in response.text
    assert "Có 1 ghế" in response.text
    messages=client.get(prefix+"/messages").json()
    assert [m["role"] for m in messages]==["user","assistant"]
    client.app.state.llm=ScriptedLLM([])
    assert "event: error" in client.post(prefix+"/queries",json={"question":"fails"}).text
    assert len(client.get(prefix+"/messages").json())==2
    assert messages[1]["content"]["object_ids"]==["chair-1"]


def call(name,arguments,id="1"):
    import json
    return {"tool_calls":[{"id":id,"function":{"name":name,"arguments":json.dumps(arguments)}}]}


def test_spatial_tools_return_measured_values(client):
    import json
    from scene_api.qa import ScriptedLLM
    prefix=uploaded(client);client.post(prefix+"/process",json={});worker(client).run_once()
    client.app.state.llm=ScriptedLLM([
      call("measure_distance",{"a_id":"chair-1","b_id":"table-1"}),
      call("measure_distance",{"a_id":"chair-1","b_id":"table-1","mode":"center"}),
      call("get_relations",{"object_id":"chair-1","predicate":"near"}),
      call("relative_direction",{"a_id":"chair-1","b_id":"table-1"}),
      {"content":"0.25 m","object_ids":["chair-1","table-1"]},
    ])
    camera={"position":[1.5,-3,1],"target":[1.5,1,1]}
    text=client.post(prefix+"/queries",json={"question":"How far?","camera":camera}).text
    assert text.count("event: tool")==4
    final=json.loads(text.split("event: final\ndata: ")[1].split("\n")[0])
    assert final["object_ids"]==["chair-1","table-1"]
    assert [e["object_id"] for e in final["evidence"]]==["chair-1","table-1"]
    from scene_api.qa import SceneTools
    objects=client.get(prefix+"/objects").json()
    tools=SceneTools(objects,[{"subject_id":"chair-1","predicate":"near","object_id":"table-1","value":0.25}],{},lambda q:[],camera)
    assert tools.execute("measure_distance",{"a_id":"chair-1","b_id":"table-1"})["distance_m"]==0.25
    assert tools.execute("measure_distance",{"a_id":"chair-1","b_id":"table-1","mode":"center"})["distance_m"]==1.005
    assert tools.execute("get_relations",{"object_id":"chair-1","predicate":"near"})["relations"][0]["object_id"]=="table-1"
    assert tools.execute("relative_direction",{"a_id":"chair-1","b_id":"table-1"})["direction"]=="left"
    # The table faces +x, so the chair at smaller x is behind it from the table's own front.
    assert tools.execute("relative_direction",{"a_id":"chair-1","b_id":"table-1","viewpoint":"object"})["direction"]=="behind"
    assert tools.execute("get_object",{"object_id":"missing"})=={"error":"'Unknown object id missing'"}


def test_question_rules(client):
    from scene_api.qa import ScriptedLLM
    prefix=uploaded(client)
    assert client.post(prefix+"/queries",json={"question":"?"}).json()["error"]["code"]=="SCENE_NOT_READY"
    client.post(prefix+"/process",json={});worker(client).run_once()
    client.app.state.llm=ScriptedLLM([call("get_room_info",{},str(i)) for i in range(6)])
    text=client.post(prefix+"/queries",json={"question":"Loop forever"}).text
    assert text.count("event: tool")==6 and "QA_STEP_LIMIT" in text


def test_delete_cleans_remote_workspaces_and_tolerates_unreachable_targets(tmp_path,monkeypatch):
    from scene_core.config import TargetConfig
    import scene_worker.container as container
    deleted=[]
    class Recorder:
        def __init__(self,data_dir,target):self.target=target
        def delete_workspace(self,scene_id):
            if self.target.url=="http://down":raise ConnectionError("unreachable")
            deleted.append((self.target.url,scene_id))
        def close(self):pass
    monkeypatch.setattr(container,"HttpBackend",Recorder,raising=False)
    compute=ComputeConfig(targets={"cpu":TargetConfig(),"shared":TargetConfig(backend="http",url="http://shared",shared_storage=True),
        "remote":TargetConfig(backend="http",url="http://remote"),"down":TargetConfig(backend="http",url="http://down"),"unset":TargetConfig(backend="http")})
    with TestClient(create_app(database_url=os.environ["TEST_DATABASE_URL"],data_dir=tmp_path,compute=compute)) as client:
        scene=client.post("/api/v1/scenes",json={"name":"Remote"}).json()["id"]
        assert client.delete(f"/api/v1/scenes/{scene}").status_code==204
    assert deleted==[("http://remote",scene)]


def test_worker_refuses_to_start_without_configured_gpu_targets(tmp_path, monkeypatch):
    for name in ("GPU_TARGET", "VAST_URL"):
        monkeypatch.delenv(name, raising=False)
    config = Path(__file__).parents[1]/"config"
    start = lambda: Worker(os.environ["TEST_DATABASE_URL"], tmp_path, PipelineConfig.load(config/"pipeline.fake-gpu.yaml"), ComputeConfig.load(config/"compute.yaml"))
    with pytest.raises(ValueError, match="GPU_TARGET"):
        start()
    monkeypatch.setenv("GPU_TARGET", "vast")
    with pytest.raises(ValueError, match="vast.*URL"):
        start()


def test_search_reports_unavailable_compute_target(client, monkeypatch):
    prefix=uploaded(client);client.post(prefix+"/process",json={});worker(client).run_once()
    monkeypatch.delenv("GPU_TARGET",raising=False)
    client.app.state.pipeline=PipelineConfig.load(Path(__file__).parents[1]/"config/pipeline.fake-gpu.yaml")
    client.app.state.compute=ComputeConfig.model_validate({"targets":{"cpu":{},"down":{"backend":"http","url":"http://127.0.0.1:9","startup_timeout":0.2,"poll_interval":0.1}}})
    for target in (None,"down"):
        if target:monkeypatch.setenv("GPU_TARGET",target);client.app.state.pipeline=PipelineConfig.load(Path(__file__).parents[1]/"config/pipeline.fake-gpu.yaml")
        client.app.state.embedder=None
        response=client.get(prefix+"/search",params={"q":"chair"})
        assert response.status_code==503,target
        assert response.json()["error"]["code"]=="COMPUTE_UNAVAILABLE"


def test_worker_start_fails_jobs_interrupted_by_a_restart(client):
    prefix=uploaded(client);scene=prefix.rsplit("/",1)[1];runner=worker(client)
    assert client.post(prefix+"/process",json={}).status_code==202
    with runner.repo.connect() as conn:  # a worker died mid-Stage
        conn.execute("UPDATE jobs SET status='running',started_at=now() WHERE scene_id=%s",(scene,))
        conn.execute("INSERT INTO stage_runs(scene_id,stage,algorithm,config_hash,status) VALUES(%s,'attributes','attributes.fake','x','running')",(scene,))
    worker(client).recover_interrupted()
    detail=client.get(prefix).json()
    assert detail["status"]=="failed"
    assert detail["failure"]["code"]=="WORKER_INTERRUPTED" and detail["failure"]["stage"]=="attributes"
    assert next(s for s in detail["stage_runs"] if s["stage"]=="attributes")["status"]=="failed"
    assert client.post(prefix+"/process",json={}).status_code==202
    assert runner.run_once() and client.get(prefix).json()["status"]=="ready"


def test_stage_progress_is_throttled_stored_and_replayed(client):
    prefix=uploaded(client);scene=prefix.rsplit("/",1)[1];runner=worker(client)
    runner.pipeline.stages["mesh"].params["progress_steps"]=500
    client.post(prefix+"/process",json={});runner.run_once()
    with runner.repo.connect() as conn:
        events=[r["data"] for r in conn.execute("SELECT data FROM scene_events WHERE scene_id=%s AND event='progress' ORDER BY id",(scene,)).fetchall()]
    mesh=[e for e in events if e["stage"]=="mesh"]
    assert [(e["done"],e["total"],e["unit"]) for e in mesh]==[(0,500,"step"),(500,500,"step")]
    runs={s["stage"]:s for s in client.get(prefix).json()["stage_runs"]}
    assert runs["mesh"]["progress"]=={"done":500,"total":500,"unit":"step"}
    assert all(s["started_at"] for s in runs.values())
    import json
    replay=[json.loads(line[6:]) for line in client.get(prefix+"/events").text.splitlines() if line.startswith("data: ")]
    mesh_replay=next(e for e in replay if e.get("stage")=="mesh")
    assert mesh_replay["progress"]=={"done":500,"total":500,"unit":"step"} and mesh_replay["started_at"]
