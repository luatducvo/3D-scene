"""Workspace file operations when the Target works on this machine's DATA_DIR."""
from __future__ import annotations

import shutil
from pathlib import Path

from scene_core.contracts import SceneWorkspace


class LocalFiles:
    def __init__(self, data_dir):
        self.data_dir = Path(data_dir)

    def put_file(self, scene_id, relative, stream):
        path = SceneWorkspace(self.data_dir, scene_id).path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as destination:
            shutil.copyfileobj(stream, destination, length=1024 * 1024)

    def list_files(self, scene_id, directory):
        root = SceneWorkspace(self.data_dir, scene_id)
        return sorted(p.relative_to(root.root).as_posix() for p in root.path(directory).rglob("*") if p.is_file())

    def clear(self, scene_id, paths):
        workspace = SceneWorkspace(self.data_dir, scene_id)
        for relative in paths:
            path = workspace.path(relative)
            if path.is_file():
                path.unlink()
            shutil.rmtree(path, ignore_errors=True)

    def fetch(self, scene_id, directories, staging_dir):
        """Results already sit in local Scene storage."""
        return SceneWorkspace(self.data_dir, scene_id)
