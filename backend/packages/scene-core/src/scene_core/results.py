"""Scene Results: the files a finished Job publishes, and the only code that knows their names."""

from dataclasses import dataclass
from typing import ClassVar

import numpy as np
from pydantic import ValidationError

from .contracts import SceneWorkspace
from .domain import DESCRIPTIONS, OBJECT_LIST, SceneObject
from .errors import SceneError
from .membership import ObjectMembership

# Must equal the objects.embedding column type, vector(1024); a test compares them.
EMBEDDING_DIM = 1024


@dataclass(frozen=True)
class PublishedScene:
    objects: list[SceneObject]
    embeddings: dict[str, np.ndarray]
    # Each Object's Description as the text that is embedded and reranked.
    descriptions: dict[str, str]


class SceneResults:
    """Reads published files from a Workspace root (the Scene's own or a staging copy); files only, no database."""

    # The only Workspace directories that return to the worker: publication inputs and served assets.
    # Frame images stay on the Target.
    DIRECTORIES = ("objects", "embeddings", "mesh")
    OBJECTS = "objects/objects.json"
    EMBEDDINGS = "embeddings/objects.npz"
    DESCRIPTIONS = "embeddings/descriptions.json"
    # Which points and mesh vertices belong to each Object (scene_core.membership); written by objects.
    MEMBERSHIP = "objects/membership.bin"
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
        """Read the Objects, their embeddings and Descriptions, check they agree and that every viewer asset exists, before any transaction opens."""
        try:
            objects = OBJECT_LIST.validate_json(
                self.workspace.path(self.OBJECTS).read_text(encoding="utf-8")
            )
            with np.load(self.workspace.path(self.EMBEDDINGS), allow_pickle=False) as data:
                ids = [str(key) for key in data["ids"]]
                vectors = np.asarray(data["vectors"])
            descriptions = DESCRIPTIONS.validate_json(
                self.workspace.path(self.DESCRIPTIONS).read_text(encoding="utf-8")
            )
        except (OSError, KeyError, ValueError, ValidationError) as exc:
            raise SceneError(
                "RESULTS_INVALID", f"Published results are missing or unreadable: {exc}"
            ) from exc
        object_ids = [o.id for o in objects]
        if (
            len(set(ids)) != len(ids)
            or len(set(object_ids)) != len(object_ids)
            or set(ids) != set(object_ids)
        ):
            raise SceneError("RESULTS_INVALID", "Objects and embeddings have different ids")
        if set(descriptions) != set(object_ids):
            raise SceneError("RESULTS_INVALID", "Objects and Descriptions have different ids")
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
        return PublishedScene(
            objects,
            dict(zip(ids, vectors, strict=True)),
            {key: description.text() for key, description in descriptions.items()},
        )

    def _check_membership(self, object_ids: list[str]) -> None:
        """The membership file must decode and list the Objects in order."""
        try:
            membership = ObjectMembership.decode(self.workspace.path(self.MEMBERSHIP).read_bytes())
        except (OSError, ValueError) as exc:
            raise SceneError("RESULTS_INVALID", f"Object membership is unreadable: {exc}") from exc
        if membership.ids != object_ids:
            raise SceneError(
                "RESULTS_INVALID", "Object membership and the Objects file list different Objects"
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
