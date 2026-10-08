import hashlib
import io
import json
import tarfile

import numpy as np
from fastapi.testclient import TestClient

from s3d_app.api import app


def package_bytes(label: str = "first", corrupt: bool = False,
                  translation: float = 0) -> bytes:
    vertices = b"""ply
format ascii 1.0
element vertex 3
property float x
property float y
property float z
property uchar red
property uchar green
property uchar blue
element face 1
property list uchar int vertex_indices
end_header
0 0 0 255 0 0
1 0 0 0 255 0
0 1 0 0 0 255
3 0 1 2
"""
    segments = io.BytesIO()
    np.save(segments, np.array([7, 7, 8], dtype=np.int32), allow_pickle=False)
    files = {
        "mesh/vh_clean_2.ply": vertices,
        "mesh/superpoints.npy": segments.getvalue(),
        "calib/intrinsics.json": b"{}",
        "frames/index.parquet": b"test",
        "frames/color/000000.jpg": label.encode(),
        "frames/depth/000000.png": b"depth",
        "frames/pose/000000.txt": b"1 0 0 0\n0 1 0 0\n0 0 1 0\n0 0 0 1\n",
    }
    alignment = np.eye(4)
    alignment[0, 3] = translation
    manifest = {
        "format_version": "s3dpkg/1", "status": "complete", "scan_id": "scene0000_00",
        "aligned": bool(translation), "axis_alignment": alignment.tolist(),
        "files": {name: hashlib.sha256(content).hexdigest() for name, content in files.items()},
    }
    if corrupt:
        files["frames/color/000000.jpg"] = b"tampered"
    files["manifest.json"] = json.dumps(manifest).encode()
    result = io.BytesIO()
    with tarfile.open(fileobj=result, mode="w:") as archive:
        for name, content in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
    return result.getvalue()


def test_import_noop_replace_and_checksum(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("S3D_DATA_DIR", str(tmp_path / "data"))
    client = TestClient(app)

    def upload(content: bytes, replace: bool = False):
        return client.post("/v1/imports", files={"file": ("scan.s3dpkg", content)},
                           data={"replace": str(replace).lower()})

    assert upload(package_bytes()).json() == {"scene_id": "scene0000_00", "status": "imported"}
    assert len(client.get("/v1/scenes").json()) == 1
    assert upload(package_bytes()).json()["status"] == "unchanged"
    assert upload(package_bytes("second")).status_code == 409
    from s3d_app.storage import database

    with database() as connection:
        connection.execute("UPDATE jobs SET status = 'complete'")
    assert upload(package_bytes("second"), replace=True).json()["status"] == "imported"
    response = upload(package_bytes(corrupt=True))
    assert response.status_code == 400
    assert "SHA-256 mismatch" in response.json()["detail"]


def test_load_and_publish_preserve_vertex_order(monkeypatch, tmp_path) -> None:
    import struct
    from pathlib import Path

    from s3d_app.pipeline import artifact_dir, load_package, publish_mesh

    monkeypatch.setenv("S3D_DATA_DIR", str(tmp_path))
    package = Path(tmp_path / "sample.s3dpkg")
    package.write_bytes(package_bytes(translation=10))
    load_package("scene0000_00", package)
    publish_mesh("scene0000_00")
    mesh = (artifact_dir("scene0000_00", "S6") / "mesh.bin").read_bytes()
    assert struct.unpack_from("<4sIII", mesh) == (b"S3DM", 1, 3, 3)
    positions = struct.unpack_from("<9f", mesh, 16)
    assert positions == (10, 0, 0, 11, 0, 0, 10, 1, 0)
    assert struct.unpack_from("<3i", mesh, len(mesh) - 12) == (-1, -1, -1)
