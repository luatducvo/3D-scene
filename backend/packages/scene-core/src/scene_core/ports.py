from abc import ABC,abstractmethod
from typing import Any,ClassVar,Protocol
from pydantic import BaseModel
from .contracts import SceneWorkspace
from .domain import SceneObject,Relation,SceneGraphContext
class StageAlgorithm(ABC):
    name:ClassVar[str]
    stage:ClassVar[str]
    manifest_type:ClassVar[type[BaseModel]]
    reads:ClassVar[list[str]]
    writes:ClassVar[list[str]]
    def setup(self)->None: pass
    def download_weights(self)->None: pass
    @abstractmethod
    def run(self,workspace:SceneWorkspace,params:dict[str,Any])->BaseModel: ...
class RelationRule(ABC):
    predicate:ClassVar[str]
    @abstractmethod
    def evaluate(self,a:SceneObject,b:SceneObject,context:SceneGraphContext)->Relation|None: ...
class ComputeBackend(Protocol):
    def run(self,algorithm:str,scene_id:str,params:dict,reads:list[str],writes:list[str])->dict: ...
    def invoke(self,algorithm:str,method:str,payload:dict)->dict: ...
class TextEmbedder(Protocol):
    def embed_text(self,texts:list[str]): ...
class LLMClient(Protocol):
    def complete(self,messages:list[dict],tools:list[dict])->dict: ...
class AgentTool(Protocol):
    name:str
    description:str
    parameters:dict
    def execute(self,arguments:dict)->dict: ...
