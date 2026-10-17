import logging,os
from pathlib import Path
from scene_core.config import PipelineConfig,ComputeConfig
from scene_core.executor import Executor
from .compute.http import HttpBackend
from .compute.local import LocalFiles
class InProcessBackend(LocalFiles):
    def __init__(self,data_dir): super().__init__(data_dir);self.executor=Executor(data_dir)
    def run(self,algorithm,scene_id,params,reads,writes,on_progress=None): return self.executor.run(algorithm,scene_id,params,on_progress)
    def invoke(self,algorithm,method,payload): return self.executor.invoke(algorithm,method,payload)
def backend_for(data_dir,target):
    if target.backend in ("cpu","inprocess"): return InProcessBackend(data_dir)
    if target.backend=="http":
        if not target.url:raise ValueError("A Target used by the pipeline has no URL; set it in backend/.env")
        return HttpBackend(data_dir,target)
    raise ValueError(f"Unsupported compute backend {target.backend}")
def pipeline_backend(data_dir,pipeline,compute,startup_timeout=None):
    """The backend of the one Target every Stage runs on; it also stores the uploaded inputs (ADR-0005)."""
    used={s.target for s in pipeline.stages.values()}
    unset=sorted(t[2:-1] for t in used if t.startswith("${"))
    if unset:raise ValueError(f"Set {', '.join(unset)} in backend/.env to a compute Target name")
    missing=used-set(compute.targets)
    if missing:raise ValueError(f"Pipeline uses unknown compute Targets: {sorted(missing)}")
    no_url=sorted(t for t in used if compute.targets[t].missing_url)
    if no_url:raise ValueError(f"compute Targets {no_url} have no URL; set their URL variables in backend/.env")
    # Stage outputs stay where they were produced, so the whole pipeline shares one Target.
    if len(used)!=1:raise ValueError(f"Every Stage must use one compute Target, found {sorted(used)}")
    target=compute.targets[used.pop()]
    if startup_timeout is not None:target=target.model_copy(update={"startup_timeout":min(target.startup_timeout,startup_timeout)})
    return backend_for(data_dir,target)
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
