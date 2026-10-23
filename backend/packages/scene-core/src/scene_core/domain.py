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
    box: OrientedBox
    best_views: list[BestView] = Field(default_factory=list)


class SceneGraph(BaseModel):
    objects: list[SceneObject] = Field(default_factory=list)
