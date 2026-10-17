# 06: Stage Runs belong to the current Job

**What to build:** `SceneStore.enqueue` deletes the Scene's Stage Runs in the same transaction that
queues the Job. Today the previous Job's `done` Stage Runs stay until the new Job reaches each Stage,
so a rerun shows stale `Done` Stages and a failure mixes Stage Runs from two Jobs (audit R6).

**Blocked by:** 02

**Status:** implemented

- [x] Enqueue removes the Scene's `stage_runs` rows; the replay right after enqueue has no `stage`
      events, only `status: processing`.
- [x] A Store test and a REST test (rerun, then read the Scene before the worker runs) show no
      Stage Runs from the previous Job.
- [x] docs/architecture/pipeline.md and api.md say Stage Runs describe the latest Job only.
