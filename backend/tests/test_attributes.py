import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from PIL import Image

from scene_core.contracts import SceneWorkspace
from scene_stages.attributes import VisionAttributes


def test_vlm_records_valid_attributes_and_counts_malformed_output(tmp_path, monkeypatch):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            assert body["model"] == "fixture-vision"
            assert body["messages"][1]["content"][1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
            label = body["messages"][1]["content"][0]["text"].split()[2].rstrip(".")
            content = json.dumps({"label_vi": "cốc", "attributes": {"color": ["red"]}}) if label == "cup" else "not JSON"
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"choices": [{"message": {"content": content}}]}).encode())

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("VLM_BASE_URL", f"http://127.0.0.1:{server.server_port}/v1")
    monkeypatch.setenv("VLM_API_KEY", "fixture-key")
    monkeypatch.setenv("VLM_MODEL", "fixture-vision")
    workspace = SceneWorkspace(tmp_path, "attrs")
    instances = [{"id": "cup", "label": "cup"}, {"id": "table", "label": "table"}]
    workspace.dir("instances").joinpath("instances.json").write_text(json.dumps(instances))
    for item in instances:
        Image.new("RGB", (8, 8)).save(workspace.dir("instances/crops") / f"{item['id']}_0.jpg")
    try:
        manifest = VisionAttributes().run(workspace, {})
    finally:
        server.shutdown()
        server.server_close()
    result = json.loads(workspace.path("attributes/attributes.json").read_text())
    assert result["cup"]["attributes"]["color"] == ["red"]
    assert result["table"] == {}
    assert manifest.invalid_outputs == 1


def test_vlm_request_that_never_completes_fails_only_its_object(tmp_path, monkeypatch):
    import time

    class Handler(BaseHTTPRequestHandler):
        calls = []

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            label = body["messages"][1]["content"][0]["text"].split()[2].rstrip(".")
            Handler.calls.append(label)
            if label == "lamp":  # keep-alive bytes forever, never an answer
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                try:
                    for _ in range(100):
                        self.wfile.write(b" ")
                        self.wfile.flush()
                        time.sleep(.1)
                except OSError:
                    pass
                return
            if label == "cup" and Handler.calls.count("cup") == 1:
                self.send_response(503)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            content = json.dumps({"label_vi": "cốc", "attributes": {"color": ["red"]}})
            self.wfile.write(json.dumps({"choices": [{"message": {"content": content}}]}).encode())

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv("VLM_BASE_URL", f"http://127.0.0.1:{server.server_port}/v1")
    monkeypatch.setenv("VLM_API_KEY", "fixture-key")
    monkeypatch.setenv("VLM_MODEL", "fixture-vision")
    workspace = SceneWorkspace(tmp_path, "stalled")
    instances = [{"id": "lamp-1", "label": "lamp"}, {"id": "cup-1", "label": "cup"}]
    workspace.dir("instances").joinpath("instances.json").write_text(json.dumps(instances))
    for item in instances:
        Image.new("RGB", (8, 8)).save(workspace.dir("instances/crops") / f"{item['id']}_0.jpg")
    start = time.monotonic()
    try:
        manifest = VisionAttributes().run(workspace, {"request_timeout_s": .5, "max_retries": 1})
    finally:
        server.shutdown()
        server.server_close()
    assert time.monotonic() - start < 5
    result = json.loads(workspace.path("attributes/attributes.json").read_text(encoding="utf-8"))
    errors = json.loads(workspace.path("attributes/errors.json").read_text(encoding="utf-8"))
    assert result["lamp-1"] == {} and errors[0]["object_id"] == "lamp-1"
    assert result["cup-1"]["label_vi"] == "cốc"
    assert Handler.calls.count("lamp") == 2 and Handler.calls.count("cup") == 2
    assert manifest.invalid_outputs == 1


def test_vlm_requests_run_in_parallel_and_merge_extra_body(tmp_path, monkeypatch):
    import time

    class Handler(BaseHTTPRequestHandler):
        bodies = []

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            Handler.bodies.append(body)
            time.sleep(.5)
            content = json.dumps({"label_vi": "ghế", "attributes": {"color": ["blue"]}})
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"choices": [{"message": {"content": content}}]}).encode())

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv("VLM_BASE_URL", f"http://127.0.0.1:{server.server_port}/v1")
    monkeypatch.setenv("VLM_API_KEY", "fixture-key")
    monkeypatch.setenv("VLM_MODEL", "fixture-vision")
    workspace = SceneWorkspace(tmp_path, "parallel")
    instances = [{"id": f"chair-{i}", "label": "chair"} for i in range(6)]
    workspace.dir("instances").joinpath("instances.json").write_text(json.dumps(instances))
    for item in instances:
        Image.new("RGB", (8, 8)).save(workspace.dir("instances/crops") / f"{item['id']}_0.jpg")
    start = time.monotonic()
    try:
        manifest = VisionAttributes().run(workspace, {"concurrency": 6, "extra_body": {"reasoning": {"enabled": False}}, "max_tokens": 200})
    finally:
        server.shutdown()
        server.server_close()
    assert time.monotonic() - start < 2  # six 0.5 s answers, sequential would take 3 s
    result = json.loads(workspace.path("attributes/attributes.json").read_text(encoding="utf-8"))
    assert list(result) == [item["id"] for item in instances]
    assert all(value["label_vi"] == "ghế" for value in result.values())
    assert all(body["reasoning"] == {"enabled": False} and body["max_tokens"] == 200 and body["model"] == "fixture-vision" for body in Handler.bodies)
    assert manifest.invalid_outputs == 0


def test_no_attributes_writes_an_empty_entry_per_instance_without_an_endpoint(tmp_path, monkeypatch):
    from scene_core.registry import Registry
    from scene_stages.attributes import NoAttributes

    monkeypatch.delenv("VLM_BASE_URL", raising=False)
    workspace = SceneWorkspace(tmp_path, "none")
    instances = [{"id": "cup", "label": "cup"}, {"id": "table", "label": "table"}]
    workspace.dir("instances").joinpath("instances.json").write_text(json.dumps(instances))
    manifest = NoAttributes().run(workspace, {})
    assert json.loads(workspace.path("attributes/attributes.json").read_text()) == {"cup": {}, "table": {}}
    assert json.loads(workspace.path("attributes/errors.json").read_text()) == []
    assert manifest.num_objects == 2 and manifest.invalid_outputs == 0
    assert Registry().resolve("attributes.none") is NoAttributes
