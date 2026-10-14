import json,os,shutil,uuid
from pathlib import Path
from contextlib import asynccontextmanager
import httpx
from fastapi import BackgroundTasks,FastAPI,Request,UploadFile,File,Response
from fastapi.responses import JSONResponse,FileResponse,StreamingResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from scene_core.contracts import SceneWorkspace,STAGES
from scene_core.errors import SceneError
from psycopg.types.json import Jsonb
from scene_worker.compute.http import ComputeError
from scene_worker.repository import Repository
from .models import *

QUERY_READY_TIMEOUT_S=10

def create_app(database_url=None,data_dir=None,pipeline=None,compute=None,llm=None):
    repo=Repository(database_url or os.getenv("DATABASE_URL","postgresql://scene:scene@localhost:5432/scene"))
    data_dir=Path(data_dir or os.getenv("DATA_DIR","data"))
    @asynccontextmanager
    async def lifespan(app):
        repo.migrate()
        yield
    app=FastAPI(title="Scene Understanding API",version="1.0.0",lifespan=lifespan)
    app.state.repository=repo;app.state.data_dir=data_dir;app.state.pipeline=pipeline;app.state.compute=compute;app.state.llm=llm
    app.add_middleware(CORSMiddleware,allow_origins=os.getenv("CORS_ORIGINS","http://localhost:3000").split(","),allow_methods=["*"],allow_headers=["*"])
    @app.exception_handler(SceneError)
    async def scene_error(request,exc): return JSONResponse({"error":{"code":exc.code,"message":exc.message}},status_code=exc.status_code)
    @app.exception_handler(RequestValidationError)
    async def validation_error(request,exc): return JSONResponse({"error":{"code":"INVALID_REQUEST","message":str(exc)}},status_code=422)
    def summary(row): return {**row,"id":str(row["id"])}
    def url(request,scene_id,path): return str(request.url_for("scene_file",scene_id=str(scene_id),file_path=path))
    @app.post("/api/v1/scenes",response_model=SceneCreated,status_code=201)
    def create_scene(body:SceneCreate):
        scene_id=uuid.uuid4()
        with repo.connect() as conn: conn.execute("INSERT INTO scenes(id,name) VALUES(%s,%s)",(scene_id,body.name.strip()))
        SceneWorkspace(data_dir,str(scene_id)).dir("raw")
        return {"id":str(scene_id)}
    @app.get("/api/v1/scenes",response_model=list[SceneSummary])
    def list_scenes():
        with repo.connect() as conn: return [summary(s) for s in conn.execute("SELECT * FROM scenes ORDER BY created_at DESC").fetchall()]
    @app.get("/api/v1/scenes/{scene_id}",response_model=SceneDetail)
    def get_scene(scene_id:uuid.UUID,request:Request):
        with repo.connect() as conn:
            scene=summary(repo.get_scene(scene_id,conn))
            stages=conn.execute("SELECT * FROM stage_runs WHERE scene_id=%s",(scene_id,)).fetchall()
        scene["stage_runs"]=sorted(stages,key=lambda s:STAGES.index(s["stage"]))
        workspace=SceneWorkspace(data_dir,str(scene_id))
        scene["assets"]={key:url(request,scene_id,path) if workspace.path(path).is_file() else None for key,path in (("mesh_url","mesh/mesh.glb"),("points_url","mesh/points.ply"))}
        scene["ingest_report"]=next((s["manifest"] for s in stages if s["stage"]=="ingest"),None)
        return scene
    @app.delete("/api/v1/scenes/{scene_id}",status_code=204)
    def delete_scene(scene_id:uuid.UUID,background:BackgroundTasks):
        with repo.connect() as conn:
            repo.get_scene(scene_id,conn,True);repo.assert_idle(scene_id,conn)
            shutil.rmtree(SceneWorkspace(data_dir,str(scene_id)).root,ignore_errors=True)
            conn.execute("DELETE FROM scenes WHERE id=%s",(scene_id,))
        from scene_worker.container import configuration,delete_remote_workspaces
        background.add_task(delete_remote_workspaces,data_dir,app.state.compute or configuration()[1],str(scene_id))
        return Response(status_code=204)
    @app.get("/api/v1/scenes/{scene_id}/files/{file_path:path}",name="scene_file")
    def scene_file(scene_id:uuid.UUID,file_path:str):
        repo.get_scene(scene_id)
        if "\\" in file_path or any(p in ("..",".") for p in file_path.split("/")) or file_path.split("/")[0] not in {"keyframes","mesh","instances","recon"}:
            raise SceneError("FILE_FORBIDDEN","File path is not public",403)
        workspace=SceneWorkspace(data_dir,str(scene_id))
        try: path=workspace.path(file_path)
        except ValueError: raise SceneError("FILE_FORBIDDEN","Invalid file path",403)
        if not path.is_file(): raise SceneError("FILE_NOT_FOUND","File not found",404)
        return FileResponse(path)
    @app.post("/api/v1/scenes/{scene_id}/uploads",response_model=UploadResult)
    def upload_files(scene_id:uuid.UUID,files:list[UploadFile]=File(...)):
        with repo.connect() as conn:
            scene=repo.get_scene(scene_id,conn,True);repo.assert_idle(scene_id,conn)
            if scene["status"] not in ("created","uploaded"):raise SceneError("SCENE_LOCKED","Create a new Scene to upload more files",409)
            if not files:raise SceneError("INVALID_UPLOAD","No files supplied",400)
            allowed={".jpg",".jpeg",".png",".webp",".heic",".mp4",".mov",".mkv",".webm"}
            for upload in files:
                if Path(upload.filename or "").suffix.lower() not in allowed or not (upload.content_type or "").startswith(("image/","video/")):
                    raise SceneError("UNSUPPORTED_MEDIA","Only photos or a video are accepted",415)
            folder=SceneWorkspace(data_dir,str(scene_id)).dir("raw")
            video_ext={".mp4",".mov",".mkv",".webm"}
            existing=list(folder.iterdir())
            is_video=any(Path(u.filename).suffix.lower() in video_ext for u in files)
            if (is_video and (len(files)!=1 or existing)) or any(f.suffix.lower() in video_ext for f in existing):
                raise SceneError("INVALID_UPLOAD","Upload photos or one video, without mixing them",400)
            saved=[]
            try:
                for upload in files:
                    name=uuid.uuid4().hex+Path(upload.filename).suffix.lower()
                    with (folder/name).open("wb") as dest:
                        shutil.copyfileobj(upload.file,dest,length=1024*1024)
                    saved.append(name)
                conn.execute("UPDATE scenes SET status='uploaded' WHERE id=%s",(scene_id,))
            except Exception:
                for name in saved:(folder/name).unlink(missing_ok=True)
                raise
            return {"filenames":saved}
    @app.post("/api/v1/scenes/{scene_id}/process",response_model=JobCreated,status_code=202)
    def process_scene(scene_id:uuid.UUID,body:ProcessRequest):
        return {"job_id":repo.enqueue(scene_id,body.from_stage)}
    def public_objects(scene_id,request):
        objects=repo.objects(scene_id)
        for obj in objects:
            for view in obj["best_views"]:
                view["image_url"]=url(request,scene_id,"recon/rgb/"+view["frame_id"]+".png")
        return objects
    @app.get("/api/v1/scenes/{scene_id}/objects",response_model=list[SceneObject])
    def list_objects(scene_id:uuid.UUID,request:Request):return public_objects(scene_id,request)
    @app.get("/api/v1/scenes/{scene_id}/objects/{object_id}",response_model=SceneObject)
    def get_object(scene_id:uuid.UUID,object_id:str,request:Request):
        found=next((obj for obj in public_objects(scene_id,request) if obj["id"]==object_id),None)
        if found is None:raise SceneError("OBJECT_NOT_FOUND","Object not found",404)
        return found
    @app.get("/api/v1/scenes/{scene_id}/events",response_class=StreamingResponse)
    def events(scene_id:uuid.UUID):
        repo.get_scene(scene_id)
        def stream():
            with repo.connect() as conn:
                conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
                scene=repo.get_scene(scene_id,conn)
                stages=conn.execute("SELECT * FROM stage_runs WHERE scene_id=%s",(scene_id,)).fetchall()
                cursor=conn.execute("SELECT COALESCE(MAX(id),0) AS id FROM scene_events WHERE scene_id=%s",(scene_id,)).fetchone()["id"]
            for stage in sorted(stages,key=lambda s:STAGES.index(s["stage"])):
                payload={k:stage[k] for k in ("stage","status","algorithm","manifest","error","progress")}
                payload.update({k:stage[k].isoformat() if stage[k] else None for k in ("started_at","updated_at")})
                yield "event: stage\ndata: "+json.dumps({"type":"stage",**payload})+"\n\n"
            yield "event: status\ndata: "+json.dumps({"type":"status","status":scene["status"]})+"\n\n"
            if scene["status"]!="processing":return
            import time
            while True:
                with repo.connect() as conn:
                    rows=conn.execute("SELECT * FROM scene_events WHERE scene_id=%s AND id>%s ORDER BY id",(scene_id,cursor)).fetchall()
                for event in rows:
                    cursor=event["id"]
                    yield f"id: {cursor}\nevent: {event['event']}\ndata: "+json.dumps({"type":event["event"],**event["data"]})+"\n\n"
                    if event["event"]=="status" and event["data"]["status"] in ("ready","failed"):return
                time.sleep(0.2)
        return StreamingResponse(stream(),media_type="text/event-stream",headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})
    def query_embedder():
        """Queries are embedded by the pipeline's own embed Algorithm on its Target, created once."""
        if getattr(app.state,"embedder",None) is None:
            from scene_worker.container import configuration,backend_for
            defaults=None if app.state.pipeline and app.state.compute else configuration()
            pipeline=app.state.pipeline or defaults[0];compute_config=app.state.compute or defaults[1]
            stage=pipeline.stages["embed"];target=compute_config.targets.get(stage.target)
            if target is None or target.missing_url:
                raise SceneError("COMPUTE_UNAVAILABLE",f"The embed Stage's compute Target {stage.target} is not configured",503)
            # A query waits briefly for readiness instead of a Job's full cold-start deadline.
            target=target.model_copy(update={"startup_timeout":min(target.startup_timeout,QUERY_READY_TIMEOUT_S)})
            app.state.embedder=(stage.algorithm,backend_for(data_dir,target))
        return app.state.embedder
    @app.get("/api/v1/scenes/{scene_id}/search",response_model=list[SearchHit])
    def search_objects(scene_id:uuid.UUID,q:str,request:Request):
        return search(scene_id,q,public_objects(scene_id,request))
    def search(scene_id,q,objects):
        if not q.strip():return []
        import numpy as np
        algorithm,backend=query_embedder()
        try:vector=backend.invoke(algorithm,"embed_text",{"texts":[q]})["vectors"][0]
        except (ComputeError,httpx.TransportError) as exc:
            raise SceneError("COMPUTE_UNAVAILABLE",f"The embed Stage's compute Target is unavailable: {exc}",503) from exc
        if len(vector)!=1024:raise SceneError("EMBEDDING_DIMENSION_MISMATCH","Query vector dimension differs from database",500)
        scores={}
        if np.linalg.norm(vector)>0:
            with repo.connect() as conn:
                for row in conn.execute("SELECT id,1-(embedding <=> %s::vector) AS score FROM objects WHERE scene_id=%s",(str(vector),scene_id)).fetchall():scores[row["id"]]=float(row["score"] or 0)
        hits=[]
        for obj in objects:
            label_match=any(label and (q.lower() in label.lower() or label.lower() in q.lower()) for label in (obj["label"],obj["label_vi"]))
            score=scores.get(obj["id"],0)+(1 if label_match else 0)
            if score>0.15:hits.append({"object":obj,"score":score})
        return sorted(hits,key=lambda hit:hit["score"],reverse=True)
    @app.get("/api/v1/scenes/{scene_id}/messages",response_model=list[Message])
    def list_messages(scene_id:uuid.UUID):
        with repo.connect() as conn:
            repo.get_scene(scene_id,conn)
            return conn.execute("SELECT id,role,content,created_at FROM messages WHERE scene_id=%s ORDER BY id",(scene_id,)).fetchall()
    @app.post("/api/v1/scenes/{scene_id}/queries",response_class=StreamingResponse,responses={200:{"model":QueryEvent,"content":{"text/event-stream":{}}}})
    def ask(scene_id:uuid.UUID,body:QueryRequest,request:Request):
        from .qa import OpenAICompatibleLLM,QAAgent,SceneTools
        with repo.connect() as conn:
            scene=repo.get_scene(scene_id,conn)
            if scene["status"]!="ready":raise SceneError("SCENE_NOT_READY","Process the Scene before asking questions",409)
            relations=conn.execute("SELECT subject_id,predicate,object_id,value FROM relations WHERE scene_id=%s",(scene_id,)).fetchall()
            history=conn.execute("SELECT role,content FROM messages WHERE scene_id=%s ORDER BY id DESC LIMIT 10",(scene_id,)).fetchall()[::-1]
        llm=app.state.llm or OpenAICompatibleLLM.from_env()
        if llm is None:raise SceneError("LLM_NOT_CONFIGURED","Set LLM_BASE_URL and LLM_MODEL to ask questions",503)
        objects=public_objects(scene_id,request)
        tools=SceneTools(objects,relations,scene["room"],lambda q:search(scene_id,q,objects),body.camera.model_dump() if body.camera else None)
        past=[{"role":m["role"],"content":m["content"].get("question") or m["content"].get("answer") or ""} for m in history]
        def stream():
            try:
                for event in QAAgent(llm).answer(body.question,tools,past):
                    if event["type"]=="final":
                        by_id={o["id"]:o for o in objects}
                        event["evidence"]=[{"object_id":i,"frame_id":v["frame_id"],"image_url":v["image_url"]} for i in event["object_ids"] for v in by_id[i]["best_views"][:1]]
                        with repo.connect() as conn:
                            conn.execute("INSERT INTO messages(scene_id,role,content) VALUES(%s,'user',%s)",(scene_id,Jsonb({"question":body.question})))
                            conn.execute("INSERT INTO messages(scene_id,role,content) VALUES(%s,'assistant',%s)",(scene_id,Jsonb({k:event[k] for k in ("answer","object_ids","evidence")})))
                    yield f"event: {event['type']}\ndata: "+json.dumps(QueryEvent.model_validate(event).model_dump(mode="json"),ensure_ascii=False)+"\n\n"
            except Exception as exc:
                code=getattr(exc,"code","QA_FAILED")
                yield "event: error\ndata: "+json.dumps({"error":{"code":code,"message":str(exc)}},ensure_ascii=False)+"\n\n"
        return StreamingResponse(stream(),media_type="text/event-stream",headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})
    return app
app=create_app()
