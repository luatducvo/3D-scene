"""Durable local job runner for Package loading and mesh publication."""

import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import tarfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path, PurePosixPath

import numpy as np
from plyfile import PlyData

from s3d_app.gpu import GPU, VramMeter
from s3d_app.llm import LlmRouter
from s3d_app.storage import data_root, database

STAGES = ("S1", "S2", "S3", "S4a", "S4b", "S4c", "S5", "S6")
CONFIG_HASH = hashlib.sha256(b"s3dpkg/1:s1-s6:1").hexdigest()[:12]
WAKE = threading.Event()
STOP = threading.Event()


def artifact_dir(scene_id: str, stage: str) -> Path:
    voxel = os.getenv("S3D_MASK3D_VOXEL", "0.03")
    configurations = {"S2": "geometry:cuda-v3", "S3": f"mask3d:scannet200-val:{voxel}:xyz-v3",
                      "S4": f"yoloe26:mobileclip2:v2:{voxel}",
                      "S5": f"graph:v3:{voxel}", "S6": f"mesh:v3:{voxel}"}
    config_hash = (hashlib.sha256(configurations[stage].encode()).hexdigest()[:12]
                   if stage in configurations else CONFIG_HASH)
    return data_root() / "scenes" / scene_id / stage / config_hash


def load_package(scene_id: str, package: Path) -> None:
    target = artifact_dir(scene_id, "S1")
    if (target / "complete.json").exists():
        return
    temporary = target.with_name(target.name + ".partial")
    if temporary.exists():
        shutil.rmtree(temporary)
    temporary.mkdir(parents=True)
    with tarfile.open(package, "r:") as archive:
        manifest = json.load(archive.extractfile("manifest.json"))
        for member in archive.getmembers():
            if member.name == "manifest.json":
                continue
            destination = temporary / member.name
            if not destination.resolve().is_relative_to(temporary.resolve()):
                raise ValueError("Package member escapes the extraction directory")
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("wb") as output:
                shutil.copyfileobj(archive.extractfile(member), output)
    alignment = np.asarray(manifest["axis_alignment"], dtype=np.float64)
    mesh_path = temporary / "mesh/vh_clean_2.ply"
    mesh = PlyData.read(mesh_path, mmap=False)
    vertex = mesh["vertex"].data
    xyz = np.column_stack((vertex["x"], vertex["y"], vertex["z"], np.ones(len(vertex))))
    aligned_xyz = xyz @ alignment.T
    for index, field in enumerate(("x", "y", "z")):
        vertex[field] = aligned_xyz[:, index]
    mesh.write(mesh_path)
    for pose_path in (temporary / "frames/pose").glob("*.txt"):
        pose = np.loadtxt(pose_path)
        np.savetxt(pose_path, alignment @ pose, fmt="%.9g")
    (temporary / "complete.json").write_text(json.dumps({"aligned": manifest["aligned"]}))
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        shutil.rmtree(target)
    temporary.replace(target)


def publish_mesh(scene_id: str) -> None:
    target = artifact_dir(scene_id, "S6")
    if (target / "mesh.bin").exists():
        return
    source = artifact_dir(scene_id, "S1") / "mesh/vh_clean_2.ply"
    mesh = PlyData.read(source)
    vertex = mesh["vertex"].data
    xyz = np.column_stack((vertex["x"], vertex["y"], vertex["z"])).astype("<f4")
    color = np.column_stack(tuple(vertex[name] for name in ("red", "green", "blue"))).astype("u1")
    faces = mesh["face"].data["vertex_indices"]
    triangles = []
    for face in faces:
        if len(face) < 3:
            continue
        for index in range(1, len(face) - 1):
            triangles.extend((face[0], face[index], face[index + 1]))
    indices = np.asarray(triangles, dtype="<u4")
    masks_path = artifact_dir(scene_id, "S3") / "masks.npz"
    if masks_path.is_file():
        with np.load(masks_path, allow_pickle=False) as masks:
            instance_ids = masks["instance_ids"].astype("<i4")
        if len(instance_ids) != len(vertex):
            raise ValueError("S3 masks have a different vertex count from S1 mesh")
    else:
        instance_ids = np.full(len(vertex), -1, dtype="<i4")
    target.mkdir(parents=True, exist_ok=True)
    partial = target / "mesh.bin.partial"
    with partial.open("wb") as output:
        output.write(struct.pack("<4sIII", b"S3DM", 1, len(vertex), len(indices)))
        output.write(xyz.tobytes())
        output.write(color.tobytes())
        output.write(indices.tobytes())
        output.write(instance_ids.tobytes())
    partial.replace(target / "mesh.bin")


def run_instances(scene_id: str) -> dict:
    target = artifact_dir(scene_id, "S3")
    if (target / "masks.npz").is_file():
        return json.loads((target / "masks.json").read_text())
    mesh = artifact_dir(scene_id, "S1") / "mesh/vh_clean_2.ply"
    target.mkdir(parents=True, exist_ok=True)
    url = os.getenv("S3D_MASK3D_URL", "http://mask3d:9000").rstrip("/") + "/run"
    remote_root = PurePosixPath(os.getenv("S3D_MASK3D_DATA_DIR", "/data"))
    remote_mesh = remote_root.joinpath(*mesh.relative_to(data_root()).parts).as_posix()
    remote_output = remote_root.joinpath(*(target / "masks.npz").relative_to(data_root()).parts).as_posix()
    payload = json.dumps({"mesh": remote_mesh, "output": remote_output,
                          "voxel_m": float(os.getenv("S3D_MASK3D_VOXEL", "0.03"))}).encode()
    with GPU.reserve(3500, timeout=120, unload=unload_llm), VramMeter() as meter:
        request = urllib.request.Request(url, payload, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=1200) as response:
                report = json.load(response)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Mask3D failed: {detail[-3000:]}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError("Mask3D is unavailable. Start its service and retry the Scene job.") from exc
    if not (target / "masks.npz").is_file():
        raise RuntimeError("Mask3D did not create masks.npz")
    return {**report, **meter.report()}


def unload_llm() -> None:
    try:
        LlmRouter().unload_all()
    except urllib.error.URLError as exc:
        raise RuntimeError("Cannot confirm LLM unloading. Start the llm service and retry the Scene job.") from exc


def run_module(module: str, *arguments: str, environment: dict | None = None) -> None:
    result = subprocess.run([sys.executable, "-m", module, *arguments],
                            capture_output=True, text=True, timeout=1200, check=False,
                            env={**os.environ, **(environment or {})})
    if result.returncode:
        raise RuntimeError(result.stderr[-3000:] or f"{module} exited {result.returncode}")


def run_geometry(scene_id: str) -> dict:
    target = artifact_dir(scene_id, "S2")
    if all((target / filename).is_file() for filename in ("geometry.npz", "structures.json", "metrics.json")):
        return json.loads((target / "metrics.json").read_text())
    with GPU.reserve(512, timeout=120, unload=unload_llm), VramMeter() as meter:
        run_module("s3d_app.geometry", scene_id)
    return {**json.loads((target / "metrics.json").read_text()), **meter.report()}


def run_semantics(scene_id: str, kind: str) -> dict:
    target = artifact_dir(scene_id, "S4")
    metric = target / ("labels.complete" if kind == "labels" else "embeddings.metrics.json")
    complete = target / ("labels.complete" if kind == "labels" else "embeddings.npz")
    if complete.is_file() and metric.is_file():
        return json.loads(metric.read_text())
    with (GPU.reserve(2300 if kind == "labels" else 1400, timeout=120, unload=unload_llm),
          VramMeter() as meter):
        for image_size in (640, 480, 320):
            try:
                run_module("s3d_app.semantics", kind, scene_id,
                           environment={"S3D_IMAGE_SIZE": str(image_size)})
                break
            except RuntimeError as exc:
                if "out of memory" not in str(exc).lower() or image_size == 320:
                    raise
    return {**json.loads(metric.read_text()), "image_size": image_size, **meter.report()}


def stage_actions(scene_id: str, package: Path):
    actions = [("S1", lambda: run_module("s3d_app.pipeline", "load", scene_id, str(package))),
                          ("S2", lambda: run_geometry(scene_id)),
                          ("S3", lambda: run_instances(scene_id)),
                          ("S4a", lambda: run_semantics(scene_id, "labels")),
                          ("S4b", lambda: run_semantics(scene_id, "embeddings")),
                          ("S5", lambda: run_module("s3d_app.graph_stage", scene_id)),
               ("S6", lambda: run_module("s3d_app.pipeline", "publish", scene_id))]
    count = min(20, max(0, int(os.getenv("S3D_CAPTIONS_TOP_N", "0"))))
    if count:
        actions.insert(5, ("S4c", lambda: precaption(scene_id, count)))
    return actions


def precaption(scene_id: str, count: int) -> None:
    from s3d_app.vision import caption

    with database() as connection:
        objects = [json.loads(row["data"]) for row in connection.execute(
            "SELECT data FROM objects WHERE scene_id = ?", (scene_id,))]
    for item in sorted(objects, key=lambda node: node["vertices"], reverse=True)[:count]:
        caption(scene_id, item, LlmRouter())


def process_job(job_id: int, scene_id: str, package: Path) -> None:
    for stage, action in stage_actions(scene_id, package):
        started = time.monotonic()
        with database() as connection:
            connection.execute("UPDATE jobs SET status = 'running', stage = ? WHERE id = ?",
                               (stage, job_id))
            connection.execute("UPDATE scenes SET status = 'processing' WHERE id = ?", (scene_id,))
        try:
            result = action()
        except Exception as exc:  # noqa: BLE001 - a failed stage must be persisted for the UI
            with database() as connection:
                connection.execute("UPDATE jobs SET status = 'failed', error = ? WHERE id = ?",
                                   (str(exc), job_id))
                connection.execute("UPDATE scenes SET status = 'failed', error = ? WHERE id = ?",
                                   (str(exc), scene_id))
                connection.execute(
                    "INSERT INTO stage_runs(job_id, stage, status, seconds, error) VALUES (?, ?, ?, ?, ?)",
                    (job_id, stage, "failed", time.monotonic() - started, str(exc)),
                )
            return
        with database() as connection:
            peak = result.get("peak_vram_mb", result.get("peak_torch_reserved_mb")) if isinstance(result, dict) else None
            connection.execute("INSERT INTO stage_runs(job_id, stage, status, seconds, peak_vram_mb, config) "
                               "VALUES (?, ?, ?, ?, ?, ?)",
                               (job_id, stage, "complete", time.monotonic() - started, peak,
                                json.dumps(result) if isinstance(result, dict) else None))
    with database() as connection:
        connection.execute("UPDATE jobs SET status = 'complete', stage = NULL WHERE id = ?", (job_id,))
        connection.execute("UPDATE scenes SET status = 'ready', error = NULL WHERE id = ?",
                           (scene_id,))


def worker() -> None:
    with database() as connection:
        connection.execute("UPDATE jobs SET status = 'queued' WHERE status = 'running'")
    while not STOP.is_set():
        with database() as connection:
            row = connection.execute(
                "SELECT jobs.id, jobs.scene_id, scenes.package_path FROM jobs "
                "JOIN scenes ON scenes.id = jobs.scene_id WHERE jobs.status = 'queued' "
                "ORDER BY jobs.id LIMIT 1"
            ).fetchone()
        if row:
            process_job(row["id"], row["scene_id"], Path(row["package_path"]))
            continue
        WAKE.wait(1)
        WAKE.clear()


def start_worker() -> threading.Thread:
    STOP.clear()
    thread = threading.Thread(target=worker, name="s3d-job-worker", daemon=True)
    thread.start()
    return thread


def stop_worker(thread: threading.Thread) -> None:
    STOP.set()
    WAKE.set()
    thread.join(timeout=5)


if __name__ == "__main__":
    if sys.argv[1] == "load":
        load_package(sys.argv[2], Path(sys.argv[3]))
    elif sys.argv[1] == "publish":
        publish_mesh(sys.argv[2])
