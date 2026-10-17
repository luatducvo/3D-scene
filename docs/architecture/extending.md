# Extending and replacing components

Every capability is a replaceable component chosen in configuration. This page lists the change
points; each recipe touches only the files it names.

## Change points

| To change | Write | Configure |
|---|---|---|
| A Stage method | A `StageAlgorithm` class + an optional extra + an entry point in [scene-stages/pyproject.toml](../../backend/packages/scene-stages/pyproject.toml) | `pipeline.yaml` → `algorithm` |
| Where the pipeline runs | Nothing | `GPU_TARGET` in `backend/.env`, Target in `compute.yaml` |
| GPU provider | A guide or deploy file under `backend/deploy/<provider>/` | A Target in `compute.yaml` (URL, headers) |
| Embedding model | A `StageAlgorithm` with `embed_text` | `pipeline.yaml` embed Stage; migrate `vector(dim)` |
| LLM / VLM | Nothing (OpenAI-compatible) | `LLM_*` / `VLM_*` in `.env` |
| Spatial Relation | A `RelationRule` (set `reach` when the rule needs the two footprints within a horizontal gap, so the graph can skip farther pairs) + an entry point in group `scene_relations` | `graph.params.relations` |
| QA capability | A tool definition and handler in `SceneTools` ([qa.py](../../backend/services/scene-api/src/scene_api/qa.py)) | Nothing |
| 3D rendering | A layer component | `sceneLayers` in [layers/index.tsx](../../frontend/src/components/viewer/layers/index.tsx) |
| API contract | Routes and models in `scene_api`, then `uv run main.py openapi` | Frontend: `npm run api:sync` |

## Replace an Algorithm (example: another reconstruction method)

1. Add a `StageAlgorithm` named `recon.mymethod` in `scene_stages`, with the same `reads`,
   `writes` and `ReconManifest` as `recon.da3`. Output must be metric; converting to meters is the
   Algorithm's job.
2. For a CPU Algorithm, add a test at the Stage Algorithm seam ([SPEC](../SPEC.md#seams-agreed));
   a GPU Algorithm is verified live (step 6).
3. Add an extra `recon-mymethod`, include it in the `gpu` extra of
   [scene-compute](../../backend/services/scene-compute/pyproject.toml), and register the entry point.
4. Set `algorithm: recon.mymethod` in [pipeline.yaml](../../backend/config/pipeline.yaml).
5. Rebuild and redeploy the GPU image (`uv run main.py push-compute-image --extras gpu`, or
   `up-local-gpu`), restart the worker, and process the Scene again.
6. Record the live check in [GPU-INTEGRATION.md](../GPU-INTEGRATION.md#live-check-log).

The runner, other Stages, the API and the frontend do not change.

## Add a provider

- **It runs a Docker image and exposes an HTTP port** (almost every GPU cloud): deploy the
  `scene-compute` image, add an `http` Target to `compute.yaml` and a URL variable to
  `backend/.env.example`, and write a guide under `backend/deploy/<provider>/`.
- **It only accepts its own function or handler format:** add a thin adapter under
  `backend/deploy/<provider>/` that runs inside the provider and forwards to the same `Executor`, or
  use that provider's container product. `TargetWorkspace` keeps its HTTP adapter.

## Record the decision

A change that is hard to reverse, surprising without context and the result of a real trade-off
gets an ADR in [docs/adr/](../adr/) with the next free number. A change that contradicts SPEC says
so in the ADR's status line, as ADR-0004 and ADR-0005 do.
