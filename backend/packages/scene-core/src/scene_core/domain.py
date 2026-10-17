from enum import StrEnum

from pydantic import BaseModel, Field


class SceneStatus(StrEnum):
    CREATED = "created"
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class OrientedBox(BaseModel):
    center: tuple[float, float, float]
    size: tuple[float, float, float]
    yaw: float = 0


class BestView(BaseModel):
    frame_id: str
    bbox: tuple[int, int, int, int]
    score: float


class SceneObject(BaseModel):
    id: str
    label: str
    label_vi: str | None = None
    box: OrientedBox
    attributes: dict[str, list[str]] = Field(default_factory=dict)
    best_views: list[BestView] = Field(default_factory=list)


class Relation(BaseModel):
    subject_id: str
    predicate: str
    object_id: str | None = None
    value: float | None = None


class SceneGraph(BaseModel):
    scene_id: str
    floor_z: float = 0
    ceiling_height: float | None = None
    floor_area: float | None = None
    objects: list[SceneObject] = Field(default_factory=list)
    relations: list[Relation] = Field(default_factory=list)


class SceneGraphContext(BaseModel):
    floor_z: float = 0
    ceiling_height: float | None = None
    walls: list[dict] = Field(default_factory=list)
