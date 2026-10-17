"""Exercise the scene-compute HTTP contract with tiny transfer chunks; TargetWorkspace tests are in test_target.py."""

import gzip
import hashlib

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
        assert (
            client.put(
                url,
                headers=headers,
                params={"offset": 0, "total": 700, "sha256": digest},
                content=data[:512],
            ).status_code
            == 200
        )
        assert not (tmp_path / "scenes/room/raw/photo.jpg").exists()
        assert (
            client.put(
                url,
                headers=headers,
                params={"offset": 512, "total": 700, "sha256": digest},
                content=data[512:],
            ).status_code
            == 200
        )
        response = client.get(url, headers={**headers, "Range": "bytes=500-699"})
        assert response.status_code == 206
        assert response.content == b"a" * 200
        assert client.get(url, headers=headers).status_code == 413
        assert (
            client.get("/workspaces/room/files?dirs=raw", headers=headers).json()["files"][0][
                "sha256"
            ]
            == digest
        )
        assert (
            client.put(
                url,
                headers=headers,
                params={"offset": 0, "total": 3, "sha256": "0" * 64},
                content=b"bad",
            ).status_code
            == 422
        )
        assert (tmp_path / "scenes/room/raw/photo.jpg").read_bytes() == data
        assert (
            client.put(
                "/workspaces/room/files/raw/%2e%2e%2f%2e%2e%2fescape",
                headers=headers,
                params={"total": 0, "sha256": hashlib.sha256(b"").hexdigest()},
                content=b"",
            ).status_code
            == 400
        )
        assert client.delete("/workspaces/room", headers=headers).status_code == 204
        assert not (tmp_path / "scenes/room").exists()


def test_whole_file_downloads_are_gzip_compressed_in_transit(tmp_path):
    data = b"vertex 0.25 0.50 0.75\n" * 400
    (tmp_path / "scenes/room/mesh").mkdir(parents=True)
    (tmp_path / "scenes/room/mesh/points.ply").write_bytes(data)
    with TestClient(create_app(tmp_path)) as client:
        url = "/workspaces/room/files/mesh/points.ply"
        with client.stream("GET", url, headers={"Accept-Encoding": "gzip"}) as response:
            sent = b"".join(response.iter_raw())
        assert response.status_code == 200
        assert response.headers["content-encoding"] == "gzip"
        assert len(sent) < len(data) // 4
        assert gzip.decompress(sent) == data
        assert client.get(url).content == data
        # A Range response stays uncompressed, so its length is the requested byte count.
        ranged = client.get(url, headers={"Range": "bytes=100-4099", "Accept-Encoding": "gzip"})
        assert "content-encoding" not in ranged.headers and ranged.content == data[100:4100]


def test_a_clean_start_removes_earlier_workspaces(tmp_path, monkeypatch):
    (tmp_path / "scenes/room/raw").mkdir(parents=True)
    monkeypatch.setenv("CLEAN_ON_START", "1")
    with TestClient(create_app(tmp_path)):
        assert not (tmp_path / "scenes").exists()


def test_create_app_accepts_timeout_and_chunk_bytes(tmp_path):
    app = create_app(tmp_path, chunk_bytes=100_000_000, timeout_s=300)
    with TestClient(app) as client:
        assert client.get("/ping").status_code == 200
