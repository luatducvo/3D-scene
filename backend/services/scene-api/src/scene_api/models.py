from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field
from scene_core.contracts import STAGES
from scene_core.domain import SceneObject, SceneStatus

# The nine Stages in order; the frontend checks its own list against this enum.
Stage = Literal[STAGES]


class SceneCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class SceneCreated(BaseModel):
    id: str


class Failure(BaseModel):
    stage: str
    code: str
    message: str
    details: dict = Field(default_factory=dict)


class SceneSummary(BaseModel):
    id: str
    name: str
    status: SceneStatus
    created_at: datetime


class StageProgress(BaseModel):
    done: int
    total: int
    unit: str


class StageRun(BaseModel):
    stage: Stage
    algorithm: str
    status: Literal["running", "done", "failed"]
    manifest: dict | None = None
    error: dict | None = None
    progress: StageProgress | None = None
    started_at: datetime | None = None
    updated_at: datetime | None = None


class SceneAssets(BaseModel):
    mesh_url: str | None = None
    points_url: str | None = None
    membership_url: str | None = Field(
        default=None,
        description=(
            "Object membership of points and mesh vertices (binary, see docs/architecture/api.md); "
            "null for a Scene published before membership existed."
        ),
    )


class SceneDetail(SceneSummary):
    stage_runs: list[StageRun] = Field(default_factory=list)
    assets: SceneAssets = Field(default_factory=SceneAssets)
    failure: Failure | None = None
    ingest_report: dict | None = None


class JobCreated(BaseModel):
    job_id: str


class UploadResult(BaseModel):
    filenames: list[str]


class SearchHit(BaseModel):
    object: SceneObject
    score: float


class Camera(BaseModel):
    position: tuple[float, float, float]
    target: tuple[float, float, float]
    up: tuple[float, float, float] = (0, 0, 1)


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    camera: Camera | None = None


class Evidence(BaseModel):
    """The Frame that best shows an Object in an answer; its image is not published (ADR-0008)."""

    object_id: str
    frame_id: str


class ProgressEvent(BaseModel):
    """`stage` events carry a Stage Run's state, `status` events the Scene's; `progress` events carry done/total/unit
    for one Stage. Replay sends the same shapes as live: each Stage Run's `stage` event, then its `progress` if any."""

    type: Literal["stage", "status", "progress"]
    stage: Stage | None = None
    status: str | None = None
    algorithm: str | None = None
    manifest: dict | None = None
    error: dict | None = None
    started_at: datetime | None = None
    updated_at: datetime | None = None
    done: int | None = None
    total: int | None = None
    unit: str | None = None


class QueryEvent(BaseModel):
    type: Literal["tool", "delta", "final"]
    tool: str | None = None
    delta: str | None = None
    answer: str | None = None
    object_ids: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)


class Message(BaseModel):
    id: int
    role: str
    content: dict
    created_at: datetime
