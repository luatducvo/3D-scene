from pathlib import Path

from s3d_app import pipeline
from s3d_app.storage import database


def seed_job(monkeypatch, tmp_path, status="queued"):
    monkeypatch.setenv("S3D_DATA_DIR", str(tmp_path))
    with database() as connection:
        connection.execute("INSERT INTO scenes VALUES ('scan','sha','imported','source.s3dpkg',NULL)")
        cursor = connection.execute("INSERT INTO jobs(scene_id,status) VALUES ('scan',?)", (status,))
    return cursor.lastrowid


def test_failed_fake_stage_stops_job_and_persists_error(monkeypatch, tmp_path):
    job = seed_job(monkeypatch, tmp_path)
    executed = []

    def fail():
        raise RuntimeError("fake model failed")

    monkeypatch.setattr(pipeline, "stage_actions", lambda *_: [
        ("S1", lambda: executed.append("load")), ("S2", fail),
        ("S3", lambda: executed.append("should not run"))])
    pipeline.process_job(job, "scan", Path("source.s3dpkg"))
    with database() as connection:
        result = connection.execute("SELECT status,error FROM jobs WHERE id=?", (job,)).fetchone()
        stages = [tuple(row) for row in connection.execute("SELECT stage,status FROM stage_runs")]
    assert executed == ["load"]
    assert result["status"] == "failed" and "fake model failed" in result["error"]
    assert stages == [("S1", "complete"), ("S2", "failed")]


def test_restart_recovers_a_running_job(monkeypatch, tmp_path):
    job = seed_job(monkeypatch, tmp_path, "running")
    called = []

    def complete(identifier, scene_id, package):
        with database() as connection:
            status = connection.execute("SELECT status FROM jobs WHERE id=?", (identifier,)).fetchone()[0]
            assert status == "queued"
            connection.execute("UPDATE jobs SET status='complete' WHERE id=?", (identifier,))
        called.append(identifier)
        pipeline.STOP.set()

    monkeypatch.setattr(pipeline, "process_job", complete)
    thread = pipeline.start_worker()
    thread.join(timeout=3)
    pipeline.stop_worker(thread)
    assert called == [job]
    pipeline.STOP.clear()
