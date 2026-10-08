"""HTTP API and static web entry point."""

import asyncio
import errno
import hashlib
import json
import os
import shutil
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict

from s3d_app.ask import answer_events
from s3d_app.packages import InvalidPackage, verify_package
from s3d_app.pipeline import STAGES, WAKE, artifact_dir, start_worker, stop_worker
from s3d_app.storage import data_root, database, inbox_root


@asynccontextmanager
async def lifespan(_app: FastAPI):
    thread = start_worker()
    yield
    stop_worker(thread)


app = FastAPI(title="S3D", version="0.1.0", lifespan=lifespan)


@app.exception_handler(OSError)
async def storage_error(_request, exception: OSError) -> JSONResponse:
    exhausted = exception.errno == errno.ENOSPC
    return JSONResponse(status_code=507 if exhausted else 500, content={"detail":
        "The data disk is full. Free disk space and retry." if exhausted else
        f"Storage operation failed: {exception}"})

if os.getenv("S3D_DEV") == "1":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.get("/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/inbox")
def list_inbox() -> list[str]:
    root = inbox_root()
    if not root.is_dir():
        return []
    return sorted(path.name for path in root.glob("*.s3dpkg") if path.is_file())


@app.get("/v1/scenes")
def list_scenes() -> list[dict]:
    with database() as connection:
        return [dict(row) for row in connection.execute("SELECT * FROM scenes ORDER BY id")]


@app.get("/v1/scenes/{scene_id}")
def get_scene(scene_id: str) -> dict:
    with database() as connection:
        row = connection.execute("SELECT * FROM scenes WHERE id = ?", (scene_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Scene not found")
    return dict(row)


@app.get("/v1/scenes/{scene_id}/events")
async def scene_events(scene_id: str) -> StreamingResponse:
    async def stream():
        previous = None
        while True:
            with database() as connection:
                row = connection.execute(
                    "SELECT status, stage, error FROM jobs WHERE scene_id = ? ORDER BY id DESC LIMIT 1",
                    (scene_id,),
                ).fetchone()
            if row is None:
                yield 'event: error\ndata: {"error":"Job not found"}\n\n'
                return
            payload = dict(row)
            if payload != previous:
                yield f"event: progress\ndata: {json.dumps(payload)}\n\n"
                previous = payload
            if payload["status"] in {"complete", "failed"}:
                return
            await asyncio.sleep(0.5)
    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/v1/scenes/{scene_id}/mesh")
def scene_mesh(scene_id: str) -> FileResponse:
    get_scene(scene_id)
    path = artifact_dir(scene_id, "S6") / "mesh.bin"
    if not path.is_file():
        raise HTTPException(404, "Mesh is not ready")
    return FileResponse(path, media_type="application/octet-stream")


@app.get("/v1/scenes/{scene_id}/structures")
def scene_structures(scene_id: str) -> list[dict]:
    get_scene(scene_id)
    path = artifact_dir(scene_id, "S2") / "structures.json"
    if not path.is_file():
        raise HTTPException(404, "Structures are not ready")
    return json.loads(path.read_text())


@app.get("/v1/scenes/{scene_id}/objects")
def scene_objects(scene_id: str, label: str | None = None) -> list[dict]:
    get_scene(scene_id)
    with database() as connection:
        rows = [json.loads(row["data"]) for row in connection.execute(
            "SELECT data FROM objects WHERE scene_id = ? ORDER BY id", (scene_id,))]
    if label:
        rows = [item for item in rows if label.casefold() in item["label"].casefold()]
    return rows


@app.get("/v1/scenes/{scene_id}/objects/{object_id}/mask")
def object_mask(scene_id: str, object_id: int) -> dict:
    get_scene(scene_id)
    import numpy as np

    with database() as connection:
        row = connection.execute("SELECT mask FROM objects WHERE scene_id = ? AND id = ?",
                                 (scene_id, object_id)).fetchone()
        if row is None:
            raise HTTPException(404, "Object not found")
        stored = row["mask"]
        if stored is None:
            path = artifact_dir(scene_id, "S3") / "masks.npz"
            if not path.is_file():
                raise HTTPException(404, "Instance masks are not ready")
            with np.load(path, allow_pickle=False) as masks:
                stored = np.flatnonzero(masks["instance_ids"] == object_id).astype("<i4").tobytes()
            connection.execute("UPDATE objects SET mask = ? WHERE scene_id = ? AND id = ?",
                               (stored, scene_id, object_id))
        vertices = np.frombuffer(stored, dtype="<i4").tolist()
    return {"object_id": object_id, "vertex_indices": vertices}


@app.get("/v1/scenes/{scene_id}/graph")
def scene_graph(scene_id: str) -> dict:
    get_scene(scene_id)
    path = artifact_dir(scene_id, "S5") / "graph.json"
    if not path.is_file():
        raise HTTPException(404, "Scene graph is not ready")
    return json.loads(path.read_text())


class ViewpointRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    position: tuple[float, float, float]
    forward: tuple[float, float, float]


class AskRequest(BaseModel):
    text: str = ""
    program: dict | None = None
    viewpoint: ViewpointRequest | None = None
    session_id: str | None = None
    selected_object_id: int | str | None = None
    choice_id: int | str | None = None


@app.post("/v1/scenes/{scene_id}/ask")
def ask(scene_id: str, request: AskRequest) -> StreamingResponse:
    scene = get_scene(scene_id)
    if scene["status"] != "ready":
        raise HTTPException(409, "Wait for Scene processing to finish before asking questions")

    def stream():
        for event, payload in answer_events(scene_id, request.model_dump()):
            yield f"event: {event}\ndata: {json.dumps(payload)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/v1/scenes/{scene_id}/frames/{frame_id}.jpg")
def frame(scene_id: str, frame_id: int) -> FileResponse:
    get_scene(scene_id)
    if frame_id < 0:
        raise HTTPException(404, "Frame not found")
    path = artifact_dir(scene_id, "S1") / "frames/color" / f"{frame_id:06d}.jpg"
    if not path.is_file():
        raise HTTPException(404, "Frame not found")
    return FileResponse(path, media_type="image/jpeg")


class ReprocessRequest(BaseModel):
    stage: str


@app.post("/v1/scenes/{scene_id}/reprocess")
def reprocess_scene(scene_id: str, request: ReprocessRequest) -> dict:
    if request.stage == "S4":
        request.stage = "S4a"
    if request.stage not in STAGES:
        raise HTTPException(400, f"Supported stages: {', '.join(STAGES)}")
    with database() as connection:
        scene = connection.execute("SELECT id FROM scenes WHERE id = ?", (scene_id,)).fetchone()
        if scene is None:
            raise HTTPException(404, "Scene not found")
        active = connection.execute(
            "SELECT id FROM jobs WHERE scene_id = ? AND status IN ('queued','running')", (scene_id,)
        ).fetchone()
        if active:
            raise HTTPException(409, "Scene has an active job")
        if STAGES.index(request.stage) <= STAGES.index("S4b"):
            connection.execute("DELETE FROM sessions WHERE scene_id = ?", (scene_id,))
        stages = STAGES[STAGES.index(request.stage):]
        if request.stage == "S4c":
            for row in connection.execute("SELECT id,data FROM objects WHERE scene_id = ?", (scene_id,)).fetchall():
                item = json.loads(row["data"])
                item.pop("caption", None)
                connection.execute("UPDATE objects SET data = ? WHERE scene_id = ? AND id = ?",
                                   (json.dumps(item), scene_id, row["id"]))
        for stage in stages:
            if stage == "S4b" and request.stage == "S4b":
                directory = artifact_dir(scene_id, "S4")
                for filename in ("embeddings.npz", "embeddings.metrics.json"):
                    (directory / filename).unlink(missing_ok=True)
                connection.execute("UPDATE objects SET embedding = NULL WHERE scene_id = ?", (scene_id,))
                continue
            directory = artifact_dir(scene_id, "S4" if stage in {"S4a", "S4b"} else stage)
            if directory.exists():
                shutil.rmtree(directory)
        connection.execute("UPDATE scenes SET status = 'imported', error = NULL WHERE id = ?",
                           (scene_id,))
        connection.execute("INSERT INTO jobs(scene_id, status, stage) VALUES (?, 'queued', ?)",
                           (scene_id, request.stage))
    WAKE.set()
    return {"scene_id": scene_id, "status": "queued", "from_stage": request.stage}


@app.delete("/v1/scenes/{scene_id}")
def delete_scene(scene_id: str, delete_package: Annotated[bool, Query()] = False) -> dict:
    with database() as connection:
        scene = connection.execute("SELECT * FROM scenes WHERE id = ?", (scene_id,)).fetchone()
        if scene is None:
            raise HTTPException(404, "Scene not found")
        active = connection.execute(
            "SELECT id FROM jobs WHERE scene_id = ? AND status IN ('queued','running')", (scene_id,)
        ).fetchone()
        if active:
            raise HTTPException(409, "Scene has an active job")
        package = Path(scene["package_path"])
        if not delete_package and package.is_file():
            retained = data_root() / "packages" / f"{scene_id}-{scene['package_sha256']}.s3dpkg"
            retained.parent.mkdir(parents=True, exist_ok=True)
            package.replace(retained)
        job_ids = [row["id"] for row in connection.execute(
            "SELECT id FROM jobs WHERE scene_id = ?", (scene_id,))]
        for job_id in job_ids:
            connection.execute("DELETE FROM stage_runs WHERE job_id = ?", (job_id,))
        connection.execute("DELETE FROM jobs WHERE scene_id = ?", (scene_id,))
        connection.execute("DELETE FROM objects WHERE scene_id = ?", (scene_id,))
        connection.execute("DELETE FROM sessions WHERE scene_id = ?", (scene_id,))
        connection.execute("DELETE FROM queries WHERE scene_id = ?", (scene_id,))
        connection.execute("DELETE FROM scenes WHERE id = ?", (scene_id,))
        directory = data_root() / "scenes" / scene_id
        if directory.exists():
            shutil.rmtree(directory)
    return {"scene_id": scene_id, "status": "deleted", "package_deleted": delete_package}


@app.post("/v1/imports")
def import_package(file: Annotated[UploadFile | None, File()] = None,
                   inbox_name: Annotated[str | None, Form()] = None,
                   replace: Annotated[bool, Form()] = False) -> dict:
    if (file is None) == (inbox_name is None):
        raise HTTPException(400, "Choose one uploaded file or inbox Package")
    if file is not None and Path(file.filename or "").suffix != ".s3dpkg":
        raise HTTPException(400, "The file must end in .s3dpkg")
    if inbox_name is not None:
        source_path = inbox_root() / inbox_name
        if (source_path.name != inbox_name or source_path.suffix != ".s3dpkg"
                or not source_path.is_file()):
            raise HTTPException(400, "Invalid inbox Package name")
    root = data_root()
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=root, suffix=".s3dpkg", delete=False) as temporary:
        candidate = Path(temporary.name)
        if file is not None:
            source = file.file
        else:
            source = source_path.open("rb")
        digest = hashlib.sha256()
        try:
            while block := source.read(1024 * 1024):
                temporary.write(block)
                digest.update(block)
        finally:
            if file is None:
                source.close()
    try:
        manifest = verify_package(candidate)
        scene_id = manifest["scan_id"]
        with database() as connection:
            existing = connection.execute("SELECT * FROM scenes WHERE id = ?", (scene_id,)).fetchone()
            if existing is not None and existing["package_sha256"] == digest.hexdigest():
                return {"scene_id": scene_id, "status": "unchanged"}
            if existing is not None and not replace:
                raise HTTPException(409, "A different Package exists; choose Replace")
            target_dir = root / "scenes" / scene_id
            if existing is not None:
                active = connection.execute("SELECT id FROM jobs WHERE scene_id = ? "
                    "AND status IN ('queued','running')", (scene_id,)).fetchone()
                if active:
                    raise HTTPException(409, "Scene has an active job")
                shutil.rmtree(target_dir, ignore_errors=True)
                connection.execute("DELETE FROM stage_runs WHERE job_id IN "
                    "(SELECT id FROM jobs WHERE scene_id = ?)", (scene_id,))
                connection.execute("DELETE FROM objects WHERE scene_id = ?", (scene_id,))
                connection.execute("DELETE FROM sessions WHERE scene_id = ?", (scene_id,))
                connection.execute("DELETE FROM queries WHERE scene_id = ?", (scene_id,))
                connection.execute("DELETE FROM jobs WHERE scene_id = ?", (scene_id,))
                connection.execute("DELETE FROM scenes WHERE id = ?", (scene_id,))
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / "source.s3dpkg"
            candidate.replace(target)
            connection.execute(
                "INSERT INTO scenes(id, package_sha256, status, package_path) VALUES (?, ?, ?, ?)",
                (scene_id, digest.hexdigest(), "imported", str(target)),
            )
            connection.execute("INSERT INTO jobs(scene_id, status, stage) VALUES (?, ?, ?)",
                               (scene_id, "queued", "S1"))
        WAKE.set()
        return {"scene_id": scene_id, "status": "imported"}
    except InvalidPackage as exc:
        raise HTTPException(400, str(exc)) from exc
    finally:
        candidate.unlink(missing_ok=True)


def web_root() -> Path:
    return Path(os.getenv("S3D_WEB_DIR", Path(__file__).resolve().parents[3] / "frontend" / "out"))


@app.get("/{path:path}", include_in_schema=False)
def static_page(path: str) -> FileResponse:
    root = web_root().resolve()
    candidate = (root / (path or "index.html")).resolve()
    if not candidate.is_relative_to(root):
        raise HTTPException(404)
    if candidate.is_dir():
        candidate = candidate / "index.html"
    if not candidate.is_file() and not Path(path).suffix:
        candidate = root / path / "index.html"
    if not candidate.is_file():
        raise HTTPException(404)
    return FileResponse(candidate)
