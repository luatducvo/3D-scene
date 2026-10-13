import hashlib,json,os,re
from pathlib import Path
import yaml
from pydantic import BaseModel,Field,field_validator,model_validator
from .contracts import STAGES
class StageConfig(BaseModel):
    algorithm:str
    target:str="cpu"
    params:dict=Field(default_factory=dict)
    def config_hash(self):
        return hashlib.sha256(json.dumps({"algorithm":self.algorithm,"params":self.params},sort_keys=True,separators=(",",":")).encode()).hexdigest()
class PipelineConfig(BaseModel):
    default_gpu_target:str="cpu"
    stages:dict[str,StageConfig]
    @model_validator(mode="after")
    def validate_stages(self):
        if tuple(self.stages)!=STAGES: raise ValueError("Pipeline must declare all nine stages in order")
        return self
    @classmethod
    def load(cls,path):
        return cls.model_validate(yaml.safe_load(Path(path).read_text()))
class TargetConfig(BaseModel):
    backend:str="inprocess"
    url:str|None=None
    token:str=""
    headers:dict[str,str]=Field(default_factory=dict)
    shared_storage:bool=False
    chunk_size:int=25*1024*1024
    startup_timeout:float=900
    poll_interval:float=1
    @field_validator("url",mode="before")
    @classmethod
    def blank_url(cls,value): return value or None
    @field_validator("token",mode="before")
    @classmethod
    def blank_token(cls,value): return value or ""
    @field_validator("headers",mode="before")
    @classmethod
    def strip_headers(cls,value): return {k:str(v or "").strip() for k,v in (value or {}).items()}
class ComputeConfig(BaseModel):
    targets:dict[str,TargetConfig]=Field(default_factory=lambda:{"cpu":TargetConfig()})
    @classmethod
    def load(cls,path):
        # Unset or empty ${VAR} values expand to nothing, so unused Targets stay valid.
        text=re.sub(r"\$\{(\w+)\}",lambda m:os.environ.get(m.group(1),""),Path(path).read_text())
        return cls.model_validate(yaml.safe_load(text))
