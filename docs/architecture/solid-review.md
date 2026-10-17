# SOLID review and legacy cleanup — 2026-10-17

Reviewed backend packages, services, Algorithm/Relation entry points, configuration, tests and
deployment code; checked frontend callers, translations, assets and types for obsolete code.
This is a source review of the current checkout, not a claim that SOLID can be fully verified
by a linter. Inline comments marked `SOLID review` identify every remaining finding below.

## Assessment

The backend uses SOLID principles substantially, with some explicit and some structural
interfaces. It does not follow all five principles consistently.

| Principle | Evidence | Remaining limitation |
|---|---|---|
| Single responsibility (SRP) | Algorithms transform Workspaces; SceneResults validates publication files; SceneStore owns transactional state writes and events. | API and compute app factories also own application behavior and orchestration. |
| Open/closed (OCP) | Algorithms and Relation rules are registered through lazy package entry points, selected through configuration. | The Scene Graph loop recognizes `against_wall` by name. |
| Liskov substitution (LSP) | Real/fake Algorithms share StageAlgorithm and Manifests; the Target contract suite exercises both in-process and HTTP adapters. | Room Relation rules ignore the second Object and require special dispatch. Contract tests support substitutability; they do not prove all GPU implementations. |
| Interface segregation (ISP) | RelationRule has one operation. Algorithm setup/weight hooks have default no-op implementations, so CPU Algorithms need no overrides. | Query embedding relies on a capability outside StageAlgorithm; it deserves its own narrow interface. |
| Dependency inversion (DIP) | Core imports no FastAPI, database driver or Torch. The Executor resolves registered Algorithms; QAAgent accepts real/scripted LLMs and owns no HTTP client. | The Target adapter interface is implicit, and Worker constructs SceneStore internally. |

## Inline findings

| Location | Finding and suggested direction |
|---|---|
| `scene_api/main.py:create_app` | SRP: separate upload/search/QA use cases from HTTP composition and read SQL as those responsibilities evolve. Keep writes transactional in SceneStore. |
| `scene_compute/server.py:create_app` | SRP: Compute Run scheduling/records and Workspace transfers can change independently. Extract their behavior behind the existing compute contract. |
| `scene_stages/graph.py:GeometricGraph.run` | OCP/LSP: model Object-versus-room evaluation scope on RelationRule so a new room Relation needs no special case or dummy second Object. |
| `scene_core/executor.py:Executor.invoke` | ISP/DIP: describe optional text embedding with a separate capability interface; avoid requiring it on every Stage. The invoke allowlist remains intentional. |
| `scene_target/__init__.py:TargetWorkspace.__init__` | DIP, maintainability improvement: give the two real adapters a typed Protocol. Runtime duck typing already permits replacement. |
| `scene_worker/runner.py:Worker.__init__` | DIP, conditional improvement: persistence construction remains coupled to orchestration. Inject SceneStore from main if persistence needs another adapter; no speculative repository hierarchy is needed now. |

These are review comments, not completed refactors. The lifecycle hooks, fake Algorithms,
ScriptedLLM, configured providers and registered `attributes.vlm_api` are current supported seams.

## Removed code

- The API's synthetic `legacy` publication version and flat publication serving path
  ([ADR-0007](../adr/0007-retire-unversioned-results.md)); unpublished Scenes expose no asset URLs.
- The unused `Registry.get` alias, `dominant_yaw` wrapper, ErrorDetail/ErrorResponse models,
  Worker.data_dir state and unused SceneError import.
- The `cpu` backend alias; `cpu` remains a valid Target name using `backend: inprocess`.
- The Scene Graph reader's old `{instances: [...]}` wrapper; both current lift Algorithms write
  a JSON list, as the embedding and attributes readers already require.
- Duplicated model-download configuration path probing; it now uses MODELS_PIPELINE_CONFIG or
  the shared CONFIG_DIR/source-layout resolver, and a bad explicit override fails visibly.
- Seven unused translation keys in both locales: title, create, delete, open, noObjects, clear,
  measureHint. Current UI strings, evidence data and supported Algorithms remain available.
- Wildcard imports and existing lint debt. Colab cells now share model-cache configuration,
  use port 9000 consistently and avoid printing the compute token; saved cell output is cleared.

Historical migration files remain immutable under the repository rules. They are needed to build
the current schema from scratch; historical mentions of removed behavior are not executable code.

## Validation

- `uv run tasks.py lint`: passed, clearing all 60 baseline findings.
- `uv run tasks.py test`: 86 passed against the disposable Postgres with fake Algorithms and
  ScriptedLLM. One dependency deprecation warning remains in FastAPI/Starlette's TestClient.
- `uv run tasks.py openapi`, then `npm run api:sync`: passed; generated contracts are unchanged.
- Frontend `npm run typecheck`, `npm test`, `npm run build`: passed; 19 frontend tests.
  TypeScript also passed with `--noUnusedLocals --noUnusedParameters`.
- Checked scene-core imports for forbidden framework/GPU/database dependencies; none found.
  Exercised model-download CONFIG_DIR discovery and failure on a missing explicit override from
  outside the repository, using all nine fake Algorithms without downloading model weights.
- Colab notebook JSON parses and contains no saved execution output. No live GPU inference,
  tunnel session or provider deployment was performed; those checks remain in GPU-INTEGRATION.md.

## Local data cleanup

Removed 238 existing Scenes and dependent Jobs, Stage Runs, Objects, Relations, messages and events
from the project's `scene-test-db`, retaining the schema and migration ledger. Synthetic records
created by verification and their temporary Workspaces were also removed. Final counts are zero
for all seven Scene/state tables, with all four schema migration records retained. There were no
local `data/` or `backend/data/` folders and no application Compose volumes to delete. Model weights
and environment files are untouched. The configured Colab Target was not accessed; remote storage
was not deleted or certified empty. Its updated notebook clears disposable Scene data on the next
server start, as described in the Colab guide.
