"""In-process adapter: Algorithms run in this process on a Target Workspace under DATA_DIR/target."""

import shutil
from pathlib import Path

from scene_core.contracts import SceneWorkspace
from scene_core.executor import Executor


class InProcessAdapter:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.executor = Executor(self.root)

    def _workspace(self, scene_id):
        return SceneWorkspace(self.root, scene_id)

    def put(self, scene_id, files):
        for relative, stream in files.items():
            path = self._workspace(scene_id).path(relative)
            path.parent.mkdir(parents=True, exist_ok=True)
            stream.seek(0)
            with path.open("wb") as destination:
                shutil.copyfileobj(stream, destination, length=1024 * 1024)

    def list(self, scene_id, directory):
        workspace = self._workspace(scene_id)
        return sorted(
            p.relative_to(workspace.root).as_posix()
            for p in workspace.path(directory).rglob("*")
            if p.is_file()
        )

    def clear(self, scene_id, paths):
        workspace = self._workspace(scene_id)
        for relative in paths:
            path = workspace.path(relative)
            if path.is_file():
                path.unlink()
            shutil.rmtree(path, ignore_errors=True)

    def run(self, algorithm, scene_id, params, on_progress=None):
        return self.executor.run(algorithm, scene_id, params, on_progress)

    def download(self, scene_id, directories, staging: SceneWorkspace):
        """Copy the directories into the staging Workspace, as the HTTP adapter downloads them."""
        source = self._workspace(scene_id)
        for directory in directories:
            if source.path(directory).is_dir():
                shutil.copytree(source.path(directory), staging.path(directory))
        staging.root.mkdir(parents=True, exist_ok=True)

    def embed(self, algorithm, texts):
        return self.executor.invoke(algorithm, "embed_text", {"texts": texts})["vectors"]

    def delete(self, scene_id):
        shutil.rmtree(self._workspace(scene_id).root, ignore_errors=True)

    def close(self):
        pass
