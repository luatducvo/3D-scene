"""Provider-independent remote execution and checksummed workspace synchronization."""
from __future__ import annotations

import hashlib
import time
from pathlib import Path

import httpx

from scene_core.contracts import SceneWorkspace


class ComputeError(RuntimeError):
    code = "COMPUTE_FAILED"


def sha256_file(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


class HttpBackend:
    def __init__(self, data_dir, target_config, client=None):
        self.data_dir = Path(data_dir)
        self.target = target_config
        headers = dict(target_config.headers)
        if target_config.token:
            headers["X-Compute-Token"] = target_config.token
        self.client = client or httpx.Client(base_url=target_config.url, headers=headers, timeout=29)

    def _call(self, method, path, **kwargs):
        response = self.client.request(method, path, **kwargs)
        if response.is_error:
            try:
                error = response.json()["error"]
                message = error.get("message", str(error))
            except (ValueError, KeyError, TypeError):
                message = f"Compute HTTP {response.status_code}"
            raise ComputeError(message)
        return response

    def _wait_until_ready(self):
        deadline = time.monotonic() + self.target.startup_timeout
        while time.monotonic() < deadline:
            try:
                response = self.client.get("/ping")
                if response.status_code == 200:
                    return
                if 400 <= response.status_code < 500 and response.status_code != 429:
                    raise ComputeError(f"Target rejected readiness request: {response.status_code}")
            except httpx.TransportError:
                pass
            time.sleep(self.target.poll_interval)
        raise ComputeError("Compute target did not become ready before startup timeout")

    def _files(self, scene_id, directories):
        if not directories:
            return []
        files, cursor = [], 0
        while True:
            value = self._call("GET", f"/workspaces/{scene_id}/files", params={"dirs": ",".join(directories), "cursor": cursor}).json()
            files.extend(value["files"])
            cursor = value.get("next_cursor")
            if cursor is None:
                return files

    def _sync_up(self, scene_id, directories):
        workspace = SceneWorkspace(self.data_dir, scene_id)
        remote = {item["path"]: item["sha256"] for item in self._files(scene_id, directories)}
        for directory in directories:
            for path in sorted(workspace.path(directory).rglob("*")):
                if not path.is_file():
                    continue
                relative = path.relative_to(workspace.root).as_posix()
                workspace.path(relative)  # reject escaping symlinks
                digest, size = sha256_file(path), path.stat().st_size
                if remote.get(relative) == digest:
                    continue
                with path.open("rb") as stream:
                    offset = 0
                    while True:
                        chunk = stream.read(self.target.chunk_size)
                        self._call("PUT", f"/workspaces/{scene_id}/files/{relative}", params={"offset": offset, "total": size, "sha256": digest}, content=chunk)
                        offset += len(chunk)
                        if offset == size:
                            break

    def _sync_down(self, scene_id, directories):
        workspace = SceneWorkspace(self.data_dir, scene_id)
        remote_files = self._files(scene_id, directories)
        expected = set()
        for item in remote_files:
            relative = item["path"]
            if not any(relative.startswith(directory + "/") for directory in directories):
                raise ComputeError("Target returned a file outside declared outputs")
            path = workspace.path(relative)
            expected.add(path)
            if path.exists() and sha256_file(path) == item["sha256"]:
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(path.name + ".download")
            try:
                with temporary.open("wb") as stream:
                    for offset in range(0, item["size"], self.target.chunk_size):
                        end = min(offset + self.target.chunk_size, item["size"]) - 1
                        response = self._call("GET", f"/workspaces/{scene_id}/files/{relative}", headers={"Range": f"bytes={offset}-{end}"})
                        if len(response.content) != end - offset + 1:
                            raise ComputeError("Target returned an incorrect range length")
                        stream.write(response.content)
                if sha256_file(temporary) != item["sha256"]:
                    raise ComputeError("Downloaded file checksum differs")
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)
        # Remove stale outputs only after every new output has been verified.
        for directory in directories:
            for path in workspace.path(directory).rglob("*"):
                if path.is_file() and path not in expected:
                    path.unlink()

    def run(self, algorithm, scene_id, params, reads, writes):
        self._wait_until_ready()
        if not self.target.shared_storage:
            self._sync_up(scene_id, reads)
        run_id = self._call("POST", "/runs", json={"algorithm": algorithm, "scene_id": scene_id, "params": params}).json()["run_id"]
        deadline = time.monotonic() + 6 * 60 * 60
        while time.monotonic() < deadline:
            result = self._call("GET", f"/runs/{run_id}").json()
            if result["state"] == "failed":
                error = result.get("error", "Compute Run failed")
                raise ComputeError(error.get("message", str(error)) if isinstance(error, dict) else error)
            if result["state"] == "done":
                if not self.target.shared_storage:
                    self._sync_down(scene_id, writes)
                return result["manifest"]
            time.sleep(self.target.poll_interval)
        raise ComputeError("Compute Run exceeded six-hour execution limit")

    def invoke(self, algorithm, method, payload):
        self._wait_until_ready()
        return self._call("POST", f"/invoke/{algorithm}/{method}", json=payload).json()

    def delete_workspace(self, scene_id):
        if not self.target.shared_storage:
            self._call("DELETE", f"/workspaces/{scene_id}")

    def close(self):
        self.client.close()
