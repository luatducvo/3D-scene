# Backend guidance

Read [root AGENTS.md](../AGENTS.md) and [current status](../docs/project-status.md)
first. Paths below are relative to `backend/`.

## Code map

| Modules in `src/s3d_app/` | Responsibility |
| --- | --- |
| `api.py`, `cli.py`, `export_openapi.py` | HTTP/SSE, static web serving, CLI, committed API schema |
| `packages.py`, `storage.py`, `pipeline.py` | Independent Package validation, SQLite, durable jobs and stage artifacts |
| `geometry.py`, `instances.py`, `semantics.py`, `objects.py` | Visibility/Structures, masks, labels/embeddings, Object records |
| `graph_stage.py`, `scene_graph.py`, `solver.py`, `retrieval.py` | Graph publication, predicates/Program/Solver, CPU Lookup |
| `ask.py`, `llm.py`, `vision.py` | Sessions, Program generation, guarded wording, Tiebreak and captions |
| `gpu.py`, `models.py` | GPU admission/measurements and verified model assets |

## Contracts and lifecycle

- `packages.py` verifies uploads independently of `tools/scannet_prep.py`; this
  separation is intentional. Keep their implementations independent and verify
  agreement using the shared [Package contract](../docs/s3dpkg-spec.md).
- S1 reads already aligned coordinates. `source_axis_alignment` is provenance.
  Preserve mesh vertex order throughout S1–S6 and Instance mask storage.
- Artifact paths are resolved through `pipeline.artifact_dir`. The v1 string in
  `CONFIG_HASH` preserves the established artifact namespace, not input support.
  Changing it needs a cache/migration plan for existing processed Scenes.
- Reprocessing S1 validates the source Package before deleting artifacts. A
  legacy v1 source fails with a prep/upload instruction while its ready Scene
  stays available. Later stages can reuse the existing aligned S1 artifact.
- Keep no-op, conflict/Replace, active-job checks, restart recovery and failure
  persistence observable through the public API. Write complete artifacts only
  after successful work, using the existing partial/rename convention.
- The GPU lock is process-local. Adding API workers or simultaneous inference
  needs a new coordination design; keep one API process with current coordination.
- Preserve Program validation, Solver authority, Session/Viewpoint persistence,
  Clarify handling and final SSE payloads when changing question handling.
  Compatible cloud endpoints use direct chat calls; read `llm.py`/`vision.py`
  before changing their data disclosure or local model management behavior.

## Verification

From `backend/`, use the frozen `uv` environment and existing tests:

```powershell
uv run --frozen pytest tests/test_import.py
uv run --frozen ruff check . ../tools ../mask3d
uv run --frozen python -m s3d_app.export_openapi --check
```

Choose the test module matching the changed behavior; run the full `pytest` suite
for changes spanning pipeline/storage/question contracts. GPU acceptance needs
real model/VRAM evidence in addition to synthetic tests. Keep test data separate
from the user's Compose volume.

For changed API contracts, from the repository root:

```powershell
uv run --project backend --frozen python -m s3d_app.export_openapi
npm run types:api --prefix frontend
npm run typecheck --prefix frontend
```

Commit schema and generated types together; `frontend` prebuild checks source and
schema hashes. Dependency changes also update `uv.lock`; native Windows and Linux
installation must remain supported (ADR 0003).
