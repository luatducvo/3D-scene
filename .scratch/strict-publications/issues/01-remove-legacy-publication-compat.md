# Remove tolerance for incomplete Publications and Stage outputs

Status: ready-for-agent

`docs/agents/failures.md` says reading is strict: a Publication or Stage output that lacks a file the current code expects is invalid and raises, and the user reprocesses the Scene. These branches still tolerate missing files and must go.

## Scope

Backend:

- `SceneResults._check_membership` (`scene_core/results.py`) returns early when `graph/membership.bin` is missing. Require it: missing raises `RESULTS_INVALID`, so a Job without membership fails at publish.
- `SceneResults.load` should also require `mesh/mesh.glb` and `mesh/points.ply` (`ASSETS`), raising `RESULTS_INVALID` when either is missing. `assets()` then never reports `None` for a published Scene.
- `GeometricGraph.run` (`scene_stages/graph.py`) reads `attributes/attributes.json`, `align/manifest.json` and `align/walls.json` only when they exist. Read them unconditionally; a missing file is an error.
- `AlignFake` (`scene_stages/fake.py`) writes no `align/walls.json`. Make it write one (an empty list is enough) so the fake pipeline produces every file the real one does.
- `SceneAssets.membership_url` in `scene_api/models.py` documents "null for a Scene published before membership existed". Change it to say the URLs are null only while the Scene has no Publication, then regenerate the contract (`uv run main.py openapi`, `npm run api:sync`).

Frontend:

- `highlightState` in `src/components/viewer/view.ts` returns `"reprocess"` when `membership_url` is absent or the membership does not match the loaded geometry. Remove the `"reprocess"` state: a missing `membership_url` on a ready Scene, or a mismatch, is a failure shown as an error.
- Drop the `ui.reprocessForHighlight` string from `messages/en.json` (and `vi.json` if it still exists) and its use in `SceneExplorer.tsx`.
- Update `view.test.ts` and the layer mismatch report in `viewer/layers/index.tsx` accordingly.

## Behaviour change

Scenes published by older code that lack these files stop rendering highlights and show an error until they are processed again.

## Done when

- No code path checks whether a Publication or Stage output file exists before reading it, apart from listing optional inputs such as Keyframes.
- Tests cover a Publication missing `membership.bin` (publish fails with `RESULTS_INVALID`) and a graph Stage without `walls.json` (the Stage fails).
- The done check in `docs/agents/testing.md` passes for backend and frontend.
