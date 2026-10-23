# API

`backend/services/scene-api/src/scene_api/`. The contract is `backend/openapi/openapi.json`; errors follow [docs/agents/failures.md](../agents/failures.md).

## Endpoints

All under `/api/v1/scenes`.

| Request | Does |
| --- | --- |
| `POST /` `{name}` | create a Scene (`created`) |
| `GET /` | list Scenes, newest first |
| `GET /{scene}` | Scene with Stage Runs, `assets` URLs, `failure`, `ingest_report` |
| `DELETE /{scene}` | delete an idle Scene, its Publications and, in the background, its Target Workspace |
| `POST /{scene}/uploads` (multipart `files`) | store photos or one video on the Target |
| `POST /{scene}/process` | queue a Job; returns `job_id` |
| `GET /{scene}/events` | SSE progress stream |
| `GET /{scene}/objects`, `GET /{scene}/objects/{object}` | Objects of the current Publication |
| `GET /{scene}/search?q=` | Search Hits |
| `POST /{scene}/queries` `{question, camera?}` | SSE answer stream |
| `GET /{scene}/publications/{job}/files/{path}` | a public file of a Publication |

## Scene lifecycle

`created` → upload → `uploaded` → process → `processing` → `ready` or `failed`. A `ready` or `failed` Scene can be processed again.

| Action | Allowed when | Otherwise |
| --- | --- | --- |
| upload | `created` or `uploaded`, no active Job | `SCENE_LOCKED`, `SCENE_BUSY` |
| process | `uploaded`, `ready` or `failed`, no active Job | `SCENE_NOT_UPLOADED`, `SCENE_BUSY` |
| delete | no active Job | `SCENE_BUSY` |
| ask a question | `ready` | `SCENE_NOT_READY` |

Uploads accept `.jpg .jpeg .png .webp .heic` photos or one `.mp4 .mov .mkv .webm` video, never both and never a second video (`INVALID_UPLOAD`, `UNSUPPORTED_MEDIA`). Each stored name is the sanitised original stem plus a random suffix, so ingest keeps capture order.

## Progress events

`GET /events` first replays the Scene's state, then, while it is `processing`, streams new `scene_events` rows until a `ready` or `failed` status. Replayed and live events have the same shapes:

- `stage`: one Stage Run's `stage`, `algorithm`, `status`, `manifest`, `error`, `started_at`, `updated_at`
- `progress`: `stage`, `done`, `total`, `unit`
- `status`: the Scene's `status`, plus `error` (the failure) when failed

Only live events carry an SSE `id`.

## Publication files

`assets` gives `mesh_url` (`mesh/mesh.glb`), `points_url` (`mesh/points.ply`) and `membership_url` (`graph/membership.bin`), each a URL that names the Publication, so a new Job's files never reuse an old URL. Only `mesh/` and `graph/membership.bin` are public (`SceneResults.PUBLIC`); everything else, including the Scene Graph, is served through the Objects endpoints.

## Search

The query is embedded on the Target with the embed Stage's Algorithm and compared with each Object's embedding by cosine similarity in pgvector. A label match is the query containing the Object's label, or the reverse.

- `GET /search` returns every label match (score = similarity + 1), then the other Objects within `SEARCH_MARGIN` (default 0.05) of the best similarity, at most 10 hits in all. Each hit carries `score` and `raw_similarity`.
- The QA tools rank the same way but keep every Object scoring above 0.15, uncut, so counts stay whole.

## Question answering

`qa.py`. `QAAgent` sends the question to an OpenAI-compatible chat endpoint (`LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`) with the tools of `SceneTools`: `find_objects`, `count_objects`, `get_object`, `get_room_info`, `measure_distance`, `get_relations`, `relative_direction`, plus `final_answer`. Each question is independent and answered in English.

- Every number in the answer must appear in a tool result or the question, at the precision stated (metres may be restated in centimetres or millimetres). The first ungrounded answer is sent back once; a second fails with `QA_UNGROUNDED`.
- More than six steps fails with `QA_STEP_LIMIT`.
- `relative_direction` from the user's viewpoint needs the `camera` sent with the question.
- The stream sends `tool` events, one `delta`, then `final` with `answer`, `object_ids` and `evidence` (the first Best View Frame id of each Object; Frame images are not published).

## Database

`backend/migrations/001_init.sql` is the whole schema. Postgres runs it once, when its data volume is created (Compose mounts the folder as `docker-entrypoint-initdb.d`); the API and the worker never change the schema. A schema change edits this file and resets the database (`uv run main.py reset`).

| Table | Holds |
| --- | --- |
| `scenes` | name, status, `failure`, `room` (floor, ceiling, area), `publication` (Job id) |
| `jobs` | status `queued`, `running`, `done`, `failed`; at most one queued or running per Scene |
| `stage_runs` | one row per Stage of the latest Job: Algorithm, status, Manifest, error, progress, times |
| `objects` | the current Publication's Objects with a `vector(1024)` embedding (HNSW cosine index) |
| `relations` | the current Publication's Relations |
| `scene_events` | the progress outbox read by `GET /events` |

## Object membership file

`graph/membership.bin`, written by the graph Stage, encoded by `scene_core/membership.py` and decoded by `frontend/src/lib/api/membership.ts`. All integers are little-endian `uint32`, and every section starts on a 4-byte boundary so the browser can view each array in place:

```
magic "SCMB" | version 1 | object_count N | point_count | vertex_count | ids_byte_length L
ids: UTF-8 JSON array of the N Object ids, space-padded to L bytes
point_offsets[N + 1]  | point_indices[point_offsets[N]]
vertex_offsets[N + 1] | vertex_indices[vertex_offsets[N]]
```

Object `i` owns `point_indices[point_offsets[i] : point_offsets[i + 1]]`, sorted and unique; vertices work the same way. Points index `mesh/points.ply`, vertices index every primitive of `mesh/mesh.glb` in order. The ids list the Scene Graph's Objects in the same order.
