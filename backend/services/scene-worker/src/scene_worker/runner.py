import logging,time
import numpy as np
from psycopg.types.json import Jsonb
from scene_core.contracts import SceneWorkspace,STAGES
from scene_core.domain import SceneGraph
from scene_core.registry import Registry
from .container import backend_for,configuration
from .repository import Repository
class Worker:
    def __init__(self,database_url,data_dir,pipeline=None,compute=None):
        self.repo=Repository(database_url);self.data_dir=data_dir
        defaults=configuration() if pipeline is None or compute is None else (pipeline,compute)
        self.pipeline=pipeline or defaults[0];self.compute=compute or defaults[1]
        used={s.target for s in self.pipeline.stages.values()}
        unset=sorted(t[2:-1] for t in used if t.startswith("${"))
        if unset:raise ValueError(f"Set {', '.join(unset)} in backend/.env to a compute Target name")
        missing=used-set(self.compute.targets)
        if missing:raise ValueError(f"Pipeline uses unknown compute Targets: {sorted(missing)}")
        no_url=sorted(t for t in used if self.compute.targets[t].missing_url)
        if no_url:raise ValueError(f"compute Targets {no_url} have no URL; set their URL variables in backend/.env")
        self.backends={name:backend_for(data_dir,self.compute.targets[name]) for name in used}
    def recover_interrupted(self):
        """Fail Jobs left running by a previous worker process, so their Scenes can be processed again.

        Assumes one worker per database, as in the Compose deployment.
        """
        with self.repo.connect() as conn:
            for job in conn.execute("SELECT * FROM jobs WHERE status='running'").fetchall():
                stage=conn.execute("SELECT stage FROM stage_runs WHERE scene_id=%s AND status='running'",(job["scene_id"],)).fetchone()
                failure={"stage":stage["stage"] if stage else "publish","code":"WORKER_INTERRUPTED","message":"The worker restarted while this Job was running; process the Scene again","details":{}}
                if stage:
                    conn.execute("UPDATE stage_runs SET status='failed',error=%s WHERE scene_id=%s AND stage=%s",(Jsonb(failure),job["scene_id"],stage["stage"]))
                    self.repo.event(conn,job["scene_id"],"stage",{"stage":stage["stage"],"status":"failed","error":failure})
                conn.execute("UPDATE jobs SET status='failed',finished_at=now(),error=%s WHERE id=%s",(Jsonb(failure),job["id"]))
                conn.execute("UPDATE scenes SET status='failed',failure=%s WHERE id=%s",(Jsonb(failure),job["scene_id"]))
                self.repo.event(conn,job["scene_id"],"status",{"status":"failed","error":failure})
                logging.warning("Job %s was interrupted at %s; marked failed",job["id"],failure["stage"])
    def run_once(self):
        with self.repo.connect() as conn:
            job=conn.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1").fetchone()
            if not job:return False
            conn.execute("UPDATE jobs SET status='running',started_at=now() WHERE id=%s",(job["id"],))
        stage=None
        try:
            workspace=SceneWorkspace(self.data_dir,str(job["scene_id"]))
            force=False
            for stage in STAGES:
                config=self.pipeline.stages[stage];algorithm=Registry().resolve(config.algorithm)
                with self.repo.connect() as conn:
                    previous=conn.execute("SELECT * FROM stage_runs WHERE scene_id=%s AND stage=%s",(job["scene_id"],stage)).fetchone()
                force=force or stage==job["from_stage"]
                skip=not force and previous and previous["status"] in ("done","skipped") and previous["config_hash"]==config.config_hash() and all(workspace.path(d).is_dir() and any(workspace.path(d).iterdir()) for d in algorithm.writes)
                if skip:
                    self._stage(job,stage,config,"skipped",previous["manifest"]);continue
                force=True;self._stage(job,stage,config,"running")
                manifest=self.backends[config.target].run(config.algorithm,str(job["scene_id"]),config.params,algorithm.reads,algorithm.writes,on_progress=self._reporter(job,stage))
                self._stage(job,stage,config,"done",manifest)
            self.publish(job["scene_id"],workspace)
            with self.repo.connect() as conn:
                conn.execute("UPDATE jobs SET status='done',finished_at=now() WHERE id=%s",(job["id"],))
                conn.execute("UPDATE scenes SET status='ready',failure=NULL WHERE id=%s",(job["scene_id"],))
                self.repo.event(conn,job["scene_id"],"status",{"status":"ready"})
        except Exception as exc:
            logging.exception("Job %s failed at %s",job["id"],stage)
            failure={"stage":stage or "publish","code":getattr(exc,"code","STAGE_FAILED"),"message":str(exc),"details":getattr(exc,"details",{})}
            with self.repo.connect() as conn:
                if stage:
                    conn.execute("UPDATE stage_runs SET status='failed',error=%s WHERE scene_id=%s AND stage=%s",(Jsonb(failure),job["scene_id"],stage))
                    self.repo.event(conn,job["scene_id"],"stage",{"stage":stage,"status":"failed","error":failure})
                conn.execute("UPDATE jobs SET status='failed',finished_at=now(),error=%s WHERE id=%s",(Jsonb(failure),job["id"]))
                conn.execute("UPDATE scenes SET status='failed',failure=%s WHERE id=%s",(Jsonb(failure),job["scene_id"]))
                self.repo.event(conn,job["scene_id"],"status",{"status":"failed","error":failure})
        return True
    def _stage(self,job,stage,config,status,manifest=None):
        # A running Stage restarts its clock and clears progress; later states keep both.
        with self.repo.connect() as conn:
            row=conn.execute("INSERT INTO stage_runs(scene_id,stage,algorithm,config_hash,status,manifest,started_at) VALUES(%s,%s,%s,%s,%s,%s,now()) ON CONFLICT(scene_id,stage) DO UPDATE SET algorithm=EXCLUDED.algorithm,config_hash=EXCLUDED.config_hash,status=EXCLUDED.status,manifest=EXCLUDED.manifest,error=NULL,updated_at=now(),started_at=CASE WHEN EXCLUDED.status='running' OR stage_runs.started_at IS NULL THEN now() ELSE stage_runs.started_at END,progress=CASE WHEN EXCLUDED.status='running' THEN NULL ELSE stage_runs.progress END RETURNING started_at,updated_at",(job["scene_id"],stage,config.algorithm,config.config_hash(),status,Jsonb(manifest))).fetchone()
            self.repo.event(conn,job["scene_id"],"stage",{"stage":stage,"algorithm":config.algorithm,"status":status,"manifest":manifest,"started_at":row["started_at"].isoformat(),"updated_at":row["updated_at"].isoformat()})
    def _reporter(self,job,stage,interval=2.0):
        """Store and announce Stage progress at most every interval seconds, always including the last report."""
        last=[float("-inf")]
        def report(progress):
            now=time.monotonic()
            if progress["done"]<progress["total"] and now-last[0]<interval:return
            last[0]=now
            with self.repo.connect() as conn:
                conn.execute("UPDATE stage_runs SET progress=%s WHERE scene_id=%s AND stage=%s",(Jsonb(progress),job["scene_id"],stage))
                self.repo.event(conn,job["scene_id"],"progress",{"stage":stage,**progress})
        return report
    def publish(self,scene_id,workspace):
        graph=SceneGraph.model_validate_json(workspace.path("graph/scene_graph.json").read_text())
        with np.load(workspace.path("embeddings/objects.npz"),allow_pickle=False) as data:
            vectors={str(key):value for key,value in zip(data["ids"],data["vectors"],strict=True)}
        if set(vectors)!=set(o.id for o in graph.objects):raise ValueError("Object and embedding identities differ")
        if any(vector.shape!=(1024,) or not np.isfinite(vector).all() for vector in vectors.values()):raise ValueError("Embedding dimension must match database vector(1024)")
        with self.repo.connect() as conn:
            conn.execute("DELETE FROM objects WHERE scene_id=%s",(scene_id,));conn.execute("DELETE FROM relations WHERE scene_id=%s",(scene_id,))
            for obj in graph.objects:
                conn.execute("INSERT INTO objects(scene_id,id,label,label_vi,box,attributes,best_views,embedding) VALUES(%s,%s,%s,%s,%s,%s,%s,%s::vector)",(scene_id,obj.id,obj.label,obj.label_vi,Jsonb(obj.box.model_dump()),Jsonb(obj.attributes),Jsonb([v.model_dump() for v in obj.best_views]),str(vectors[obj.id].tolist())))
            for rel in graph.relations:
                conn.execute("INSERT INTO relations(scene_id,subject_id,predicate,object_id,value) VALUES(%s,%s,%s,%s,%s)",(scene_id,rel.subject_id,rel.predicate,rel.object_id,rel.value))
            conn.execute("UPDATE scenes SET room=%s WHERE id=%s",(Jsonb(graph.model_dump(exclude={"objects","relations"})),scene_id))
