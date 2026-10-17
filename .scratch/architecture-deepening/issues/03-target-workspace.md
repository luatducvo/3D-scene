# 03: Target Workspace module

**What to build:** A `TargetWorkspace` module in a new workspace package `scene-target`, which
becomes the only way api and worker reach a Scene's Target Workspace. Today the api builds two
separate backends (`input_store`, `query_embedder`) by importing `scene_worker.container`.
`HttpBackend` branches on `shared_storage` in five methods. Deleting a Scene loops over every
Target. This ticket also fixes two bugs:

- Reprocessing a Scene on the `cpu` or `local_gpu` Target deletes the served mesh and images before
  the Job succeeds (runner.py:41).
- On HTTP Targets, Algorithm error codes and details are replaced by `COMPUTE_FAILED`
  (http.py:142, server.py:90).

**Status:** needs-live-check — automated tests pass; a live GPU run should confirm the HTTP adapter and the local_gpu DATA_DIR change

- [x] scene-target package. scene-api no longer depends on scene-worker or imports httpx.
- [x] `TargetWorkspace` is built once per runtime from (pipeline, compute, data_dir, ready_timeout)
      and exposes `put_input`, `list_inputs`, `run_stage`, `replace_results`, `embed_text` and
      `delete`, each taking `scene_id`. `invoke` and `reads`/`writes` are gone from the interface.
- [x] Two adapters, in-process and HTTP. `shared_storage` is removed from config, code and
      compute.yaml. The in-process adapter works under its own root (for example
      `DATA_DIR/target/scenes/{id}`) and copies results out like the HTTP adapter.
- [x] `pipeline.yaml`, `pipeline.fake.yaml` and `pipeline.fake-gpu.yaml` declare `target:` once.
      `StageConfig.target` and the split-Targets check and test are removed.
- [x] `replace_results`: download to staging, then publish + ready in one `SceneStore`
      transaction, then rename directories. A test on the in-process adapter and one on HTTP show
      that a failed reprocess leaves the earlier mesh, images and Objects untouched.
- [x] Scene deletion deletes the Target Workspace on the current Target only.
- [x] compute server returns `code`, `message` and `details`. The HTTP adapter raises `SceneError`
      with them. Transport failures raise `SceneError("COMPUTE_UNAVAILABLE")`. A test sends
      `NOT_ENOUGH_KEYFRAMES` with details across the HTTP seam. The api's three
      `(ComputeError, httpx.TransportError)` handlers are gone.
- [x] `create_app` and `Runner` accept a built `TargetWorkspace`. Tests pass one backed by
      `TestClient(create_compute_app(...))`. No monkeypatching of `container` and no assignment to
      `app.state.storage` or `app.state.embedder`.
- [x] Removed: `_sync_up` and the checksum-skip test, `ComputeBackend`, `TextEmbedder`, `LLMClient`,
      `AgentTool`, `Instance3D`, the per-Stage `Registry().resolve` in the runner, and the
      `mesh-tsdf` extra of scene-worker.
- [x] docs/architecture/compute.md, pipeline.md, overview.md and extending.md updated.
      docs/SPEC.md seams section no longer names skip/force or checksum skip.

## Comments

- 2026-10-17: Stage outputs are still cleared with `OUTPUTS` from contracts.py, not with each
  Algorithm's `writes`: resolving Algorithms in the api or worker is what this ticket removed.
  `TargetWorkspace.delete` removes only the Target Workspace; the api removes the published copy.
  The local Compose `scene-compute` now sets `DATA_DIR=/data/target`. The root workspace installs
  `scene-stages[mesh-tsdf]` for the mesh tests, since scene-worker no longer pulls that extra.
