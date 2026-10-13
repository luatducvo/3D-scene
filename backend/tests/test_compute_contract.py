"""Exercise the HTTP contract with non-shared storage and tiny transfer chunks."""
import hashlib
import pytest

from fastapi.testclient import TestClient

from scene_compute.server import create_app


def test_chunked_upload_is_atomic_and_verifies_checksum(tmp_path):
    app = create_app(tmp_path, token="secret", chunk_bytes=512)
    with TestClient(app) as client:
        url = "/workspaces/room/files/raw/photo.jpg"
        headers = {"X-Compute-Token": "secret"}
        data = b"a" * 700
        digest = hashlib.sha256(data).hexdigest()
        assert client.get("/info").status_code == 401
        assert client.put(url, headers=headers, params={"offset": 0, "total": 700, "sha256": digest}, content=data[:512]).status_code == 200
        assert not (tmp_path / "scenes/room/raw/photo.jpg").exists()
        assert client.put(url, headers=headers, params={"offset": 512, "total": 700, "sha256": digest}, content=data[512:]).status_code == 200
        response = client.get(url, headers={**headers, "Range": "bytes=500-699"})
        assert response.status_code == 206
        assert response.content == b"a" * 200
        assert client.get(url, headers=headers).status_code == 413
        assert client.get("/workspaces/room/files?dirs=raw", headers=headers).json()["files"][0]["sha256"] == digest
        assert client.put(url, headers=headers, params={"offset": 0, "total": 3, "sha256": "0" * 64}, content=b"bad").status_code == 422
        assert (tmp_path / "scenes/room/raw/photo.jpg").read_bytes() == data
        assert client.put("/workspaces/room/files/raw/%2e%2e%2f%2e%2e%2fescape", headers=headers, params={"total": 0, "sha256": hashlib.sha256(b"").hexdigest()}, content=b"").status_code == 400
        assert client.delete("/workspaces/room", headers=headers).status_code == 204
        assert not (tmp_path / "scenes/room").exists()


def test_remote_fake_stage_roundtrip_skip_failure_and_cleanup(tmp_path):
    from scene_core.config import TargetConfig
    from scene_worker.compute.http import HttpBackend, ComputeError

    local, remote = tmp_path / "local", tmp_path / "remote"
    raw = local / "scenes/room/raw"
    raw.mkdir(parents=True)
    (raw / "sample.jpg").write_bytes(b"fixture" * 120)
    app = create_app(remote, chunk_bytes=512)
    requests = []
    with TestClient(app) as client:
        client.event_hooks["request"].append(lambda request: requests.append((request.method, request.url.path)))
        backend = HttpBackend(local, TargetConfig(url="http://testserver", chunk_size=512, poll_interval=.001), client=client)
        result = backend.run("ingest.fake", "room", {}, ["raw"], ["keyframes"])
        assert result["num_keyframes"] == 1
        assert (local / "scenes/room/keyframes/0000.jpg").read_bytes() == (remote / "scenes/room/keyframes/0000.jpg").read_bytes()
        requests.clear()
        backend.run("ingest.fake", "room", {}, ["raw"], ["keyframes"])
        assert not any(method == "PUT" for method, _ in requests)
        with pytest.raises(ComputeError, match="deliberate failure"):
            backend.run("ingest.fake", "room", {"fail": "deliberate failure"}, ["raw"], ["keyframes"])
        backend.delete_workspace("room")
        assert not (remote / "scenes/room").exists()


def test_shared_storage_avoids_file_endpoints(tmp_path):
    from scene_core.config import TargetConfig
    from scene_worker.compute.http import HttpBackend

    raw = tmp_path / "scenes/room/raw"
    raw.mkdir(parents=True)
    (raw / "input.jpg").write_bytes(b"synthetic")
    with TestClient(create_app(tmp_path)) as client:
        paths = []
        client.event_hooks["request"].append(lambda request: paths.append(request.url.path))
        backend = HttpBackend(tmp_path, TargetConfig(url="http://testserver", shared_storage=True, poll_interval=.001), client=client)
        assert backend.run("ingest.fake", "room", {}, ["raw"], ["keyframes"])["num_keyframes"] == 1
        assert not any("/files" in path for path in paths)
