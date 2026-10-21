# Extending

Each recipe lists every file the change touches. Finish with the done check in [agents/testing.md](agents/testing.md).

## A new Algorithm for an existing Stage

1. Write a `StageAlgorithm` subclass in `backend/packages/scene-stages/src/scene_stages/` (`gpu.py` for model-backed Algorithms, otherwise the Stage's module). Set `name = "<stage>.<method>"`, `stage`, `reads` and `writes` equal to the Stage's row in `OUTPUTS`, and `manifest_type` to the Stage's Manifest from `scene_core/contracts.py`. Write the same files, with the same names, as the Algorithm it replaces: later Stages read them.
2. Import heavy libraries inside `setup`, `run` or `download_weights`. Load models in `setup`; fetch weights into `MODELS_DIR` in `download_weights`; report progress with `self.progress`.
3. Register it under `[project.entry-points.scene_stages]` in `backend/packages/scene-stages/pyproject.toml`. Put its dependencies in a new optional extra there, and add that extra to the `gpu` extra in `backend/services/scene-compute/pyproject.toml` if it runs on the GPU image. Run `uv lock`.
4. Select it in `backend/config/pipeline.yaml` with its params.
5. Test it on small synthetic inputs in `backend/tests/test_<stage>.py`.

## A new Relation

1. Subclass `RelationRule` in `scene_stages/graph.py` with `predicate`, `reach` (the widest footprint gap in metres at which it can hold, or `None`) and `evaluate(a, b, context)`.
2. Register it under `[project.entry-points.scene_relations]` in `scene-stages/pyproject.toml`.
3. Add the predicate to `graph.params.relations` in `config/pipeline.yaml` and to the `get_relations` tool description in `scene_api/qa.py`.
4. Test it in `backend/tests/test_graph.py`.

## A new QA tool

1. Add a `_tool(...)` definition to `SceneTools.definitions` and a `_<name>` method in `scene_api/qa.py`.
2. Return every number the answer may state in the tool result, since the grounding check only accepts numbers that tools returned; add Object ids it refers to to `self.mentioned`.
3. Test it with `ScriptedLLM` in `backend/tests/test_api.py`.

## A new API endpoint

1. Add the route to `scene_api/main.py` and its models to `scene_api/models.py`; writes go through a `SceneStore` method.
2. `uv run main.py openapi`, then `npm run api:sync` in `frontend/`.
3. Add a `sceneApi` method in `frontend/src/lib/api/http.ts` and a handler in `frontend/src/lib/api/mock/handlers.ts`.
4. Test the route in `backend/tests/test_api.py`.

## A new database column or table

Add the next numbered file to `backend/migrations/`, written so it can run on a database that already has it (`IF NOT EXISTS`), and change the `SceneStore` writes and the API reads that use it.

## A new viewer layer

1. If it needs a new Publication file, write it from a Stage into `mesh/` or `graph/`, add it to `SceneResults.PUBLIC` and `ASSETS` in `scene_core/results.py` and to `SceneAssets` in `scene_api/models.py`, then regenerate the contract.
2. Write a component taking `SceneLayerProps` in `frontend/src/components/viewer/layers/index.tsx` and add it to `sceneLayers`.
3. Put its show and hide rules in `viewer/view.ts` with tests in `view.test.ts`, and its toggle in the `layers` panel of `SceneExplorer.tsx`, with strings in `messages/en.json`.

## A new Target or Provider

1. Add the Target to `backend/config/compute.yaml` with `backend: http`, `url: ${<PROVIDER>_URL}`, `token: ${COMPUTE_TOKEN}` and timeouts suited to its cold start.
2. Add `<PROVIDER>_URL` to `backend/.env.example`.
3. Write `backend/deploy/<provider>/README.md`: how to run the GPU image there, which port and URL to use, and how to check `/ping` and `/info`.
4. Check it with `GPU_TARGET=<target>` and `pipeline.fake-gpu.yaml` before the real pipeline.

## A new Stage

The nine Stages are fixed across both sides. A tenth touches `STAGES`, `OUTPUTS` and a new Manifest in `scene_core/contracts.py`; a Fake Algorithm and a real one; every `config/pipeline*.yaml`; `STAGES` in `frontend/src/lib/api/types.ts`; `METRICS` in `PipelineInspector.tsx`; the Stage strings in `messages/en.json`; the mock Scene in `mock/handlers.ts`; and the API contract.
