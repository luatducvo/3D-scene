"""Scene Results: the files a finished Job publishes, and the only code that knows their names."""

from dataclasses import dataclass
from typing import ClassVar

import numpy as np
from pydantic import ValidationError

from .contracts import SceneWorkspace
from .domain import SceneGraph
from .errors import SceneError
from .membership import ObjectMembership

# Must equal the objects.embedding column type, vector(1024); a test compares them.
EMBEDDING_DIM = 1024


@dataclass(frozen=True)
class PublishedScene:
    graph: SceneGraph
    embeddings: dict[str, np.ndarray]


class SceneResults:
    """Reads published files from a Workspace root (the Scene's own or a staging copy); files only, no database."""

    # The only Workspace directories that return to the worker: publication inputs and served assets.
    # Frame images stay on the Target.
    DIRECTORIES = ("graph", "embeddings", "mesh")
    GRAPH = "graph/scene_graph.json"
    EMBEDDINGS = "embeddings/objects.npz"
    # Which points and mesh vertices belong to each Object (scene_core.membership); written by graph.
    MEMBERSHIP = "graph/membership.bin"
    # Served to browsers on every Target: a trailing slash names a whole directory, anything else one
    # file. Everything else in a Workspace stays private.
    PUBLIC = ("mesh/", MEMBERSHIP)
    ASSETS: ClassVar[dict[str, str]] = {
        "mesh": "mesh/mesh.glb",
        "points": "mesh/points.ply",
        "membership": MEMBERSHIP,
    }

    def __init__(self, workspace: SceneWorkspace):
        self.workspace = workspace

    def load(self) -> PublishedScene:
        """Read the Scene Graph and Object embeddings, check they agree and that every viewer asset exists, before any transaction opens."""
        try:
            graph = SceneGraph.model_validate_json(
                self.workspace.path(self.GRAPH).read_text(encoding="utf-8")
            )
            with np.load(self.workspace.path(self.EMBEDDINGS), allow_pickle=False) as data:
                ids = [str(key) for key in data["ids"]]
                vectors = np.asarray(data["vectors"])
        except (OSError, KeyError, ValueError, ValidationError) as exc:
            raise SceneError(
                "RESULTS_INVALID", f"Published results are missing or unreadable: {exc}"
            ) from exc
        object_ids = [o.id for o in graph.objects]
        if (
            len(set(ids)) != len(ids)
            or len(set(object_ids)) != len(object_ids)
            or set(ids) != set(object_ids)
        ):
            raise SceneError(
                "RESULTS_INVALID", "Scene Graph Objects and embeddings have different ids"
            )
        if vectors.shape != (len(ids), EMBEDDING_DIM):
            raise SceneError(
                "RESULTS_INVALID",
                f"Embeddings must have shape (objects, {EMBEDDING_DIM}), got {vectors.shape}",
            )
        if not np.isfinite(vectors).all():
            raise SceneError("RESULTS_INVALID", "Embeddings contain non-finite values")
        missing = [path for path in self.ASSETS.values() if not self.workspace.path(path).is_file()]
        if missing:
            raise SceneError(
                "RESULTS_INVALID", f"Published results are missing {', '.join(missing)}"
            )
        self._check_membership(object_ids)
        return PublishedScene(graph, dict(zip(ids, vectors, strict=True)))

    def _check_membership(self, object_ids: list[str]) -> None:
        """The membership file must decode and list the Scene Graph's Objects in order."""
        try:
            membership = ObjectMembership.decode(self.workspace.path(self.MEMBERSHIP).read_bytes())
        except (OSError, ValueError) as exc:
            raise SceneError("RESULTS_INVALID", f"Object membership is unreadable: {exc}") from exc
        if membership.ids != object_ids:
            raise SceneError(
                "RESULTS_INVALID", "Object membership and the Scene Graph list different Objects"
            )

    def assets(self) -> dict[str, str]:
        """Workspace-relative paths of the viewer assets, keyed as ASSETS; load() checked each exists."""
        return dict(self.ASSETS)

    @classmethod
    def is_public(cls, file_path: str) -> bool:
        parts = file_path.split("/")
        if "\\" in file_path or any(p in ("", ".", "..") for p in parts):
            return False
        return any(
            file_path.startswith(public) if public.endswith("/") else file_path == public
            for public in cls.PUBLIC
        )

    def public_file(self, file_path: str):
        """The file behind a public path; a private, malformed or missing path is not found."""
        if not self.is_public(file_path):
            raise SceneError("FILE_NOT_FOUND", "File not found", 404)
        try:
            path = self.workspace.path(file_path)
        except ValueError:
            raise SceneError("FILE_NOT_FOUND", "File not found", 404) from None
        if not path.is_file():
            raise SceneError("FILE_NOT_FOUND", "File not found", 404)
        return path
