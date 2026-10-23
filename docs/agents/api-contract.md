# Backend–frontend contract

Things that are defined on both sides, and what has to change together.

## API routes and models

1. Change the route in `backend/services/scene-api/src/scene_api/main.py` or the model in `models.py`.
2. `uv run main.py openapi` (repository root) rewrites `backend/openapi/openapi.json`.
3. `npm run api:sync` (`frontend/`) copies it to `frontend/openapi/openapi.json` and regenerates `src/lib/api/schema.d.ts`.
4. Update the `sceneApi` method in `src/lib/api/http.ts` and the mock handler in `src/lib/api/mock/handlers.ts`, so mock mode stays faithful.

The three generated files are never edited by hand. Frontend types come from `Schemas["<pydantic model name>"]` in `src/lib/api/types.ts`, so renaming a pydantic model renames the frontend type.

## Shared definitions

| Definition | Backend | Frontend |
| --- | --- | --- |
| The eight Stages, in order | `STAGES`, `OUTPUTS` in `scene_core/contracts.py`; every `config/pipeline*.yaml` | `STAGES` in `src/lib/api/types.ts` (typecheck fails when one is missing); stage strings in `messages/en.json` |
| Manifest fields | `*Manifest` models in `scene_core/contracts.py` | `IngestReport.tsx` |
| Upload long side | `ingest.params.long_side` in `config/pipeline.yaml` | `UPLOAD_LONG_SIDE` in `src/lib/upload/shrink.ts` |
| Object membership binary format | `scene_core/membership.py` | `src/lib/api/membership.ts`, `src/lib/api/mock/membership.ts` |
| Files a browser may fetch | `SceneResults.PUBLIC` and `ASSETS` in `scene_core/results.py`; `SceneAssets` in `models.py` | `Schemas["SceneAssets"]`, viewer layers |
| Progress event shapes | `stage_event`, `progress_event`, `status_event` in `scene_store`; `ProgressEvent` model | `fold` in `src/lib/sceneProgress.ts` |
| Embedding size | `EMBEDDING_DIM` in `scene_core/results.py` and the `objects.embedding vector(1024)` column (a test compares them) | none |

Change the membership format only together with its `VERSION`, on both sides. The format itself is described in [docs/architecture/api.md](../architecture/api.md#object-membership-file).
