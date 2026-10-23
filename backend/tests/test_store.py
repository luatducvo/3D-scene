"""Scene Store transitions against the disposable Postgres, called directly rather than over HTTP."""

import os

import numpy as np
import pytest
from scene_core.contracts import STAGES
from scene_core.domain import SceneObject
from scene_core.errors import SceneError
from scene_core.results import EMBEDDING_DIM, PublishedScene
from scene_stages.fake import OBJECTS
from scene_store import SceneStore

pytestmark = pytest.mark.db


@pytest.fixture
def store():
    return SceneStore(os.environ["TEST_DATABASE_URL"])


def uploaded(store):
    scene = store.create_scene("Store room")
    with store.uploading(scene):
        pass
    return scene


def claimed(store, scene):
    """Enqueue and claim the Scene's Job; other tests leave no queued Jobs behind."""
    job_id = store.enqueue(scene)
    job = store.claim()
    assert str(job["id"]) == job_id
    return job


def published(scene):
    return PublishedScene(
        [SceneObject.model_validate(o) for o in OBJECTS],
        {o["id"]: np.full(EMBEDDING_DIM, 0.1, dtype=np.float32) for o in OBJECTS}
    )


def live(store, scene):
    return [(event, data) for _, event, data in store.events_since(scene, 0)]


def test_a_job_runs_every_stage_publishes_and_replays_as_it_happened(store):
    scene = uploaded(store)
    job = claimed(store, scene)
    with pytest.raises(SceneError) as busy:
        store.enqueue(scene)
    assert busy.value.code == "SCENE_BUSY"
    for stage in STAGES:
        store.stage_started(job, stage, f"{stage}.fake")
        store.stage_progress(job, stage, {"done": 1, "total": 1, "unit": "step"})
        store.stage_done(job, stage, {"stage": stage})
    store.publish(job, published(scene))
    with store.connect() as conn:
        assert (
            conn.execute("SELECT status FROM jobs WHERE id=%s", (job["id"],)).fetchone()["status"]
            == "done"
        )
        assert [
            r["id"]
            for r in conn.execute("SELECT id FROM objects WHERE scene_id=%s ORDER BY id", (scene,))
        ] == ["chair-1", "table-1"]
    assert store.get_scene(scene)["status"] == "ready"
    events = live(store, scene)
    assert events[0] == ("status", {"status": "processing"}) and events[-1] == (
        "status",
        {"status": "ready"},
    )
    # Replay sends each Stage Run's final stage event and its progress, with the same shapes as live.
    snapshot = store.snapshot(scene)
    assert snapshot.status == "ready" and snapshot.cursor > 0
    final = {data["stage"]: data for event, data in events if event == "stage"}
    replay_stages = [data for event, data in snapshot.events if event == "stage"]
    assert [data["stage"] for data in replay_stages] == list(STAGES)
    assert all(data == final[data["stage"]] for data in replay_stages)
    assert next(e for e in snapshot.events if e[0] == "progress") == (
        "progress",
        {"stage": "ingest", "done": 1, "total": 1, "unit": "step"},
    )
    assert snapshot.events[-1] == ("status", {"status": "ready"})


def test_a_new_job_starts_without_the_previous_jobs_stage_runs(store):
    scene = uploaded(store)
    job = claimed(store, scene)
    store.stage_started(job, "ingest", "ingest.fake")
    store.stage_done(job, "ingest", {"stage": "ingest"})
    store.fail(job, "recon", "TEST", "stop here")
    claimed_again = claimed(store, scene)
    snapshot = store.snapshot(scene)
    assert snapshot.events == [("status", {"status": "processing"})]
    store.fail(claimed_again, None, "TEST", "done with this Job")


def test_a_stage_failure_fails_the_stage_run_job_and_scene_with_one_shape(store):
    scene = uploaded(store)
    job = claimed(store, scene)
    store.stage_started(job, "ingest", "ingest.fake")
    failure = store.fail(
        job,
        "ingest",
        "NOT_ENOUGH_KEYFRAMES",
        "Too few sharp Frames",
        {"rejection_counts": {"blur": 3}},
    )
    assert failure == {
        "stage": "ingest",
        "code": "NOT_ENOUGH_KEYFRAMES",
        "message": "Too few sharp Frames",
        "details": {"rejection_counts": {"blur": 3}},
    }
    assert store.get_scene(scene)["failure"] == failure
    stage_event, status_event = live(store, scene)[-2:]
    assert (
        stage_event[1]["status"] == "failed"
        and stage_event[1]["error"] == failure
        and stage_event[1]["algorithm"] == "ingest.fake"
    )
    assert status_event == ("status", {"status": "failed", "error": failure})
    assert store.snapshot(scene).events[-1] == status_event


def test_a_publication_failure_names_publish(store):
    scene = uploaded(store)
    job = claimed(store, scene)
    assert store.fail(job, None, "RESULTS_INVALID", "missing objects")["stage"] == "publish"
    assert store.get_scene(scene)["status"] == "failed"
    again = claimed(store, scene)  # a failed Scene can be processed again
    store.fail(again, None, "TEST", "done with this Job")


def test_recovery_fails_jobs_a_dead_worker_left_running(store):
    scene = uploaded(store)
    job = claimed(store, scene)
    store.stage_started(job, "embed", "embed.fake")
    failures = [f for f in store.recover_interrupted() if f["job_id"] == str(job["id"])]
    assert [(f["stage"], f["code"]) for f in failures] == [("embed", "WORKER_INTERRUPTED")]
    assert store.get_scene(scene)["status"] == "failed"
    assert store.snapshot(scene).events[0][1]["status"] == "failed"


def test_uploads_hold_the_scene_and_only_mark_it_uploaded_when_they_finish(store):
    scene = store.create_scene("Uploads")
    with pytest.raises(RuntimeError):
        with store.uploading(scene):
            raise RuntimeError("Target unavailable")
    assert store.get_scene(scene)["status"] == "created"
    with store.uploading(scene):
        pass
    assert store.get_scene(scene)["status"] == "uploaded"
    job = claimed(store, scene)
    with pytest.raises(SceneError) as busy, store.uploading(scene):
        pass
    assert busy.value.code == "SCENE_BUSY"
    store.fail(job, None, "TEST", "done with this Job")
    with pytest.raises(SceneError) as locked, store.uploading(scene):
        pass
    assert locked.value.code == "SCENE_LOCKED"


def test_delete_refuses_an_active_job_and_removes_the_scene(store):
    scene = uploaded(store)
    job = claimed(store, scene)
    with pytest.raises(SceneError) as busy:
        store.delete_scene(scene)
    assert busy.value.code == "SCENE_BUSY"
    store.fail(job, None, "TEST", "done with this Job")
    store.delete_scene(scene)
    with pytest.raises(SceneError) as missing:
        store.get_scene(scene)
    assert missing.value.code == "SCENE_NOT_FOUND"
