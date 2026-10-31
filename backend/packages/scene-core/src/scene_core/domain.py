from enum import StrEnum

from pydantic import BaseModel, Field, TypeAdapter


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


class ObjectDescription(BaseModel):
    """An Object's three sentences: how it looks, what it is for and where it is in the Scene."""

    appearance: str = Field(min_length=1)
    use: str = Field(min_length=1)
    placement: str = Field(min_length=1)

    def text(self) -> str:
        """The sentences in the order they are embedded and reranked."""
        return " ".join((self.appearance, self.use, self.placement))


# The embed Stage's Descriptions file: each Object id's Object Description.
DESCRIPTIONS = TypeAdapter(dict[str, ObjectDescription])

# The objects Stage's file: a Scene's Objects, in the order their Object Membership lists them.
OBJECT_LIST = TypeAdapter(list[SceneObject])
