# Backend API, events and the QA agent

What `scene-api` exposes and the rules behind it. All routes are in
[scene_api/main.py](../../backend/services/scene-api/src/scene_api/main.py); request and response
models are in [models.py](../../backend/services/scene-api/src/scene_api/models.py).

## Contract rules

- Everything is under `/api/v1`. Swagger UI runs at `http://localhost:8000/docs`.
- **OpenAPI is the source of truth.** `uv run main.py openapi` writes
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
| POST | `/scenes/{id}/uploads` | Multipart photos or one video, sent to the Target's `raw/` several files at once; on failure none of the request's files stay |
| POST | `/scenes/{id}/process` | Queue a Job (no body options) |
| GET | `/scenes/{id}/events` | SSE progress |
| GET | `/scenes/{id}/objects` | Objects with boxes, labels, attributes and best views (Frame id, box, score; no image, [ADR-0008](../adr/0008-frame-images-stay-on-target.md)) |
| GET | `/scenes/{id}/objects/{object_id}` | One Object |
| GET | `/scenes/{id}/search?q=` | Free-text Object search (English or Vietnamese), ranked as in [Search](#search) |
| GET | `/scenes/{id}/messages` | Stored chat history |
| POST | `/scenes/{id}/queries` | `{question, camera?}` → SSE answer stream |
| GET | `/scenes/{id}/publications/{version}/files/{path}` | Serve a public file of one publication ([ADR-0006](../adr/0006-versioned-publication.md)): only `mesh/` and `graph/membership.bin` ([Scene Results](pipeline.md#scene-results)); any other path, invalid Job UUID or removed publication is 404 `FILE_NOT_FOUND`. API responses carry these URLs for the current version. Unversioned results are not served ([ADR-0007](../adr/0007-retire-unversioned-results.md)); a Scene without a publication has no asset URLs. |

## Search

`similarities` embeds the query on the Target (ADR-0005; an unset or unreachable Target is 503
`COMPUTE_UNAVAILABLE`, and the frontend shows its own message for that code) and compares it with
each Object's stored embedding by cosine similarity. For `GET /search`, `rank_search_hits` in
[main.py](../../backend/services/scene-api/src/scene_api/main.py) then keeps:

- every **label match** (the query contains the Object's `label` or `label_vi`, or the reverse),
  scored similarity + 1, so they rank first;
- other Objects whose similarity is positive and within `SEARCH_MARGIN` (environment variable,
  default 0.05) of the best similarity in the Scene, best first, while fewer than 10 hits are kept.

Text-to-image cosines of the embedding model sit in a narrow band, so an absolute threshold kept most
of the room; the margin keeps only the Objects close to the best match, and label matches are never
cut. This cut is for `GET /search` only. `find_objects` and `count_objects` in the QA agent rank
with `rank_tool_hits` instead, uncut so a count stays whole: every Object whose similarity, plus 1
for a label match, exceeds 0.15 (`TOOL_MIN_SCORE`), best first.

## Scene assets

`GET /scenes/{id}` returns `assets` (`SceneAssets`) with three absolute URLs into the current
publication, each `null` when the Scene has no publication or the file is absent:

| Field | File | Content |
|---|---|---|
| `points_url` | `mesh/points.ply` | Binary little-endian PLY, float32 `x y z` and uchar `red green blue`, aligned frame (z-up, m) |
| `mesh_url` | `mesh/mesh.glb` | Binary glTF from the mesh Stage, positions in the aligned frame |
| `membership_url` | `graph/membership.bin` | Which points and mesh vertices belong to each Object ([below](#object-membership)); `null` for a Scene published before membership existed, which must be reprocessed to get it |

### Object membership

Written by the graph Stage (see the graph row in [pipeline.md](pipeline.md#stage-contracts)) and
defined by `ObjectMembership` in
[membership.py](../../backend/packages/scene-core/src/scene_core/membership.py). It is served as
`application/octet-stream`. Every integer is a little-endian uint32 and every section starts at a
multiple of 4 bytes, so each array is a zero-copy `Uint32Array` view of the response buffer:

| Byte offset | Field |
|---|---|
| 0 | magic, the ASCII bytes `SCMB` |
| 4 | `version`, 1 |
| 8 | `object_count` N |
| 12 | `point_count`: vertices of `points.ply` when it was written |
| 16 | `vertex_count`: POSITION entries of `mesh.glb` when it was written |
| 20 | `ids_byte_length` L, a multiple of 4 |
| 24 | ids: UTF-8 JSON array of the N Object ids, padded with spaces to L bytes |
| 24 + L | `point_offsets`, N + 1 values |
| … | `point_indices`, `point_offsets[N]` values |
| … | `vertex_offsets`, N + 1 values |
| … | `vertex_indices`, `vertex_offsets[N]` values; the file ends here |

Object `ids[i]` owns `point_indices[point_offsets[i] .. point_offsets[i+1])` and
`vertex_indices[vertex_offsets[i] .. vertex_offsets[i+1])`, each sorted ascending without
repeats. The ids are the Scene Graph's Object ids in the Scene Graph's order. A point index is the
vertex's position in `points.ply` file order, which is the order of the `position` attribute that
three.js `PLYLoader` builds. A mesh vertex index counts the POSITION accessors of every primitive of
every mesh in the glTF's `meshes` order; the mesh Stage writes one primitive, so it is the index into
`geometry.attributes.position` of the one mesh `GLTFLoader` (drei `useGLTF`) returns. A point or
vertex may be listed under several Objects (a door handle and the wardrobe it is on) or under none.

The browser fetches it from the URL with `fetch(url)` and `response.arrayBuffer()` (CORS allows the
frontend origin) and decodes it like this:

```ts
function decodeMembership(buffer: ArrayBuffer) {
  const head = new DataView(buffer);
  const magic = String.fromCharCode(...new Uint8Array(buffer, 0, 4));
  if (magic !== "SCMB" || head.getUint32(4, true) !== 1) throw new Error("Unsupported membership file");
  const count = head.getUint32(8, true), idsLength = head.getUint32(20, true);
  const ids: string[] = JSON.parse(new TextDecoder().decode(new Uint8Array(buffer, 24, idsLength)));
  let offset = 24 + idsLength;
  const take = (length: number) => {
    const view = new Uint32Array(buffer, offset, length);
    offset += 4 * length;
    return view;
  };
  const pointOffsets = take(count + 1), pointIndices = take(pointOffsets[count]);
  const vertexOffsets = take(count + 1), vertexIndices = take(vertexOffsets[count]);
  return {
    ids,
    pointCount: head.getUint32(12, true),
    vertexCount: head.getUint32(16, true),
    points: (i: number) => pointIndices.subarray(pointOffsets[i], pointOffsets[i + 1]),
    vertices: (i: number) => vertexIndices.subarray(vertexOffsets[i], vertexOffsets[i + 1]),
  };
}
```

`point_count` and `vertex_count` let the viewer check that the loaded `points.ply` and `mesh.glb`
belong to the same publication. Size is 4 bytes per membership entry plus 8 bytes per Object; a
Scene of ~600 k points is a few MB at most.

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
 "evidence": [{"object_id": "o12", "frame_id": "0042"}]}
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
`final_answer` call listing the Object ids, and the API attaches each Object's best Frame id as evidence (no image, [ADR-0008](../adr/0008-frame-images-stay-on-target.md)) and
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
| `count_objects` | Counts every tool hit ([Search](#search)): label matches plus Objects with similarity above 0.15, uncut |
| `get_object` | Label, size, attributes |
| `get_room_info` | Floor area, ceiling height, Object counts by label |
| `measure_distance` | Surface-to-surface or center-to-center, meters |
| `get_relations` | Stored Relations of an Object |
| `relative_direction` | Left/right/front/behind from the viewer camera or an Object's front |
