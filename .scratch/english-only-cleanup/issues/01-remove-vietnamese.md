# Remove the Vietnamese locale and `label_vi`

Status: ready-for-agent

The application is English only: next-intl serves only `en`, and the QA agent always answers in English. Vietnamese remnants are still in the code, the database and the API. Remove all of them so nothing Vietnamese-specific is left.

## Scope

Frontend:

- Delete `frontend/messages/vi.json`.
- Delete `frontend/src/middleware.ts` (it redirects old `/vi/...` links).
- `objectLabel` in `src/lib/api/types.ts`: drop the `vi` branch and the `locale` parameter, or replace its callers (`ObjectDetails.tsx`, `viewer/SceneCanvas.tsx`) with `object.label`.
- Tests: drop the `vi` cases in `ObjectDetails.test.tsx` and `SceneExplorer.test.tsx`.
- Mock data: drop `label_vi` from `src/lib/api/mock/room.ts` and its use in `mock/handlers.ts`.

Backend:

- `SceneObject.label_vi` in `scene_core/domain.py`.
- `attributes.vlm_api` (`scene_stages/attributes.py`): its `Description` model and prompts ask for `label_vi`; keep only `attributes`. Update the `NoAttributes` docstring.
- `scene_stages/fake.py` and `scene_stages/graph.py`: stop writing and reading `label_vi`.
- `scene_store.publish`: stop inserting `label_vi`.
- `scene_api/main.py`: `label_matches` checks only `label`; `public_objects` stops selecting `label_vi`.
- `scene_api/qa.py`: `_summary` drops `label_vi`.
- The next numbered migration in `backend/migrations/` (`002_drop_label_vi.sql` unless another issue took 002): `ALTER TABLE objects DROP COLUMN IF EXISTS label_vi;`.
- Tests: `test_api.py` inserts and `test_attributes.py` fixtures.
- Regenerate the contract: `uv run main.py openapi`, then `npm run api:sync` in `frontend/`.

## Behaviour change

A Search for a Vietnamese word no longer gets the label-match bonus; it still matches by embedding similarity.

## Done when

- `git grep -n -E "label_vi|vi\.json|/vi\b"` finds nothing outside `backend/migrations/`.
- `frontend/AGENTS.md` no longer mentions the Vietnamese remnants.
- The done check in `docs/agents/testing.md` passes for backend and frontend.
