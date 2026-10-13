# 06: Process a Scene with the fake pipeline

**What to build:** Pressing Process runs all nine Stages end-to-end on CPU using fake Algorithms. Introduces the Postgres Job queue, the scene-worker with the pipeline runner and in-process backend, the entry-point registry, the Executor in scene-core, pipeline configuration loading, and one fake Algorithm per Stage writing contract-valid outputs. Enforces the Scene lifecycle rules.

**Blocked by:** 05

**Status:** done

- [ ] Pressing Process on an `uploaded` Scene enqueues a Job; the worker claims it; the Scene goes `processing` then `ready`; a Stage Run is recorded for each of the nine Stages with algorithm and config hash.
- [ ] Every fake Stage writes its documented Workspace layout and Manifest.
- [ ] A Stage that raises makes the Scene `failed`, with the Stage and error message visible in the Scene detail.
- [ ] While a Job is queued or running, Process, upload and delete return 409 `SCENE_BUSY` (enforced in the database, not only in code).
- [ ] Upload to a Scene that is `processing`, `ready` or `failed` returns 409 `SCENE_LOCKED`.
- [ ] Available Algorithms are discovered from installed entry points without importing heavy libraries.
- [ ] API tests (primary seam, real worker, fake pipeline config) cover success, failure and the 409 rules.
