# Architecture deepening

Five refactors from the 2026-10-17 architecture review. Each one replaces several shallow modules
with one deep module, so callers and tests use a single interface. Terms follow
[CONTEXT.md](../../CONTEXT.md); architecture vocabulary (module, interface, seam, adapter) follows
the codebase-design skill.

## Decisions

### Scene Results (ticket 01)

- `SceneResults` in scene-core, next to `SceneWorkspace`. It reads only files, with no httpx and no
  database. It names the published files, validates the Scene Graph against the embeddings (same
  ids, dimension, finite) before any transaction opens, and answers which paths are public.
- Only `mesh/` and `recon/rgb/` are publicly served, on every Target.
- One `EMBEDDING_DIM = 1024` constant. A test compares it with the `objects.embedding` column type.
- The layout between Stages (Manifests, `OUTPUTS`, `align/manifest.json`) stays out of scope.

### Scene Store (ticket 02)

- `SceneStore` in a new workspace package `scene-store`. It owns every state write: enqueue,
  claim, stage started / done / progress, fail, recover after a crash, publish + ready in one
  transaction, delete Scene. It also owns the `scene_events` outbox. The api's read queries stay in
  the api.
- `Repository` moves out of scene-worker.
- Events have one shape. `stage` and `progress` are separate events, in replay exactly as live.
- Remove skip/rerun residue: `config_hash`, the `skipped` status, `jobs.from_stage` (new migration).
- Tested against real Postgres by calling the module directly, not over HTTP. No in-memory fake.

### Target Workspace (ticket 03, merges review candidates 01, 02 and 03)

- `TargetWorkspace` in a new workspace package `scene-target`. scene-api stops depending on
  scene-worker.
- Built once per runtime from (pipeline, compute, data_dir, ready_timeout). Commands take
  `scene_id`: `put_input`, `list_inputs`, `run_stage`, `replace_results`, `embed_text`, `delete`.
  `invoke` leaves the interface.
- Two adapters: in-process and HTTP. `shared_storage` is removed. The in-process adapter works in a
  directory of its own (for example `DATA_DIR/target/scenes/{id}`) and copies results out like a
  remote Target does.
- `pipeline.yaml` declares `target:` once at the top. The per-Stage `target` field is removed.
- Deleting a Scene deletes its Target Workspace on the current Target only.
- `replace_results`: download to staging → publish + ready in one transaction → rename the
  directories. A failure before commit discards staging, and the earlier results stay untouched.
- Errors cross the seam as `SceneError` with the Algorithm's `code` and `details`. A transport
  failure becomes `COMPUTE_UNAVAILABLE`, and httpx never escapes the module.
- `create_app` and `Runner` accept a ready-built `TargetWorkspace`. Tests pass one backed by
  `TestClient(create_compute_app(...))`. No monkeypatching.
- Remove residue tied to Targets: `reads`/`writes` on the backend seam, `_sync_up` and checksum
  skip, the `ComputeBackend` port and the unused ports (`TextEmbedder`, `LLMClient`, `AgentTool`,
  `Instance3D`), and the `mesh-tsdf` extra of scene-worker.

### Scene progress in the frontend (ticket 04)

- `useSceneProgress(sceneId)` owns replay + live SSE and invalidation. It is tested through the
  hook with MSW streaming events.
- The fake `SceneApi` port and the `NEXT_PUBLIC_API_MODE` switch are removed. `sceneApi` uses
  `typedClient` with one error decoder.
- One `STAGES` constant, type-checked against a Stage enum the backend exports
  (`Literal` from scene-core `STAGES`).

### Viewer (ticket 05, speculative, last)

- A camera module with `goHome()` / `focus(box)` that `Controls` registers on mount. The store
  holds state only.
- One viewer module owns the visible-layer rule (points if available, else mesh) and the bounds,
  taken from the visible layer. Tested with vitest, without WebGL.

## Order

01 → 02 → 03 → 04 → 05. Each ticket uses modules finished earlier.
