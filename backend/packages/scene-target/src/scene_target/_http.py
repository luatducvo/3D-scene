"""HTTP adapter: the scene-compute contract with checksummed, chunked file transfer.

Every failure leaves as a SceneError: an Algorithm's own code and details from a failed Compute Run,
the contract's code for a rejected request, and COMPUTE_UNAVAILABLE when the Target cannot be reached.
"""
from __future__ import annotations

import hashlib
import time

import httpx
from scene_core.contracts import SceneWorkspace
from scene_core.errors import SceneError

RUN_LIMIT_S = 6 * 60 * 60


def sha256_file(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def unavailable(message):
    return SceneError("COMPUTE_UNAVAILABLE", message, 503)


class HttpAdapter:
    def __init__(self, target_config, client=None):
        self.target = target_config
        headers = dict(target_config.headers)
        if target_config.token:
            headers["X-Compute-Token"] = target_config.token
        self.client = client or httpx.Client(base_url=target_config.url, headers=headers, timeout=29)

    def _call(self, method, path, **kwargs):
        try:
            response = self.client.request(method, path, **kwargs)
        except httpx.TransportError as exc:
            raise unavailable(f"The compute Target is unreachable: {exc}") from exc
        if response.is_error:
            try:
                error = response.json()["error"]
                code, message = error.get("code", "COMPUTE_FAILED"), error.get("message", str(error))
            except (ValueError, KeyError, TypeError, AttributeError):
                code, message = "COMPUTE_FAILED", f"Compute HTTP {response.status_code}"
            raise SceneError(code, message, 502)
        return response

    def _wait_until_ready(self):
        deadline = time.monotonic() + self.target.startup_timeout
        while time.monotonic() < deadline:
            try:
                response = self.client.get("/ping")
                if response.status_code == 200:
                    return
                if 400 <= response.status_code < 500 and response.status_code != 429:
                    raise unavailable(f"The compute Target rejected the readiness request: {response.status_code}")
            except httpx.TransportError:
                pass
            time.sleep(self.target.poll_interval)
        raise unavailable("The compute Target did not become ready before its startup timeout")

    def _files(self, scene_id, directories):
        files, cursor = [], 0
        while True:
            value = self._call("GET", f"/workspaces/{scene_id}/files", params={"dirs": ",".join(directories), "cursor": cursor}).json()
            files.extend(value["files"])
            cursor = value.get("next_cursor")
            if cursor is None:
                return files

    def _upload(self, scene_id, relative, stream, digest, size):
        offset = 0
        while True:
            chunk = stream.read(self.target.chunk_size)
            self._call("PUT", f"/workspaces/{scene_id}/files/{relative}", params={"offset": offset, "total": size, "sha256": digest}, content=chunk)
            offset += len(chunk)
            if offset == size:
                break

    def put(self, scene_id, relative, stream):
        self._wait_until_ready()
        stream.seek(0)
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
        size = stream.seek(0, 2)
        stream.seek(0)
        self._upload(scene_id, relative, stream, digest, size)

    def list(self, scene_id, directory):
        self._wait_until_ready()
        return [item["path"] for item in self._files(scene_id, [directory])]

    def clear(self, scene_id, paths):
        self._wait_until_ready()
        self._call("DELETE", f"/workspaces/{scene_id}/files", params={"dirs": ",".join(paths)})

    def run(self, algorithm, scene_id, params, on_progress=None):
        self._wait_until_ready()
        run_id = self._call("POST", "/runs", json={"algorithm": algorithm, "scene_id": scene_id, "params": params}).json()["run_id"]
        deadline = time.monotonic() + RUN_LIMIT_S
        reported = None
        while time.monotonic() < deadline:
            result = self._call("GET", f"/runs/{run_id}").json()
            if on_progress and result.get("progress") and result["progress"] != reported:
                reported = result["progress"]
                on_progress(reported)
            if result["state"] == "failed":
                error = result.get("error") or {}
                if not isinstance(error, dict):
                    error = {"message": str(error)}
                raise SceneError(error.get("code", "COMPUTE_FAILED"), error.get("message", "Compute Run failed"), 502, error.get("details"))
            if result["state"] == "done":
                return result["manifest"]
            time.sleep(self.target.poll_interval)
        raise SceneError("COMPUTE_TIMEOUT", "Compute Run exceeded the six-hour execution limit", 504)

    def download(self, scene_id, directories, staging: SceneWorkspace):
        """Download every file under the directories into the empty staging Workspace, verifying checksums."""
        self._wait_until_ready()
        staging.root.mkdir(parents=True, exist_ok=True)
        for item in self._files(scene_id, directories):
            relative = item["path"]
            if not any(relative.startswith(directory + "/") for directory in directories):
                raise SceneError("COMPUTE_FAILED", "The compute Target returned a file outside the requested directories", 502)
            path = staging.path(relative)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("wb") as stream:
                for offset in range(0, item["size"], self.target.chunk_size):
                    end = min(offset + self.target.chunk_size, item["size"]) - 1
                    response = self._call("GET", f"/workspaces/{scene_id}/files/{relative}", headers={"Range": f"bytes={offset}-{end}"})
                    if len(response.content) != end - offset + 1:
                        raise SceneError("COMPUTE_FAILED", "The compute Target returned an incorrect range length", 502)
                    stream.write(response.content)
            if sha256_file(path) != item["sha256"]:
                raise SceneError("COMPUTE_FAILED", f"Downloaded file {relative} has a different checksum", 502)

    def embed(self, algorithm, texts):
        self._wait_until_ready()
        return self._call("POST", f"/invoke/{algorithm}/embed_text", json={"texts": texts}).json()["vectors"]

    def delete(self, scene_id):
        self._call("DELETE", f"/workspaces/{scene_id}")

    def close(self):
        self.client.close()
