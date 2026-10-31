from pathlib import Path

from pydantic import BaseModel

STAGES = ("ingest", "recon", "align", "mesh", "segment", "lift", "objects", "embed")
OUTPUTS = {
    "ingest": ["keyframes"],
    "recon": ["recon"],
    "align": ["align"],
    "mesh": ["mesh"],
    "segment": ["segment"],
    "lift": ["instances"],
    "objects": ["objects"],
    "embed": ["embeddings"],
}


class SceneWorkspace:
    """A Scene's folder under data_dir/scenes; with a version, one immutable publication inside it."""

    def __init__(self, data_dir: Path, scene_id: str, version: str | None = None):
        for name in (scene_id, version):
            if name is not None and (not name or any(x in name for x in ("/", "\\", "..", ":"))):
                raise ValueError("Invalid scene id or version")
        self.scene_id = scene_id
        self.version = version
        self.root = (Path(data_dir) / "scenes" / scene_id / (version or "")).resolve()

    def path(self, *parts: str) -> Path:
        candidate = self.root.joinpath(*parts).resolve()
        if not candidate.is_relative_to(self.root):
            raise ValueError("Path outside workspace")
        return candidate

    def dir(self, *parts: str) -> Path:
        result = self.path(*parts)
        result.mkdir(parents=True, exist_ok=True)
        return result


class IngestManifest(BaseModel):
    num_inputs: int
    num_keyframes: int
    rejected: dict[str, list[str]]


class ReconManifest(BaseModel):
    num_frames: int
    frame_ids: list[str]
    metric_scale: float
    image_size: tuple[int, int]


class AlignManifest(BaseModel):
    world_to_aligned: list[list[float]]
    floor_z: float
    ceiling_height: float | None = None


class MeshManifest(BaseModel):
    mesh_file: str
    points_file: str
    num_faces: int
    num_points: int = 0


class SegmentManifest(BaseModel):
    num_masks: int
    vocabulary_size: int


class LiftManifest(BaseModel):
    num_instances: int
    instances_file: str


class EmbedManifest(BaseModel):
    # The sentence model that embedded the Object Descriptions and embeds Search queries.
    model_id: str
    vlm_model_id: str
    reranker_model_id: str
    dim: int
    embeddings_file: str
    descriptions_file: str


class ObjectsManifest(BaseModel):
    num_objects: int
