"""Scene Store: every write to Scene, Job, Stage Run, Object and chat state, and the scene_events outbox.

Each transition commits its rows and its events in one transaction. Read queries for the api stay in
the api; the event stream is read here because the Store owns the event shapes.
"""

import uuid
from contextlib import contextmanager
from typing import NamedTuple

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from scene_core.contracts import STAGES
from scene_core.errors import SceneError
from scene_core.resources import backend_folder
from scene_core.results import PublishedScene

# Any constant: it only has to be the same in every process migrating this database.
MIGRATION_LOCK = 7231


def stage_event(run):
    """A `stage` event: the Stage Run's state, without progress, in replay exactly as live."""
    return {
        **{k: run[k] for k in ("stage", "algorithm", "status", "manifest", "error")},
        **{k: run[k].isoformat() if run[k] else None for k in ("started_at", "updated_at")},
    }


def progress_event(stage, progress):
    return {"stage": stage, **progress}


def status_event(status, error=None):
    return {"status": status, **({"error": error} if error else {})}


class Snapshot(NamedTuple):
    status: str
    events: list[tuple[str, dict]]
    cursor: int


class SceneStore:
    def __init__(self, url: str):
        self.url = url

    def connect(self):
        return psycopg.connect(self.url, row_factory=dict_row)

    def migrate(self) -> list[str]:
        """Apply, in name order, each migration not yet recorded in schema_migrations; return their names.

        The api and the worker both call this at start; an advisory lock lets one apply while the other waits.
        """
        folder = backend_folder("migrations", "MIGRATIONS_DIR")
        applied = []
        with self.connect() as conn:
            conn.execute("SELECT pg_advisory_xact_lock(%s)", (MIGRATION_LOCK,))
            conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations(name text PRIMARY KEY,applied_at timestamptz NOT NULL DEFAULT now())"
            )
            done = {row["name"] for row in conn.execute("SELECT name FROM schema_migrations")}
            for migration in sorted(folder.glob("*.sql")):
                if migration.name in done:
                    continue
                conn.execute(migration.read_text())
                conn.execute("INSERT INTO schema_migrations(name) VALUES(%s)", (migration.name,))
                applied.append(migration.name)
        return applied

    def get_scene(self, scene_id, conn=None, lock=False):
        if conn is None:
            with self.connect() as own:
                return self.get_scene(scene_id, own, lock)
        row = conn.execute(
            "SELECT * FROM scenes WHERE id=%s" + (" FOR UPDATE" if lock else ""), (scene_id,)
        ).fetchone()
        if row is None:
            raise SceneError("SCENE_NOT_FOUND", "Scene not found", 404)
        return row

    def _assert_idle(self, scene_id, conn):
        if conn.execute(
            "SELECT 1 FROM jobs WHERE scene_id=%s AND status IN ('queued','running')", (scene_id,)
        ).fetchone():
            raise SceneError("SCENE_BUSY", "Scene has an active Job", 409)

    def _event(self, conn, scene_id, event, data):
        conn.execute(
            "INSERT INTO scene_events(scene_id,event,data) VALUES(%s,%s,%s)",
            (scene_id, event, Jsonb(data)),
        )
        conn.execute("SELECT pg_notify('scene_events',%s)", (str(scene_id),))

    # Scenes
    def create_scene(self, name: str) -> str:
        scene_id = uuid.uuid4()
        with self.connect() as conn:
            conn.execute("INSERT INTO scenes(id,name) VALUES(%s,%s)", (scene_id, name))
        return str(scene_id)

    @contextmanager
    def uploading(self, scene_id):
        """Hold an idle, unprocessed Scene while its files are stored; it becomes uploaded only if the block finishes."""
        with self.connect() as conn:
            scene = self.get_scene(scene_id, conn, True)
            self._assert_idle(scene_id, conn)
            if scene["status"] not in ("created", "uploaded"):
                raise SceneError("SCENE_LOCKED", "Create a new Scene to upload more files", 409)
            yield
            conn.execute("UPDATE scenes SET status='uploaded' WHERE id=%s", (scene_id,))

    def delete_scene(self, scene_id):
        with self.connect() as conn:
            self.get_scene(scene_id, conn, True)
            self._assert_idle(scene_id, conn)
            conn.execute("DELETE FROM scenes WHERE id=%s", (scene_id,))

    def save_exchange(self, scene_id, question: dict, answer: dict):
        """Store one answered question and its answer; unanswered questions are not kept."""
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO messages(scene_id,role,content) VALUES(%s,'user',%s)",
                (scene_id, Jsonb(question)),
            )
            conn.execute(
                "INSERT INTO messages(scene_id,role,content) VALUES(%s,'assistant',%s)",
                (scene_id, Jsonb(answer)),
            )

    # Jobs
    def enqueue(self, scene_id) -> str:
        with self.connect() as conn:
            scene = self.get_scene(scene_id, conn, True)
            self._assert_idle(scene_id, conn)
            if scene["status"] not in ("uploaded", "ready", "failed"):
                raise SceneError("SCENE_NOT_UPLOADED", "Upload files before processing", 409)
            job_id = uuid.uuid4()
            # Stage Runs describe the latest Job only; the new Job starts with none.
            conn.execute("DELETE FROM stage_runs WHERE scene_id=%s", (scene_id,))
            conn.execute("INSERT INTO jobs(id,scene_id) VALUES(%s,%s)", (job_id, scene_id))
            conn.execute(
                "UPDATE scenes SET status='processing',failure=NULL WHERE id=%s", (scene_id,)
            )
            self._event(conn, scene_id, "status", status_event("processing"))
            conn.execute("SELECT pg_notify('jobs_queued',%s)", (str(job_id),))
            return str(job_id)

    def claim(self):
        """The oldest queued Job, now running; None when the queue is empty."""
        with self.connect() as conn:
            job = conn.execute(
                "SELECT * FROM jobs WHERE status='queued' ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1"
            ).fetchone()
            if job:
                conn.execute(
                    "UPDATE jobs SET status='running',started_at=now() WHERE id=%s", (job["id"],)
                )
            return job

    def stage_started(self, job, stage, algorithm):
        """A running Stage restarts its clock and clears its manifest, error and progress."""
        with self.connect() as conn:
            run = conn.execute(
                "INSERT INTO stage_runs(scene_id,stage,algorithm,status,started_at) VALUES(%s,%s,%s,'running',now()) "
                "ON CONFLICT(scene_id,stage) DO UPDATE SET algorithm=EXCLUDED.algorithm,status='running',manifest=NULL,error=NULL,progress=NULL,started_at=now(),updated_at=now() "
                "RETURNING *",
                (job["scene_id"], stage, algorithm),
            ).fetchone()
            self._event(conn, job["scene_id"], "stage", stage_event(run))

    def stage_done(self, job, stage, manifest: dict):
        with self.connect() as conn:
            run = conn.execute(
                "UPDATE stage_runs SET status='done',manifest=%s,updated_at=now() WHERE scene_id=%s AND stage=%s RETURNING *",
                (Jsonb(manifest), job["scene_id"], stage),
            ).fetchone()
            self._event(conn, job["scene_id"], "stage", stage_event(run))

    def stage_progress(self, job, stage, progress: dict):
        with self.connect() as conn:
            conn.execute(
                "UPDATE stage_runs SET progress=%s WHERE scene_id=%s AND stage=%s",
                (Jsonb(progress), job["scene_id"], stage),
            )
            self._event(conn, job["scene_id"], "progress", progress_event(stage, progress))

    def _fail(self, conn, job, stage, code, message, details):
        failure = {
            "stage": stage or "publish",
            "code": code,
            "message": message,
            "details": details or {},
        }
        if stage:
            run = conn.execute(
                "UPDATE stage_runs SET status='failed',error=%s,updated_at=now() WHERE scene_id=%s AND stage=%s RETURNING *",
                (Jsonb(failure), job["scene_id"], stage),
            ).fetchone()
            if run:
                self._event(conn, job["scene_id"], "stage", stage_event(run))
        conn.execute(
            "UPDATE jobs SET status='failed',finished_at=now(),error=%s WHERE id=%s",
            (Jsonb(failure), job["id"]),
        )
        conn.execute(
            "UPDATE scenes SET status='failed',failure=%s WHERE id=%s",
            (Jsonb(failure), job["scene_id"]),
        )
        self._event(conn, job["scene_id"], "status", status_event("failed", failure))
        return failure

    def fail(self, job, stage, code, message, details=None) -> dict:
        """Fail the Job, its Scene and, when one was running, its Stage Run; stage None means publication failed."""
        with self.connect() as conn:
            return self._fail(conn, job, stage, code, message, details)

    def recover_interrupted(self) -> list[dict]:
        """Fail Jobs left running by a previous worker process, so their Scenes can be processed again.

        Assumes one worker per database, as in the Compose deployment.
        """
        failures = []
        with self.connect() as conn:
            for job in conn.execute("SELECT * FROM jobs WHERE status='running'").fetchall():
                run = conn.execute(
                    "SELECT stage FROM stage_runs WHERE scene_id=%s AND status='running'",
                    (job["scene_id"],),
                ).fetchone()
                failures.append(
                    {
                        "job_id": str(job["id"]),
                        **self._fail(
                            conn,
                            job,
                            run["stage"] if run else None,
                            "WORKER_INTERRUPTED",
                            "The worker restarted while this Job was running; process the Scene again",
                            {},
                        ),
                    }
                )
        return failures

    def publish(self, job, published: PublishedScene):
        """Replace the Scene's Objects, Relations and room, point it at this Job's publication and mark Job and
        Scene ready, in one transaction. The publication folder must already be complete (ADR-0006)."""
        scene_id = job["scene_id"]
        graph = published.graph
        with self.connect() as conn:
            conn.execute("DELETE FROM objects WHERE scene_id=%s", (scene_id,))
            conn.execute("DELETE FROM relations WHERE scene_id=%s", (scene_id,))
            for obj in graph.objects:
                conn.execute(
                    "INSERT INTO objects(scene_id,id,label,label_vi,box,attributes,best_views,embedding) VALUES(%s,%s,%s,%s,%s,%s,%s,%s::vector)",
                    (
                        scene_id,
                        obj.id,
                        obj.label,
                        obj.label_vi,
                        Jsonb(obj.box.model_dump()),
                        Jsonb(obj.attributes),
                        Jsonb([v.model_dump() for v in obj.best_views]),
                        str(published.embeddings[obj.id].tolist()),
                    ),
                )
            for rel in graph.relations:
                conn.execute(
                    "INSERT INTO relations(scene_id,subject_id,predicate,object_id,value) VALUES(%s,%s,%s,%s,%s)",
                    (scene_id, rel.subject_id, rel.predicate, rel.object_id, rel.value),
                )
            conn.execute(
                "UPDATE scenes SET room=%s,publication=%s,status='ready',failure=NULL WHERE id=%s",
                (
                    Jsonb(graph.model_dump(exclude={"objects", "relations"})),
                    str(job["id"]),
                    scene_id,
                ),
            )
            conn.execute(
                "UPDATE jobs SET status='done',finished_at=now() WHERE id=%s", (job["id"],)
            )
            self._event(conn, scene_id, "status", status_event("ready"))

    # Event stream
    def snapshot(self, scene_id) -> Snapshot:
        """The Scene's current state as the events that would have produced it, and the cursor of the last stored event."""
        with self.connect() as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            scene = self.get_scene(scene_id, conn)
            runs = conn.execute(
                "SELECT * FROM stage_runs WHERE scene_id=%s", (scene_id,)
            ).fetchall()
            cursor = conn.execute(
                "SELECT COALESCE(MAX(id),0) AS id FROM scene_events WHERE scene_id=%s", (scene_id,)
            ).fetchone()["id"]
        events = []
        for run in sorted(runs, key=lambda r: STAGES.index(r["stage"])):
            events.append(("stage", stage_event(run)))
            if run["progress"]:
                events.append(("progress", progress_event(run["stage"], run["progress"])))
        events.append(
            (
                "status",
                status_event(
                    scene["status"], scene["failure"] if scene["status"] == "failed" else None
                ),
            )
        )
        return Snapshot(scene["status"], events, cursor)

    def events_since(self, scene_id, cursor: int) -> list[tuple[int, str, dict]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT id,event,data FROM scene_events WHERE scene_id=%s AND id>%s ORDER BY id",
                (scene_id, cursor),
            ).fetchall()
        return [(row["id"], row["event"], row["data"]) for row in rows]
