import logging,os
from pathlib import Path
from scene_core.config import PipelineConfig,ComputeConfig
from scene_core.executor import Executor
from .compute.http import HttpBackend
class InProcessBackend:
    def __init__(self,data_dir): self.executor=Executor(data_dir)
    def run(self,algorithm,scene_id,params,reads,writes,on_progress=None): return self.executor.run(algorithm,scene_id,params,on_progress)
    def invoke(self,algorithm,method,payload): return self.executor.invoke(algorithm,method,payload)
def backend_for(data_dir,target):
    if target.backend in ("cpu","inprocess"): return InProcessBackend(data_dir)
    if target.backend=="http":
        if not target.url:raise ValueError("A Target used by the pipeline has no URL; set it in backend/.env")
        return HttpBackend(data_dir,target)
    raise ValueError(f"Unsupported compute backend {target.backend}")
def configuration():
    root=Path(__file__).resolve().parents[4]
    pipeline=PipelineConfig.load(os.getenv("PIPELINE_CONFIG",str(root/"config/pipeline.fake.yaml")))
    compute_path=Path(os.getenv("COMPUTE_CONFIG",str(root/"config/compute.yaml")))
    return pipeline,ComputeConfig.load(compute_path) if compute_path.exists() else ComputeConfig()
def delete_remote_workspaces(data_dir,compute,scene_id):
    """Remove a Scene's copies from every non-shared remote Target; an unreachable Target is only logged."""
    for name,target in compute.targets.items():
        if target.backend!="http" or target.shared_storage or not target.url:continue
        backend=HttpBackend(data_dir,target)
        try:backend.delete_workspace(scene_id)
        except Exception:logging.exception("Could not delete Workspace %s on Target %s",scene_id,name)
        finally:backend.close()
