"""Small HTTP compute contract; algorithms never see transport or provider APIs."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import re
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field


class ContractError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code, self.message, self.status = code, message, status


def digest_file(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def safe_path(root: Path, relative: str) -> Path:
    if not relative or "\\" in relative or ":" in relative:
        raise ContractError("INVALID_PATH", "Expected a relative workspace path")
    parts = relative.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise ContractError("INVALID_PATH", "Invalid workspace path")
    result = (root / relative).resolve()
    if not result.is_relative_to(root.resolve()):
        raise ContractError("INVALID_PATH", "Path escapes workspace")
    return result


class ComputeRequest(BaseModel):
    algorithm: str
    scene_id: str
    params: dict = Field(default_factory=dict)


def create_app(data_dir: Path | str | None = None, *, token: str | None = None,
               chunk_bytes: int | None = None, executor=None) -> FastAPI:
    root = Path(data_dir or os.environ.get("DATA_DIR", "data")).resolve()
    auth_token = token if token is not None else os.environ.get("COMPUTE_TOKEN", "")
    limit = chunk_bytes or int(float(os.environ.get("CHUNK_SIZE_MB", "25")) * 1_000_000)
    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="compute")
    runs: dict[str, dict] = {}
    lock = threading.RLock()
    runtime = executor

    def get_executor():
        nonlocal runtime
        if runtime is None:
            from scene_core.executor import Executor
            runtime = Executor(root)
        return runtime

    def workspace(scene_id):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", scene_id):
            raise ContractError("INVALID_PATH", "Invalid scene id")
        return safe_path(root, f"scenes/{scene_id}")

    def record(run_id, value):
        runs[run_id] = value
        directory = root / "runs"
        directory.mkdir(parents=True, exist_ok=True)
        temporary = directory / f"{run_id}.tmp"
        temporary.write_text(json.dumps(value), encoding="utf-8")
        temporary.replace(directory / f"{run_id}.json")

    def execute(run_id, body):
        with lock:
            record(run_id, {**runs[run_id], "state": "running"})
        try:
            manifest = get_executor().run(body.algorithm, body.scene_id, body.params)
            result = {"state": "done", "manifest": manifest}
        except Exception as exc:
            result = {"state": "failed", "error": {"code": getattr(exc, "code", "COMPUTE_FAILED"), "message": str(exc)}}
        with lock:
            record(run_id, {**runs[run_id], **result})

    @asynccontextmanager
    async def lifespan(app):
        # An interrupted process cannot resume model execution. Never leave stale running records.
        for path in (root / "runs").glob("*.json"):
            value = json.loads(path.read_text(encoding="utf-8"))
            if value["state"] in ("queued", "running"):
                value.update(state="failed", error={"code": "COMPUTE_INTERRUPTED", "message": "Compute process restarted"})
            record(path.stem, value)
        yield
        pool.shutdown(wait=False, cancel_futures=True)

    app = FastAPI(title="Scene Compute", version="0.1.0", lifespan=lifespan)

    @app.exception_handler(ContractError)
    async def error_handler(request, exc):
        return JSONResponse({"error": {"code": exc.code, "message": exc.message}}, status_code=exc.status)

    @app.middleware("http")
    async def bounds(request: Request, call_next):
        if auth_token and request.url.path != "/ping" and not hmac.compare_digest(request.headers.get("X-Compute-Token", ""), auth_token):
            return JSONResponse({"error": {"code": "UNAUTHORIZED", "message": "Invalid compute token"}}, status_code=401)
        # Bound input including chunked HTTP requests before FastAPI parses JSON or a body.
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > limit:
                return JSONResponse({"error": {"code": "BODY_TOO_LARGE", "message": "Use smaller chunks"}}, status_code=413)
        request._body = bytes(body)
        try:
            return await asyncio.wait_for(call_next(request), timeout=29)
        except TimeoutError:
            return JSONResponse({"error": {"code": "REQUEST_TIMEOUT", "message": "Use asynchronous Compute Runs for long work"}}, status_code=504)

    @app.get("/ping")
    def ping():
        return {"ready": True}

    @app.get("/info")
    def info():
        from importlib.metadata import entry_points
        return {"version": os.environ.get("IMAGE_VERSION", "0.1.0"),
                "gpu": os.environ.get("GPU_NAME"),
                "algorithms": sorted(ep.name for ep in entry_points(group="scene_stages"))}

    @app.get("/workspaces/{scene_id}/files")
    def list_files(scene_id: str, dirs: str = "", cursor: int = 0):
        scene_root = workspace(scene_id)
        folders = [safe_path(scene_root, part) for part in dirs.split(",") if part] or [scene_root]
        paths = sorted({p for folder in folders for p in folder.rglob("*") if p.is_file() and not p.name.endswith(".part")})
        result = []
        next_cursor = None
        if cursor < 0:
            raise ContractError("INVALID_CURSOR", "Cursor must be nonnegative")
        for index, path in enumerate(paths[cursor:], start=cursor):
            safe_path(scene_root, path.relative_to(scene_root).as_posix())
            item = {"path": path.relative_to(scene_root).as_posix(), "size": path.stat().st_size, "sha256": digest_file(path)}
            if len(json.dumps({"files": result + [item], "next_cursor": index + 1}).encode()) > limit:
                if not result:
                    raise ContractError("BODY_TOO_LARGE", "File metadata exceeds chunk size", 413)
                next_cursor = index
                break
            result.append(item)
        return {"files": result, "next_cursor": next_cursor}

    @app.put("/workspaces/{scene_id}/files/{path:path}")
    async def upload(scene_id: str, path: str, request: Request, total: int, sha256: str, offset: int = 0):
        destination = safe_path(workspace(scene_id), path)
        data = await request.body()
        if offset < 0 or total < 0 or offset + len(data) > total or not re.fullmatch(r"[0-9a-f]{64}", sha256):
            raise ContractError("INVALID_CHUNK", "Invalid offset, total or SHA-256")
        partial = destination.with_name(destination.name + ".part")
        with lock:
            if any(r["scene_id"] == scene_id and r["state"] in ("queued", "running") for r in runs.values()):
                raise ContractError("WORKSPACE_BUSY", "Workspace has an active Compute Run", 409)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if offset == 0:
                partial.write_bytes(b"")
            if not partial.exists() or partial.stat().st_size != offset:
                raise ContractError("INVALID_OFFSET", "Chunk does not follow the previous chunk", 409)
            with partial.open("ab") as stream:
                stream.write(data)
            complete = offset + len(data) == total
            if complete:
                if digest_file(partial) != sha256:
                    partial.unlink()
                    raise ContractError("CHECKSUM_MISMATCH", "Uploaded file checksum differs", 422)
                partial.replace(destination)
        return {"complete": complete, "offset": offset + len(data)}

    @app.get("/workspaces/{scene_id}/files/{path:path}")
    def download(scene_id: str, path: str, request: Request):
        source = safe_path(workspace(scene_id), path)
        if not source.is_file() or source.name.endswith(".part"):
            raise ContractError("FILE_NOT_FOUND", "File not found", 404)
        size = source.stat().st_size
        start, end = 0, size - 1
        range_header = request.headers.get("range")
        if range_header:
            match = re.fullmatch(r"bytes=(\d+)-(\d*)", range_header)
            if not match:
                raise ContractError("INVALID_RANGE", "Expected bytes=start-end", 416)
            start, end = int(match[1]), min(int(match[2]) if match[2] else size - 1, size - 1)
            if start > end or start >= size:
                raise ContractError("INVALID_RANGE", "Range outside file", 416)
        if end - start + 1 > limit:
            raise ContractError("BODY_TOO_LARGE", "Use a bounded Range header", 413)
        with source.open("rb") as stream:
            stream.seek(start)
            data = stream.read(max(0, end - start + 1))
        headers = {"Accept-Ranges": "bytes"}
        if range_header:
            headers["Content-Range"] = f"bytes {start}-{end}/{size}"
        return Response(data, status_code=206 if range_header else 200, headers=headers, media_type="application/octet-stream")

    @app.delete("/workspaces/{scene_id}", status_code=204)
    def delete_workspace(scene_id: str):
        scene_root = workspace(scene_id)
        with lock:
            if any(r["scene_id"] == scene_id and r["state"] in ("queued", "running") for r in runs.values()):
                raise ContractError("WORKSPACE_BUSY", "Workspace has an active Compute Run", 409)
            if scene_root.exists():
                shutil.rmtree(scene_root)

    @app.post("/runs", status_code=202)
    def start_run(body: ComputeRequest):
        workspace(body.scene_id)
        with lock:
            if any(r["scene_id"] == body.scene_id and r["state"] in ("queued", "running") for r in runs.values()):
                raise ContractError("WORKSPACE_BUSY", "Workspace has an active Compute Run", 409)
            run_id = str(uuid4())
            record(run_id, {"state": "queued", "scene_id": body.scene_id})
            pool.submit(execute, run_id, body)
        return {"run_id": run_id}

    @app.get("/runs/{run_id}")
    def get_run(run_id: str):
        with lock:
            if run_id not in runs:
                raise ContractError("COMPUTE_RUN_NOT_FOUND", "Compute Run not found", 404)
            result = runs[run_id]
            if len(json.dumps(result).encode()) > limit:
                raise ContractError("BODY_TOO_LARGE", "Manifest exceeds response limit", 413)
            return result

    @app.post("/invoke/{algorithm}/{method}")
    async def invoke(algorithm: str, method: str, payload: dict):
        if method != "embed_text":
            raise ContractError("UNKNOWN_METHOD", "Only embed_text is supported", 404)
        # Share the same queue as Stage execution so GPU model caches are not accessed concurrently.
        future = pool.submit(get_executor().invoke, algorithm, method, payload)
        try:
            result = await asyncio.wait_for(asyncio.wrap_future(future), timeout=28)
        except TimeoutError:
            future.cancel()
            raise ContractError("REQUEST_TIMEOUT", "Embedding invocation exceeded time limit", 504)
        if len(json.dumps(result).encode()) > limit:
            raise ContractError("BODY_TOO_LARGE", "Embedding response exceeds chunk limit", 413)
        return result

    return app


app = create_app()
