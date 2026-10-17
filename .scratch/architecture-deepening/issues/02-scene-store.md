# 02: Scene Store module

**What to build:** A `SceneStore` module in a new workspace package `scene-store` that owns every
write to Scene, Job, Stage Run and Object state, together with the `scene_events` outbox. Today
these transitions are raw SQL spread over runner.py (the fail block is written twice, and the
Stage Run upsert is one 600-character line), repository.py (which holds `enqueue` and `objects`,
used only by the api) and main.py. See [spec](../spec.md#scene-store-ticket-02).

**Blocked by:** 01

**Status:** implemented

- [x] scene-store package with `SceneStore`. `Repository` leaves scene-worker, and the api and the
      worker both depend on scene-store.
- [x] Operations: enqueue, claim, stage started / done / progress, fail, recover interrupted Jobs,
      publish + ready in one transaction (taking validated `SceneResults` content), delete Scene. The
      runner contains no SQL.
- [x] The api's read queries (Scene list and detail, Objects, chat) stay in the api.
- [x] Events have one shape. `stage` and `progress` are separate events, and the SSE replay of Stage
      Runs emits a `stage` event followed, when present, by a flat `progress` event, the same as live.
- [x] New migration drops `stage_runs.config_hash` and `jobs.from_stage`. `skipped` is removed from
      `StageRun.status`, StageStepper, its test and the mock handlers.
- [x] Module tests run against the disposable Postgres by calling `SceneStore` directly. The
      crashed-worker test uses `SceneStore` instead of raw SQL.
- [x] `uv run tasks.py openapi`, then `npm run api:sync`. docs/architecture/pipeline.md and api.md
      updated.
