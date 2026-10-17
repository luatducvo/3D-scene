# Architecture audit — 2026-10-17

Assessment and recommendations only; this document changes no application behavior or accepted
decision. Reviewed the working checkout, SPEC, CONTEXT, ADRs 0001–0005, architecture pages, package
dependencies, backend runtimes and Algorithms, frontend data flow, tests, Docker definitions, and
the task runner. Findings distinguish reproduced behavior from conclusions drawn from source.

The checkout changed during the review: `SceneResults` and its integrations/tests were being added,
and `.scratch/architecture-deepening/` contains an implementation plan. These are work in progress,
not changes made by this audit. The existing `docs/REFACTORING.md` is preserved. Validation below is
a baseline taken during this activity, not a certification of the eventual combined changes.

## Overall assessment

The main architectural choices fit a local, single-user learning application:

- Pure Workspace Algorithms, with the Executor in `scene-core`, keep perception independent of
  Postgres and GPU providers.
- Entry-point discovery, optional heavy dependencies, fake Algorithms, and `ScriptedLLM` provide
  useful replacement and testing seams.
- The portable compute contract and one Target per Job follow ADR-0005. Returning intermediate
  data to the local worker or restoring per-Stage reruns would reverse that decision.
- OpenAPI, the frontend `SceneApi` interface, MSW, and the rendering-layer map are worth keeping.

The main weakness is that several callers must coordinate storage ownership, publication,
configuration, state transitions, and event shapes themselves. The first refactors should make
those invariants local to a few modules. Splitting long files into more files alone will not do it.

## Priority and scope

P1 means data correctness or a central SPEC guarantee. P2 means maintenance or an observable
consistency problem. P3 means cleanup that can follow the substantive changes. Effort is relative,
not a delivery estimate.

| ID | Priority | Refactor | Effort | Evidence |
|---|---|---|---|---|
| R1 | P1 | Give Target Workspace operations one owner; remove stale upload synchronization | M | Reproduced with the HTTP adapter |
| R2 | P1 | Publish one coherent version of database state and served assets | L | Failure windows established from source |
| R3 | P1 | Enforce numeric grounding inside the QA module | M–L | Unsupported numerical answer accepted in a probe |
| R4 | P1 | Preserve embedding identity across Publication, configuration changes, and restart | M | Configuration and loading paths inspected |
| R5 | P2 | Extract shared persistence and Target adapters from `scene-worker` | M | Cross-service imports and dependencies confirmed |
| R6 | P2 | Make progress state belong to the current Job | M | Schema, enqueue, replay, and UI paths inspected |
| R7 | P2 | Preserve compute failures and validate the transport contract once | M | Error-code loss reproduced |
| R8 | P2 | Make the generated HTTP contract and frontend state seams effective | M | Client, mock handlers, hooks, and tests inspected |
| R9 | P2 | Centralize artifact validation and shared Frame geometry | M | `SceneResults` partly addresses this already |
| R10 | P2/P3 | Consolidate runtime resources, migrations, Compose, and validation tasks | S–M | Deployment definitions and checks inspected |

## R1 — Target Workspace ownership and stale input synchronization

Sources: [HTTP adapter](../backend/services/scene-worker/src/scene_worker/compute/http.py),
[runner](../backend/services/scene-worker/src/scene_worker/runner.py),
[alignment/segmentation Algorithms](../backend/packages/scene-stages/src/scene_stages/gpu.py),
[ADR-0005](adr/0005-whole-pipeline-on-gpu-host.md).

`HttpBackend.run()` still calls `_sync_up(scene_id, reads)`. It treats any matching local files as
inputs that should overwrite the Target. After a successful Job, however, local `recon/rgb` holds
published results, while the Target owns the working inputs for the next Job.

On reprocessing, reconstruction writes new RGB images on the Target. Starting alignment, mesh,
segmentation, or lift can then upload the previous published RGB from local storage over those new
images. This can silently mix old images with new depth and poses, or fail when resolutions differ.
The existing remote-rerun test produces identical fake images twice, so it does not detect this.

A probe through `HttpBackend.run("align.fake", ..., reads=["recon"])`, using `httpx.MockTransport`
and a local previously published RGB file, recorded this request before Stage execution:

```text
PUT /workspaces/room/files/recon/rgb/0000.png
body: previous-published-rgb
```

Recommended interface: one Target Workspace module configured once per runtime. Callers request
uploading capture inputs, executing a configured Stage, fetching finished results, embedding query
text, and deletion. It owns Algorithm selection and parameters, local/HTTP adapters, and errors.
The runner should not resolve remote Algorithm classes simply to supply `reads` and `writes`.
Remove general Stage-input upload synchronization from the ADR-0005 execution path; explicit
capture uploads already deliver `raw/` to the Target.

Validate through the compute-contract seam: rerun with changed reconstruction RGB, assert that no
Stage sends published local files back to the Target, and verify downstream RGB/depth consistency.

## R2 — Coherent Publication and immutable served assets

Sources: [runner](../backend/services/scene-worker/src/scene_worker/runner.py),
[local file adapter](../backend/services/scene-worker/src/scene_worker/compute/local.py),
[viewer asset loaders](../frontend/src/components/viewer/layers/index.tsx).

There are two different failure windows:

1. In-process and HTTP shared-storage execution use the published Scene Workspace as the working
   Workspace. Clearing Stage outputs at the beginning of a Job deletes the previous mesh and RGB
   immediately. A later Stage failure cannot preserve those assets.
2. Non-shared HTTP execution stages downloads, but `publish()` commits new Objects and Relations
   before the runner removes and moves each asset directory. An I/O failure or process interruption
   during these moves leaves new database state with old, missing, or partially replaced assets.

The proposed `replace_results` sequence in the existing deepening plan—commit Publication and
`ready`, then rename directories—still has the second failure window, including a period where
`ready` points to incomplete assets. A database transaction cannot roll back filesystem operations.

Recommended design:

1. Keep the Target's working Workspace separate from published files for every adapter.
2. Fetch and validate a complete result set into a new immutable local directory identified by Job.
3. Finalize that directory before changing the visible publication. If this fails, the previous
   publication is still intact.
4. In one Postgres transaction, replace the published understanding, save the directory/version
   reference, finish the Job, set `ready`, and insert its event.
5. Retain the preceding directory until the new publication is committed; remove unreferenced
   directories through cleanup. A crash before commit can leave an orphan, not a broken publication.

Include that version in API-issued asset URLs. Currently reruns reuse the same mesh/PLY URL, which
is also the key passed to `useGLTF`/`useLoader`; an open browser can reuse geometry from a preceding
Job. Versioned URLs make the publication identity usable by the frontend too.

This changes persistence and storage layout, so implementation deserves an ADR and migration.
Test interrupted Publication and failed reprocessing through REST + real worker/Postgres with fake
Algorithms, for both in-process and HTTP Targets. Assert that database state and served assets
always refer to one complete publication.

## R3 — QA grounding must be an enforced invariant

Sources: [QA module](../backend/services/scene-api/src/scene_api/qa.py),
[question endpoint](../backend/services/scene-api/src/scene_api/main.py),
[SPEC QA requirements](SPEC.md#qa-agent).

`QAAgent.answer()` accepts any `content` response without tool calls and emits it as both `delta`
and `final`. The system prompt asks for grounding, but no programmatic check enforces it. A probe
with `ScriptedLLM` and no Objects/tools executed accepted:

```text
The sofa is 999 meters long.
```

There is also inconsistent responsibility across LLM adapters: `OpenAICompatibleLLM.complete()`
extracts `final_answer` itself, while the generic agent loop handles the other tools. The real
adapter can return a final answer from a response containing other tool calls without executing
those calls. The scripted and real adapters therefore do not expose exactly the same protocol.
The current adapter also waits for a complete HTTP answer, after which the agent emits one full
`delta`; this does not implement streaming an answer as it is written.

Recommended refactor: keep LLM adapters responsible for transport and one typed reply protocol;
put tool execution, finalization, and grounding in `QAAgent`. Keep a record of measured facts and
Object identities returned by tools. Numerical claims in the final response must reference those
facts and use server-validated values/units. Render numeric fragments from those facts, and reject
unsupported numerical claims. Requiring one tool call or checking numbers with a regex alone is
not sufficient. Add token streaming after the finalization contract is clear.

Keep `ScriptedLLM` and test unsupported answers, mixed final/tool calls, invalid citations, and
measurements through the existing API + SSE seam. The disabled VLM attributes are an accepted
ADR-0004 decision and are not a refactoring defect.

## R4 — Embedding identity is part of a publication

Sources: [query embedding construction](../backend/services/scene-api/src/scene_api/main.py),
[MetaCLIP loading](../backend/packages/scene-stages/src/scene_stages/gpu.py),
[embedding Manifest](../backend/packages/scene-core/src/scene_core/contracts.py),
[database schema](../backend/migrations/001_init.sql).

Object embeddings are produced using the embed Stage's parameters. Query embedding passes only
the Algorithm name and text; it does not pass those parameters. On a cold compute process,
`MetaClipEmbeddings.embed_text()` loads its class-default model rather than the configured Stage
`model_id`. A warm process can conceal this because its cached instance was configured by a Job.

Search also chooses the currently configured embed Algorithm for every Scene. A model change can
therefore compare an existing Scene's vectors against vectors from a different embedding space.
Equal dimensions do not make two embedding spaces compatible.

Persist embedding identity with Publication: Algorithm, model/revision, preprocessing or relevant
configuration fingerprint, and dimension. Configure query encoding explicitly from that identity.
If it is unavailable, return a clear mismatch/unavailable error instead of ranking incomparable
vectors. Test two fake embedding spaces of the same dimension and a cold process. Likewise, record
the capture's Target identity if previously uploaded Scenes must remain processable after a global
Target configuration change; current Scene rows contain no such reference.

## R5 — Shared infrastructure and semantic persistence operations

Sources: [API package](../backend/services/scene-api/pyproject.toml),
[worker package](../backend/services/scene-worker/pyproject.toml),
[API factory](../backend/services/scene-api/src/scene_api/main.py),
[Repository](../backend/services/scene-worker/src/scene_worker/repository.py),
[runner](../backend/services/scene-worker/src/scene_worker/runner.py).

`scene-api` depends directly on `scene-worker` for database access, Target construction, errors,
and cleanup. It consequently also installs `scene-stages[mesh-tsdf]` through the worker dependency.
Scene lifecycle SQL is distributed among route handlers, `Repository`, and the runner. Moving
`Repository` alone would leave transaction ordering and failure transitions scattered.

The planned `scene-store` and `scene-target` packages are reasonable because both runtimes already
need these capabilities. An alternative is one infrastructure package with separate persistence
and Target modules; package count is less important than ownership.

- Persistence operations should express enqueue, claim, Stage transitions, failure/recovery,
  Publication, and deletion together with their transactional events.
- Target operations should hide transport, storage layout, readiness, and implementation errors.
- API composition should construct dependencies once and close HTTP/LLM resources at shutdown.
  Currently LLM clients may be constructed per question and cached compute clients are not closed
  by the API lifespan.
- Split routes and use dependency injection after these responsibilities have clear owners.
  Routers should contain HTTP adaptation, not new copies of lifecycle logic.

Keep Postgres drivers and HTTP clients out of `scene-core`. The existing refactoring document's
suggestion to put database implementation or an HTTP compute client into core would violate the
repository's dependency rule. Pure contracts, domain validation, and NumPy geometry belong there.

## R6 — Current Job identity and progress replay

Sources: [schema](../backend/migrations/001_init.sql),
[enqueue](../backend/services/scene-worker/src/scene_worker/repository.py),
[Stage transitions](../backend/services/scene-worker/src/scene_worker/runner.py),
[progress endpoint](../backend/services/scene-api/src/scene_api/main.py),
[Scene page](../frontend/src/app/[locale]/scenes/[sceneId]/page.tsx).

`stage_runs` is keyed by `(scene_id, stage)`, events have no Job identity, and enqueue does not clear
the previous Stage Runs. On a rerun, untouched later Stages still appear `done` from the previous
Job until execution reaches them. If an early Stage fails, the response contains Stage Runs from
two Jobs. Clearing React state cannot fix replay from that database snapshot.

Choose a deliberate latest-Job policy: either reset Stage state transactionally when enqueueing,
or associate Stage Runs and events with the Job and read the current Job explicitly. Historical
Stage execution is not required just to fix current progress. Reuse the chosen identity for
frontend event folding and publication cache invalidation.

Extract `useSceneProgress` to own replay/live merging, terminal-state handling, subscription
cleanup, and query invalidation. Test reconnecting during a rerun and failure in an early Stage,
not only static `StageStepper` markup. Preserve legacy `skipped` rows deliberately if removing
that enum; dropping the frontend/backend enum alone does not migrate stored values.

## R7 — Compute failures and transport policy

Sources: [compute server](../backend/services/scene-compute/src/scene_compute/server.py),
[HTTP adapter](../backend/services/scene-worker/src/scene_worker/compute/http.py),
[Target configuration](../backend/packages/scene-core/src/scene_core/config.py).

The server drops an Algorithm failure's `details`. The HTTP adapter then discards its `code` and
rethrows `ComputeError`, whose code is always `COMPUTE_FAILED`. A transport probe returning
`NOT_ENOUGH_KEYFRAMES` with rejection counts produced `COMPUTE_FAILED` and no details. Local and
HTTP execution therefore expose different domain failures.

Share a typed failure envelope and preserve `code`, `message`, and `details` through both adapters.
Separate a Target connectivity failure from a failed Algorithm. Validate positive chunk size,
polling intervals, and deadlines once in Target configuration.

Two additional inconsistencies should be handled there:

- The model's default chunk size is `25 * 1024 * 1024`, while the server's default is 25,000,000
  bytes. The checked-in Target YAML sets matching sizes, but constructing a default HTTP Target
  does not. Use one unit and one explicit policy.
- A query readiness deadline of 10 seconds can still wait for a client request with a 29-second
  timeout before checking the deadline. Bound each request by the remaining total budget.

The single execution queue is an accepted GPU resource policy. If query embedding waits behind a
long Stage, expose a clear busy/deadline result; parallel GPU execution is not automatically the
right fix. Keep transport verification at the existing compute-contract seam.

## R8 — Frontend contract, state ownership, and mocks

Sources: [HTTP client](../frontend/src/lib/api/http.ts),
[port](../frontend/src/lib/api/port.ts), [SSE decoder](../frontend/src/lib/api/sse.ts),
[explorer](../frontend/src/components/SceneExplorer.tsx),
[viewer store](../frontend/src/lib/store/viewerStore.ts),
[MSW handlers](../frontend/src/lib/api/mock/handlers.ts),
[tests](../frontend/src/lib/api/http.test.ts).

`typedClient` is created but unused; ordinary REST calls use string paths and an unconstrained
generic JSON wrapper. Generated response types help callers, but do not check those route strings
or request shapes. Use the generated client for ordinary REST operations, retaining XHR for upload
progress and the fetch stream for answers. Use one error decoder for those transports.

Keep `SceneApi` as the frontend's testable interface. `mockSceneApi` is just an alias for the HTTP
implementation, so that redundant selection can be removed without removing the interface or
the explicit MSW development mode. Removing `NEXT_PUBLIC_API_MODE` would also remove the documented
way to run the UI without a backend unless replaced with an equivalent startup mechanism.

Move server-state lifecycle logic out of page JSX into focused hooks. Keep explorer panel
coordination local, with panel rendering split only where it improves maintainability. Define a
viewer reset policy per Scene/publication: the current singleton store is reset piecemeal by the
page, explorer, and layers. Same-Scene reprocessing needs to reset geometry/bounds as well as
selection. Prefer the publication version from R2 over ad hoc cache flushing.

MSW also needs a lifecycle owner. Today requesting `/events` drives completion; an unobserved Job
does not advance, and the handler marks the Scene ready before its stream has finished. It permits
processing a created Scene and answering questions regardless of readiness. This makes the mock
hide lifecycle bugs. Advance mock Jobs independently of subscribers, and model the important
409/error/reconnect cases. The 11 current tests cover HTTP/SSE decoding, static markup, and image
scoring; they do not exercise the Scene page's progress effects, chat cancellation, or viewer
selection/search interactions.

## R9 — Artifact contracts and shared geometry

Sources: [new SceneResults module](../backend/packages/scene-core/src/scene_core/results.py),
[Executor](../backend/packages/scene-core/src/scene_core/executor.py),
[geometry](../backend/packages/scene-core/src/scene_core/geometry.py),
[lift](../backend/packages/scene-stages/src/scene_stages/lift.py),
[mesh](../backend/packages/scene-stages/src/scene_stages/mesh.py),
[GPU Algorithms](../backend/packages/scene-stages/src/scene_stages/gpu.py).

The in-progress `SceneResults` extraction usefully centralizes result paths, publication loading,
public files, and embedding dimension. It is complementary to R2; it does not make Publication
atomic. Extend validation at this existing seam where needed: Scene identity, valid Relation
references, finite/valid boxes, required served assets, and best-view references.

Between Stages, Frame archives are still untyped dictionaries. Back-projection, camera projection,
and pose application are repeated in alignment, mesh, and lift. Small shared pure-NumPy operations
and a validated Frame loader would concentrate shape, finite-value, intrinsics, and coordinate
conventions. Keep Algorithm-specific confidence thresholds and filtering with their Algorithms.
Do not build a general artifact framework or split every helper into a public module.

One separate feature gap: the real `GeometricGraph` never populates `floor_area`, while the fake
does. Consequently `get_room_info` returns no measured floor area for real output. Treat this as a
SPEC implementation gap, not evidence that a broad architecture rewrite is needed.

## R10 — Runtime resources, migrations, and development feedback

Sources: [migration loader](../backend/services/scene-worker/src/scene_worker/repository.py),
[configuration](../backend/services/scene-worker/src/scene_worker/container.py),
[tasks](../tasks.py), [root Compose](../compose.yaml),
[backend Compose](../backend/compose.yaml), [frontend Compose](../frontend/compose.yaml).

- `parents[4]` resource discovery works in the editable source layout used by the current images.
  It is a packaging assumption, not a demonstrated current production crash. Use explicit runtime
  configuration and packaged migration resources for installed distributions; missing resources
  should fail clearly instead of silently finding no SQL files.
- The architecture pages say migrations run only at volume creation. In code, both API and worker
  call `Repository.migrate()` at startup and re-execute all SQL files. Establish one documented
  migration path with a version ledger and serialization, without requiring deletion of all Scenes
  to upgrade an existing database. A small SQL runner can suffice; a framework is optional.
- Root and backend Compose duplicate service definitions. Their relative model-cache defaults
  already resolve in different locations: `tasks.models_dir()` anchors `./models` at `backend/`,
  while root Compose interprets the same environment value from the root Compose location. Choose
  one canonical composition, resolve host paths once, and keep thin overrides only where needed.
- Add discoverable fast/backend-integration validation tasks, and put the intended Ruff rules in
  repository configuration. Prefer markers or collection rules over hard-coded test filename lists.
  Keep formatting changes in a separate mechanical change. At the initial scan Ruff reported 79
  violations and 41 files needing formatting; this is lower priority than R1–R4.

## Review of the existing five-ticket implementation plan

The plan in [.scratch/architecture-deepening](../.scratch/architecture-deepening/spec.md) identifies
useful seams. Amend it before treating the tickets as a complete solution:

| Ticket | Assessment |
|---|---|
| 01 — Scene Results | Useful and already being implemented. Keep core free of database/HTTP dependencies; distinguish artifact validation from coherent Publication. |
| 02 — Scene Store | Useful ownership change. Define current-Job state explicitly. Direct Store-only tests do not replace the REST + real worker/Postgres primary seam required by SPEC. |
| 03 — Target Workspace | Strongest consolidation opportunity. Remove stale `_sync_up`, separate working/published storage, and correct commit/rename ordering. Persist Target provenance before narrowing deletion to only the current configured Target. |
| 04 — Scene progress | Extract the progress owner and use the typed client. Keep the useful `SceneApi` interface and an explicit MSW startup mode. |
| 05 — Viewer camera | Defer speculative camera rewrites until publication identity, bounds reset, and actual UI behavior have tests. Revision counters alone are not a defect. |

The plan also needs explicit work for QA numeric grounding and embedding identity; those are not
covered by the five tickets. An API/model change still requires exporting OpenAPI and regenerating
the frontend contract. Add an ADR for any changed persistence guarantee or departure from the
accepted decisions rather than silently changing the testing or deployment scope.

## Suggested delivery order

1. Add regression coverage for stale RGB uploads, failed reprocessing, and current-Job progress at
   the existing public seams. Complete the small `SceneResults` extraction already in progress.
2. Implement Target Workspace and coherent versioned Publication together with the semantic Store
   operations they need. Preserve compute error details in the same transport work.
3. Enforce QA finalization/grounding and persist embedding identity. These can be delivered as
   independent behavior changes with fake Algorithms and `ScriptedLLM`.
4. Finish API composition/route separation, typed REST calls, progress hooks, mock lifecycle, and
   publication-aware viewer state. Apply the frontend done check and browser verification then.
5. Consolidate migrations, Compose, paths, and validation tasks. Format separately; perform deeper
   GPU resource/performance work only after the documented live acceptance checks provide evidence.

Avoid adding Redis, additional deployed services, distributed queues, cloud storage, authentication,
or model eviction solely as part of this refactor. They do not resolve the identified seams and
several are outside the accepted project scope.

## Validation and limits

- Frontend: `npm test` passed all 11 tests; `npm run typecheck` passed.
- Frontend build was attempted and failed loading `next.config.ts` with `Failed to load native
  binding`. This environment result is not attributed to an application source defect.
- Backend non-database/non-compute-contract suite: 19 passed, 3 failed. All three VLM tests recorded
  `WinError 10013` socket-access denial in their generated `errors.json`; they did not reach their
  local HTTP fixtures. Earlier temporary-directory permission problems were avoided by putting
  pytest and Python temporary files under a verified workspace path.
- The four compute-contract tests were not completed; the broader attempt stalled and was
  interrupted. No passing compute-contract baseline is claimed.
- REST/Postgres tests were not run: Docker Desktop's Linux engine pipe was unavailable. No live
  GPU checks were performed; the GPU integration log still contains pending acceptance entries.
- Lightweight probes through `HttpBackend` and `QAAgent` reproduced stale result uploads,
  compute error-code/detail loss, and accepting an unsupported numerical answer.
- Filesystem/database crash windows, embedding mismatch, and mixed-Job progress are source-based
  findings; they still need the specific regression scenarios above on a working integration stack.

No application source files, existing plans, generated contracts, or existing user changes were
edited by this audit. Only this assessment document was added.
