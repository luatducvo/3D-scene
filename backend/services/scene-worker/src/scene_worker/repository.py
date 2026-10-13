import uuid
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from scene_core.errors import SceneError
class Repository:
    def __init__(self,url:str): self.url=url
    def connect(self): return psycopg.connect(self.url,row_factory=dict_row)
    def migrate(self):
        migration=Path(__file__).resolve().parents[4]/"migrations"/"001_init.sql"
        with self.connect() as conn: conn.execute(migration.read_text())
    def get_scene(self,scene_id,conn=None,lock=False):
        if conn is None:
            with self.connect() as own: return self.get_scene(scene_id,own,lock)
        row=conn.execute("SELECT * FROM scenes WHERE id=%s"+(" FOR UPDATE" if lock else ""),(scene_id,)).fetchone()
        if row is None: raise SceneError("SCENE_NOT_FOUND","Scene not found",404)
        return row
    def assert_idle(self,scene_id,conn):
        if conn.execute("SELECT 1 FROM jobs WHERE scene_id=%s AND status IN ('queued','running')",(scene_id,)).fetchone():
            raise SceneError("SCENE_BUSY","Scene has an active Job",409)
    def event(self,conn,scene_id,event,data):
        row=conn.execute("INSERT INTO scene_events(scene_id,event,data) VALUES(%s,%s,%s) RETURNING id",(scene_id,event,Jsonb(data))).fetchone()
        conn.execute("SELECT pg_notify('scene_events',%s)",(str(scene_id),))
        return row["id"]
    def enqueue(self,scene_id,from_stage):
        with self.connect() as conn:
            scene=self.get_scene(scene_id,conn,True);self.assert_idle(scene_id,conn)
            if scene["status"] not in ("uploaded","ready","failed"):
                raise SceneError("SCENE_NOT_UPLOADED","Upload files before processing",409)
            job_id=uuid.uuid4()
            conn.execute("INSERT INTO jobs(id,scene_id,from_stage) VALUES(%s,%s,%s)",(job_id,scene_id,from_stage))
            conn.execute("UPDATE scenes SET status='processing',failure=NULL WHERE id=%s",(scene_id,))
            self.event(conn,scene_id,"status",{"status":"processing"})
            conn.execute("SELECT pg_notify('jobs_queued',%s)",(str(job_id),))
            return str(job_id)
    def objects(self,scene_id):
        with self.connect() as conn:
            self.get_scene(scene_id,conn)
            return conn.execute("SELECT id,label,label_vi,box,attributes,best_views FROM objects WHERE scene_id=%s ORDER BY id",(scene_id,)).fetchall()
