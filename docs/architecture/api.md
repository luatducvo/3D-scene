# Backend API, events and the QA agent

What `scene-api` exposes and the rules behind it. All routes are in
[scene_api/main.py](../../backend/services/scene-api/src/scene_api/main.py); request and response
models are in [models.py](../../backend/services/scene-api/src/scene_api/models.py).

## Contract rules

- Everything is under `/api/v1`. Swagger UI runs at `http://localhost:8000/docs`.
- **OpenAPI is the source of truth.** `uv run tasks.py openapi` writes
  [backend/openapi/openapi.json](../../backend/openapi/openapi.json) from the pydantic models; it is
  committed. The frontend copies it and generates its types with `npm run api:sync`.
- Errors are `{"error": {"code", "message"}}` with a matching HTTP status and an UPPER_SNAKE_CASE
  code. Codes come from `SceneError` raises in the API and from Stage failures in the worker.
- File URLs are absolute and issued by the API; clients never build storage paths.
- Units are SI; coordinates are z-up with the floor at z = 0.
- Single user, local: no authentication, ports bound to `127.0.0.1`, `CORS_ORIGINS` lists the frontend.

## Scene lifecycle

Status flow: `created → uploaded → processing → ready | failed`. Processing again (always from the
first Stage) is allowed from `ready` or `failed`.

| Rule | Response |
|---|---|
| Upload outside `created` / `uploaded` | 409 `SCENE_LOCKED`: a Scene's capture never changes after processing |
| Process, upload or delete while a Job is queued or running | 409 `SCENE_BUSY` (one active Job per Scene, enforced by a partial unique index) |
| Upload or search while the Target is unset or unreachable | 503 `COMPUTE_UNAVAILABLE` |
| Mixing photos and a video, or more than one video | 400 `INVALID_UPLOAD` |
| Asking before the Scene is `ready` | 409 `SCENE_NOT_READY` |

Deleting a Scene removes its database rows, the local Scene folder and its Workspace on every
non-shared remote Target (an unreachable Target is only logged).

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/scenes` | Create `{name}` → `{id}` |
| GET | `/scenes` | List Scenes with status |
| GET | `/scenes/{id}` | Status, Stage Runs, ingest report, failure, asset URLs |
| DELETE | `/scenes/{id}` | Delete the Scene everywhere |
| POST | `/scenes/{id}/uploads` | Multipart photos or one video, streamed to the Target's `raw/` |
| POST | `/scenes/{id}/process` | Queue a Job (no body options) |
| GET | `/scenes/{id}/events` | SSE progress |
| GET | `/scenes/{id}/objects` | Objects with boxes, labels, attributes, evidence URLs |
| GET | `/scenes/{id}/objects/{object_id}` | One Object |
| GET | `/scenes/{id}/search?q=` | Free-text Object search (English or Vietnamese) |
| GET | `/scenes/{id}/messages` | Stored chat history |
| POST | `/scenes/{id}/queries` | `{question, camera?}` → SSE answer stream |
| GET | `/scenes/{id}/publications/{version}/files/{path}` | Serve a public file of one publication ([ADR-0006](../adr/0006-versioned-publication.md)): only `mesh/` and `recon/rgb/` ([Scene Results](pipeline.md#scene-results)); any other path, or a removed publication, is 404 `FILE_NOT_FOUND`. API responses carry these URLs for the current version; `legacy` names results published before versioning |

## SSE events

**Progress** (`GET …/events`, read with `EventSource`). On connect the API replays the current
state from `SceneStore.snapshot`: one `stage` event per Stage Run, followed by a `progress` event
when the Stage Run has reported progress, then a `status` event. It then streams new rows of the
`scene_events` table until the Scene is `ready` or `failed`. Replay and live events have the same
shapes; a `stage` event never carries progress, and only live events have an SSE `id`:

```jsonc
{"type": "stage", "stage": "segment", "algorithm": "segment.sam3", "status": "running", "manifest": null, "error": null, "started_at": "…", "updated_at": "…"}
{"type": "progress", "stage": "segment", "done": 48, "total": 155, "unit": "frame"}
{"type": "stage", "stage": "segment", "status": "done", "manifest": {…}}
{"type": "status", "status": "ready"}
{"type": "status", "status": "failed", "error": {"stage", "code", "message", "details"}}
```

Stages that report progress: ingest (image), align, mesh and segment (frame), lift (mask), embed
and attributes (object). recon and graph report nothing; the UI shows an indeterminate bar.
Stage Runs belong to the latest Job: enqueueing deletes the previous ones, so a rerun starts with
none. A Stage Run is `running`, `done` or `failed`; migration 003 rewrote older `skipped` rows to `done`.

**Answers** (`POST …/queries`, read with `fetch` and a stream):

```jsonc
{"type": "tool", "tool": "measure_distance"}
{"type": "delta", "delta": "The table is about "}
{"type": "final", "answer": "…", "object_ids": ["o12", "o7"],
 "evidence": [{"object_id": "o12", "frame_id": "…", "image_url": "http://localhost:8000/api/v1/scenes/…"}]}
```

Because the stream has already returned HTTP 200, a failure mid-answer arrives as an `error` event
carrying `{"error": {"code", "message"}}` (for example `COMPUTE_UNAVAILABLE` or `QA_STEP_LIMIT`).

## Database

Migrations in [backend/migrations/](../../backend/migrations/) run in name order when the api or
worker starts: `SceneStore.migrate` applies each file not yet recorded in `schema_migrations`, under
an advisory lock so both processes can start together. Files stay idempotent, because Compose also
runs them once when it creates the Postgres volume. The folder is `MIGRATIONS_DIR`, or found in the
source layout when unset; configuration files likewise come from `CONFIG_DIR`. Every write goes through
`SceneStore`; the api's own SQL only reads. Tables: `scenes` (status, `failure`, published `room` info), `jobs`, `stage_runs`
(status, Manifest, progress), `scene_events`, `objects` (with `embedding vector(1024)` and an HNSW
cosine index), `relations`, `messages`. The embedding dimension is `EMBEDDING_DIM` in
[results.py](../../backend/packages/scene-core/src/scene_core/results.py); a test fails when it and
the column type differ, so changing the model to another dimension needs both a migration and that
constant. Search rejects a query vector of another length with `EMBEDDING_DIMENSION_MISMATCH`.

## QA agent

[qa.py](../../backend/services/scene-api/src/scene_api/qa.py). The LLM plans and phrases; every
number comes from a tool. `QAAgent` runs a function-calling loop of at most 6 steps against any
OpenAI-compatible endpoint (`LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`; without them, asking
returns 503 `LLM_NOT_CONFIGURED`). It answers in the question's language, ends with a
`final_answer` call listing the Object ids, and the API attaches one evidence image per Object and
stores the exchange in `messages`. Tests use `ScriptedLLM`.

Grounding is enforced, not only requested. Both LLM adapters return the same reply: tool calls
(with `final_answer` among them) or plain content, which counts as a final answer. `QAAgent` runs
every other tool in a reply before reading its `final_answer`, and collects every number the tools
returned this question (plus numbers in the question itself). A final answer may state only those
numbers, rounded half up to the precision it uses, also in centimeters or millimeters. The first
answer with an unsupported number is sent back to the model with the numbers named; a second one
ends the stream with `QA_UNGROUNDED`. Integers are compared at whole-number precision, so the check
catches invented measurements, not every loosely rounded count.

| Tool (`SceneTools`) | Behavior |
|---|---|
| `find_objects` | Embedding search on the Target plus label matching |
| `count_objects` | `find_objects` with a similarity threshold |
| `get_object` | Label, size, attributes, evidence image URLs |
| `get_room_info` | Floor area, ceiling height, Object counts by label |
| `measure_distance` | Surface-to-surface or center-to-center, meters |
| `get_relations` | Stored Relations of an Object |
| `relative_direction` | Left/right/front/behind from the viewer camera or an Object's front |
