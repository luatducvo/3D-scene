import json
import logging
import os
import re
import shutil
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import BackgroundTasks, FastAPI, File, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from scene_core.contracts import STAGES, SceneWorkspace
from scene_core.domain import SceneObject
from scene_core.errors import SceneError
from scene_core.results import EMBEDDING_DIM, SceneResults
from scene_store import SceneStore
from scene_target import delete_quietly, open_target_workspace

from .models import (
    JobCreated,
    SceneCreate,
    SceneCreated,
    SceneDetail,
    SceneSummary,
    SearchHit,
    UploadResult,
)

QUERY_READY_TIMEOUT_S = 10
# GET /search keeps Objects whose similarity is within SEARCH_MARGIN of the best one, SEARCH_MAX_HITS in all.
SEARCH_MARGIN = 0.05
SEARCH_MAX_HITS = 10


def label_matches(obj, query):
    """The query contains the Object's label, or the reverse."""
    query, label = query.lower(), obj["label"].lower()
    return query in label or label in query


def _best_first(hits):
    return sorted(hits, key=lambda hit: hit["score"], reverse=True)


def rank_search_hits(objects, similarities, query, margin, limit=SEARCH_MAX_HITS):
    """The GET /search cut: every label match, then the other Objects within `margin` of the best
    similarity, best first, while fewer than `limit` hits are kept. A label match scores its
    similarity plus 1."""
    best = max(similarities.values(), default=0.0)
    labelled, similar = [], []
    for obj in objects:
        similarity = similarities.get(obj["id"], 0.0)
        if label_matches(obj, query):
            labelled.append({"object": obj, "score": similarity + 1, "raw_similarity": similarity})
        elif similarity > 0 and similarity >= best - margin:
            similar.append({"object": obj, "score": similarity, "raw_similarity": similarity})
    return _best_first(labelled) + _best_first(similar)[: max(0, limit - len(labelled))]


def create_app(database_url=None, data_dir=None, pipeline=None, compute=None, target=None):
    """target replaces the TargetWorkspace built from pipeline and compute, for tests."""
    # SOLID review (SRP): composition, HTTP routes, read SQL, upload coordination and search
    # ranking live here. Extract the use cases behind small interfaces as these change;
    # keep HTTP validation/serialization here and transactional writes in SceneStore.
    store = SceneStore(
        database_url or os.getenv("DATABASE_URL", "postgresql://scene:scene@localhost:5432/scene")
    )
    data_dir = Path(data_dir or os.getenv("DATA_DIR", "data"))

    app = FastAPI(title="Scene Understanding API", version="1.0.0")
    app.state.store = store
    app.state.data_dir = data_dir
    app.state.target = target
    app.state.search_margin = float(os.getenv("SEARCH_MARGIN", SEARCH_MARGIN))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(SceneError)
    async def scene_error(request, exc):
        return JSONResponse(
            {"error": {"code": exc.code, "message": exc.message}}, status_code=exc.status_code
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return JSONResponse(
            {"error": {"code": "INVALID_REQUEST", "message": str(exc)}}, status_code=422
        )

    def summary(row):
        return {**row, "id": str(row["id"])}

    def published(scene):
        return SceneWorkspace(data_dir, str(scene["id"]), scene["publication"])

    def url(request, scene, path):
        """A file URL naming the publication, so a new Job's assets never share a URL with an old one's."""
        if scene["publication"] is None:
            return None
        return str(
            request.url_for(
                "publication_file",
                scene_id=str(scene["id"]),
                version=scene["publication"],
                file_path=path,
            )
        )

    @app.post("/api/v1/scenes", response_model=SceneCreated, status_code=201)
    def create_scene(body: SceneCreate):
        return {"id": store.create_scene(body.name.strip())}

    @app.get("/api/v1/scenes", response_model=list[SceneSummary])
    def list_scenes():
        with store.connect() as conn:
            return [
                summary(s)
                for s in conn.execute("SELECT * FROM scenes ORDER BY created_at DESC").fetchall()
            ]

    @app.get("/api/v1/scenes/{scene_id}", response_model=SceneDetail)
    def get_scene(scene_id: uuid.UUID, request: Request):
        with store.connect() as conn:
            row = store.get_scene(scene_id, conn)
            scene = summary(row)
            stages = conn.execute(
                "SELECT * FROM stage_runs WHERE scene_id=%s", (scene_id,)
            ).fetchall()
        scene["stage_runs"] = sorted(stages, key=lambda s: STAGES.index(s["stage"]))
        assets = SceneResults(published(row)).assets() if row["publication"] else {}
        scene["assets"] = {f"{key}_url": url(request, row, path) for key, path in assets.items()}
        scene["ingest_report"] = next(
            (s["manifest"] for s in stages if s["stage"] == "ingest"), None
        )
        return scene

    @app.delete("/api/v1/scenes/{scene_id}", status_code=204)
    def delete_scene(scene_id: uuid.UUID, background: BackgroundTasks):
        store.delete_scene(scene_id)
        shutil.rmtree(SceneWorkspace(data_dir, str(scene_id)).root, ignore_errors=True)
        try:
            background.add_task(delete_quietly, target_workspace(), str(scene_id))
        except SceneError:
            logging.exception("Scene %s has no Target Workspace to delete", scene_id)
        return Response(status_code=204)

    @app.get(
        "/api/v1/scenes/{scene_id}/publications/{version}/files/{file_path:path}",
        name="publication_file",
    )
    def publication_file(scene_id: uuid.UUID, version: str, file_path: str):
        """A public file of one publication; an older publication stays readable until it is removed."""
        store.get_scene(scene_id)
        try:
            # A publication is identified by its Job UUID; flat result folders are not served.
            uuid.UUID(version)
            workspace = SceneWorkspace(data_dir, str(scene_id), version)
        except ValueError:
            raise SceneError("FILE_NOT_FOUND", "File not found", 404) from None
        return FileResponse(SceneResults(workspace).public_file(file_path))

    @app.post("/api/v1/scenes/{scene_id}/uploads", response_model=UploadResult)
    def upload_files(scene_id: uuid.UUID, files: Annotated[list[UploadFile], File()]):
        with store.uploading(scene_id):
            if not files:
                raise SceneError("INVALID_UPLOAD", "No files supplied", 400)
            allowed = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".mp4", ".mov", ".mkv", ".webm"}
            for upload in files:
                if Path(upload.filename or "").suffix.lower() not in allowed or not (
                    upload.content_type or ""
                ).startswith(("image/", "video/")):
                    raise SceneError(
                        "UNSUPPORTED_MEDIA", "Only photos or a video are accepted", 415
                    )
            target = target_workspace()
            video_ext = {".mp4", ".mov", ".mkv", ".webm"}
            existing = [Path(name) for name in target.list_inputs(str(scene_id))]
            is_video = any(Path(u.filename).suffix.lower() in video_ext for u in files)
            if (is_video and (len(files) != 1 or existing)) or any(
                f.suffix.lower() in video_ext for f in existing
            ):
                raise SceneError(
                    "INVALID_UPLOAD", "Upload photos or one video, without mixing them", 400
                )
            named = {}
            for upload in files:
                # The original stem keeps capture order for ingest; the suffix keeps names unique.
                stem = re.sub(r"[^A-Za-z0-9_-]", "_", Path(upload.filename).stem)[:80]
                name = f"{stem}-{uuid.uuid4().hex[:8]}{Path(upload.filename).suffix.lower()}"
                named[name] = upload.file
            try:
                target.put_inputs(str(scene_id), named)
            except Exception:
                # Files upload concurrently, so any of them may already be stored.
                try:
                    target.remove_inputs(str(scene_id), list(named))
                except Exception:
                    logging.exception("Could not remove partial upload of Scene %s", scene_id)
                raise
            return {"filenames": list(named)}

    @app.post("/api/v1/scenes/{scene_id}/process", response_model=JobCreated, status_code=202)
    def process_scene(scene_id: uuid.UUID):
        return {"job_id": store.enqueue(scene_id)}

    def public_objects(scene_id):
        with store.connect() as conn:
            store.get_scene(scene_id, conn)
            return conn.execute(
                "SELECT id,label,box,attributes,best_views FROM objects WHERE scene_id=%s ORDER BY id",
                (scene_id,),
            ).fetchall()

    @app.get("/api/v1/scenes/{scene_id}/objects", response_model=list[SceneObject])
    def list_objects(scene_id: uuid.UUID):
        return public_objects(scene_id)

    @app.get("/api/v1/scenes/{scene_id}/objects/{object_id}", response_model=SceneObject)
    def get_object(scene_id: uuid.UUID, object_id: str):
        found = next((obj for obj in public_objects(scene_id) if obj["id"] == object_id), None)
        if found is None:
            raise SceneError("OBJECT_NOT_FOUND", "Object not found", 404)
        return found

    @app.get("/api/v1/scenes/{scene_id}/events", response_class=StreamingResponse)
    def events(scene_id: uuid.UUID):
        store.get_scene(scene_id)

        def stream():
            # Replay and live events have the same shapes; only live ones carry an id.
            snapshot = store.snapshot(scene_id)
            cursor = snapshot.cursor
            for event, data in snapshot.events:
                yield f"event: {event}\ndata: " + json.dumps({"type": event, **data}) + "\n\n"
            if snapshot.status != "processing":
                return
            import time

            while True:
                for event_id, event, data in store.events_since(scene_id, cursor):
                    cursor = event_id
                    yield (
                        f"id: {cursor}\nevent: {event}\ndata: "
                        + json.dumps({"type": event, **data})
                        + "\n\n"
                    )
                    if event == "status" and data["status"] in ("ready", "failed"):
                        return
                time.sleep(0.2)

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    def target_workspace():
        """Uploads and query embedding live on the pipeline's Target; built once, on first use."""
        if app.state.target is None:
            # A request waits briefly for a cold Target instead of a Job's full startup deadline.
            try:
                app.state.target = open_target_workspace(
                    data_dir, pipeline, compute, QUERY_READY_TIMEOUT_S
                )
            except ValueError as exc:
                raise SceneError("COMPUTE_UNAVAILABLE", str(exc), 503) from exc
        return app.state.target

    @app.get("/api/v1/scenes/{scene_id}/search", response_model=list[SearchHit])
    def search_objects(scene_id: uuid.UUID, q: str):
        if not q.strip():
            return []
        return rank_search_hits(
            public_objects(scene_id), similarities(scene_id, q), q, app.state.search_margin
        )

    def similarities(scene_id, q):
        """Cosine similarity of the query embedding, made on the Target, to each Object's."""
        import numpy as np

        vector = target_workspace().embed_text([q])[0]
        if len(vector) != EMBEDDING_DIM:
            raise SceneError(
                "EMBEDDING_DIMENSION_MISMATCH", "Query vector dimension differs from database", 500
            )
        scores = {}
        if np.linalg.norm(vector) > 0:
            with store.connect() as conn:
                for row in conn.execute(
                    "SELECT id,1-(embedding <=> %s::vector) AS score FROM objects WHERE scene_id=%s",
                    (str(vector), scene_id),
                ).fetchall():
                    scores[row["id"]] = float(row["score"] or 0)
        return scores

    return app


app = create_app()
