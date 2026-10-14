import threading
from pathlib import Path
from .contracts import SceneWorkspace
from .registry import Registry
class Executor:
    def __init__(self,data_dir:Path,registry:Registry|None=None):
        self.data_dir=Path(data_dir);self.registry=registry or Registry();self._instances={};self._lock=threading.RLock()
    def algorithm(self,name:str):
        if name not in self._instances:
            instance=self.registry.resolve(name)();instance.setup();self._instances[name]=instance
        return self._instances[name]
    def run(self,algorithm:str,scene_id:str,params:dict,on_progress=None)->dict:
        with self._lock:
            instance=self.algorithm(algorithm)
            workspace=SceneWorkspace(self.data_dir,scene_id)
            instance._progress=on_progress
            try:result=instance.manifest_type.model_validate(instance.run(workspace,params))
            finally:instance._progress=None
            for output in instance.writes:
                workspace.dir(output).joinpath("manifest.json").write_text(result.model_dump_json(indent=2),encoding="utf-8")
            return result.model_dump(mode="json")
    def invoke(self,algorithm:str,method:str,payload:dict)->dict:
        if method!="embed_text": raise ValueError("Unsupported invoke method")
        with self._lock:
            value=self.algorithm(algorithm).embed_text(**payload)
            return {"vectors":value.tolist() if hasattr(value,"tolist") else value}
