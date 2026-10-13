from datetime import datetime
from typing import Literal
from pydantic import BaseModel,Field
from scene_core.domain import SceneObject,SceneStatus,Relation
class SceneCreate(BaseModel):
    name:str=Field(min_length=1,max_length=200)
class SceneCreated(BaseModel):
    id:str
class Failure(BaseModel):
    stage:str
    code:str
    message:str
    details:dict=Field(default_factory=dict)
class SceneSummary(BaseModel):
    id:str
    name:str
    status:SceneStatus
    created_at:datetime
class StageRun(BaseModel):
    stage:str
    algorithm:str
    status:Literal["running","done","skipped","failed"]
    config_hash:str
    manifest:dict|None=None
    error:dict|None=None
class SceneAssets(BaseModel):
    mesh_url:str|None=None
    points_url:str|None=None
class SceneDetail(SceneSummary):
    stage_runs:list[StageRun]=Field(default_factory=list)
    assets:SceneAssets=Field(default_factory=SceneAssets)
    failure:Failure|None=None
    ingest_report:dict|None=None
class ProcessRequest(BaseModel):
    from_stage:Literal["ingest","recon","align","mesh","segment","lift","embed","attributes","graph"]|None=None
class JobCreated(BaseModel):
    job_id:str
class UploadResult(BaseModel):
    filenames:list[str]
class SearchHit(BaseModel):
    object:SceneObject
    score:float
class Camera(BaseModel):
    position:tuple[float,float,float]
    target:tuple[float,float,float]
    up:tuple[float,float,float]=(0,0,1)
class QueryRequest(BaseModel):
    question:str=Field(min_length=1,max_length=4000)
    camera:Camera|None=None
class Evidence(BaseModel):
    object_id:str
    image_url:str
    frame_id:str
class ProgressEvent(BaseModel):
    type:Literal["stage","status"]
    stage:str|None=None
    status:str
    algorithm:str|None=None
    manifest:dict|None=None
    error:dict|None=None
class QueryEvent(BaseModel):
    type:Literal["tool","delta","final"]
    tool:str|None=None
    delta:str|None=None
    answer:str|None=None
    object_ids:list[str]=Field(default_factory=list)
    evidence:list[Evidence]=Field(default_factory=list)
class Message(BaseModel):
    id:int
    role:str
    content:dict
    created_at:datetime
class ErrorDetail(BaseModel):
    code:str
    message:str
class ErrorResponse(BaseModel):
    error:ErrorDetail
