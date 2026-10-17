# Pipeline: Stages, Jobs and Publication

How a Job turns uploads into a published Scene Graph. Read [overview.md](overview.md) first.

## Algorithms and the registry

Every Stage method is a `StageAlgorithm` ([scene_core/ports.py](../../backend/packages/scene-core/src/scene_core/ports.py)):
a class with a registry `name` (`recon.da3`), the `stage` it serves, the Workspace folders it
`reads` and `writes`, and a `run(workspace, params)` that returns that Stage's Manifest. Optional
hooks: `download_weights()` (used by `main.py download-models`), `setup()` (load models once per
process) and `progress(done, total, unit)` (reported to the UI; a no-op unless the Executor
attached a sink).

Algorithms are pure Workspace transforms. They never access the database, never know which Target
they run on, and never transfer files ([ADR-0001](../adr/0001-worker-publishes-scene-graph.md)).

Registration is by package entry points only, listed in
[scene-stages/pyproject.toml](../../backend/packages/scene-stages/pyproject.toml): group
`scene_stages` for Algorithms, `scene_relations` for Relation rules. Discovery reads metadata
without importing heavy libraries; selecting a name loads its class lazily. A method's heavy
dependencies sit in its own optional extra (`recon-da3`, `segment-sam3`, ...), so each runtime
installs only what it runs.

Each Stage has a `*.fake` Algorithm in [fake.py](../../backend/packages/scene-stages/src/scene_stages/fake.py)
that writes contract-valid outputs without models. Tests and the walking skeleton use them.

## Pipeline configuration

[pipeline.yaml](../../backend/config/pipeline.yaml) names the one `target:` every Stage runs on,
because Stage outputs stay where they were produced
([ADR-0005](../adr/0005-whole-pipeline-on-gpu-host.md)), and maps each of the nine Stages to an
Algorithm and parameters; the parameter values there are the defaults in force. `${VAR}` is expanded
from the environment; an unset variable stays literal and the worker reports it by name.

## The Job runner

[runner.py](../../backend/services/scene-worker/src/scene_worker/runner.py), one worker per database.
The runner holds no SQL: every state change is one call on `SceneStore`
([scene_store](../../backend/packages/scene-store/src/scene_store/__init__.py)), which commits the
rows and their `scene_events` in one transaction. Every Target operation is one call on
`TargetWorkspace` ([compute.md](compute.md#target-workspace)).

1. **Claim.** Poll every 0.5 s; `SceneStore.claim` takes the oldest `queued` Job with `FOR UPDATE SKIP LOCKED`.
   A partial unique index allows one active Job per Scene. Stage Runs describe the latest Job only:
   enqueueing deletes the previous Job's Stage Runs in the same transaction.
2. **Clear.** `clear_outputs` deletes every Stage output folder on the Target, keeping `raw/`.
   Every Job runs from the start; there is no Stage skipping or rerun-from-Stage.
3. **Run.** For each Stage in `STAGES` order: mark the Stage Run `running`, `run_stage` (one
   Compute Run), forward progress (stored and announced at most every 2 s, always including the
   final report), mark it `done` with its Manifest.
4. **Publish.** `replace_results` downloads only `SceneResults.DIRECTORIES` (`graph`,
   `embeddings`, `mesh`, `recon/rgb`) into `DATA_DIR/staging` and renames the complete folder to
   `DATA_DIR/scenes/{id}/{job id}`, never modified afterwards. `SceneResults(...).load()` validates
   it (see [Scene Results](#scene-results)) before any transaction opens, then `SceneStore.publish`
   replaces the Scene's Objects, Relations and room info, sets `scenes.publication` to the Job id
   and marks the Job `done` and the Scene `ready`, in one transaction. A failure removes the new
   folder; after the commit every older folder of the Scene is removed
   ([ADR-0006](../adr/0006-versioned-publication.md)). Only Job-versioned publications are served;
   there is no read path for unversioned results ([ADR-0007](../adr/0007-retire-unversioned-results.md)).

Any failure marks the running Stage Run, the Job and the Scene `failed` with
`{stage, code, message, details}`, with the Algorithm's own code and details on every Target. A
failed Job leaves the previous results untouched on every Target, because no Target works in the
published copy. On start, the
worker fails Jobs left `running` by a previous process with `WORKER_INTERRUPTED`.

Every state change also inserts a row into `scene_events` (and `pg_notify`s). `SceneStore` owns
the event shapes, so `SceneStore.snapshot` replays the current state with exactly the events live
streaming sends ([api.md](api.md#sse-events)). Its tests in
[test_store.py](../../backend/tests/test_store.py) call it directly against the test Postgres.

## Workspace layout

Paths are resolved by `SceneWorkspace` in [contracts.py](../../backend/packages/scene-core/src/scene_core/contracts.py),
which also defines `STAGES`, `OUTPUTS` and every Manifest model. The published subset is named by
[Scene Results](#scene-results).

```
scenes/{scene_id}/
├── raw/                     uploaded originals (on the Target only)
├── keyframes/               0000.jpg ... EXIF orientation applied, metadata stripped
├── recon/rgb/0000.png       images at model resolution            ← RESULT (evidence crops, viewer)
├── recon/frames/0000.npz    depth, conf, pose (camera-to-world, m), K
├── align/frames/0000.npz    gravity-aligned poses
├── mesh/mesh.glb            TSDF mesh                              ← RESULT
├── mesh/points.ply          dense colored point cloud              ← RESULT
├── segment/masks/0000.npz   masks (N,H,W), labels, scores
├── instances/               instances.json, points/{id}.npy, crops/{id}_{k}.jpg
├── embeddings/objects.npz   ids, vectors                           ← RESULT
├── attributes/              attributes.json, errors.json
└── graph/scene_graph.json                                          ← RESULT
```

Each Stage folder also holds its `manifest.json`.

## Scene Results

`SceneResults` in [results.py](../../backend/packages/scene-core/src/scene_core/results.py) is the
only code that knows the published files of a Scene. It reads files from a Workspace root (the
Scene's own or the staging copy) and never touches the database or the network.

| Member | Answers |
|---|---|
| `DIRECTORIES` | What the worker downloads from the Target and swaps into the Scene's local copy |
| `load()` | The Scene Graph and one embedding per Object. It fails with `RESULTS_INVALID` when a file is missing or unreadable, Object and embedding ids differ or repeat, a vector is not `EMBEDDING_DIM` long, or a value is not finite |
| `assets()` | Workspace paths of `mesh/mesh.glb` and `mesh/points.ply`, or `None` when absent |
| `view_image(frame_id)` | The `recon/rgb/{frame_id}.png` image behind an Object's best view |
| `public_file(path)` | The file behind a public path. Only `mesh/` and `recon/rgb/` are public, on every Target; any other, malformed or missing path is `FILE_NOT_FOUND` (404) |

`EMBEDDING_DIM = 1024` lives in the same module. The runner, the API search, the fake and the real
embed Algorithms use it, and a Postgres test checks it equals the `objects.embedding` column type.

## Stage contracts

Each row is the contract every replacement Algorithm must honor. Parameters are in `pipeline.yaml`.

| # | Stage | Algorithm | Reads → writes | Contract |
|---|---|---|---|---|
| 1 | ingest | `ingest.opencv` | `raw/` → `keyframes/` | Apply EXIF orientation, strip metadata (incl. GPS), resize. Split video with ffmpeg. Optional blur/exposure/duplicate rejection (`quality_filter`). Sort names naturally so Keyframes follow capture order; sample down to `max_keyframes`. Fewer than `min_keyframes` fails with `NOT_ENOUGH_KEYFRAMES` and rejection counts. |
| 2 | recon | `recon.da3` | `keyframes/` → `recon/` | Depth Anything 3 Nested Giant: metric depth and poses for all Keyframes in one `inference()` call, poses from the ray head. Writes `rgb/` and `frames/` (depth m, conf, camera-to-world pose, K). A non-metric prediction fails with `INVALID_MODEL_OUTPUT`. See [ADR-0003](../adr/0003-depth-anything-3-point-cloud.md). |
| 3 | align | `align.geocalib_ransac` | `recon/` → `align/` | GeoCalib gravity per Frame, RANSAC floor plane, rotate to z-up with the floor at z = 0, Manhattan yaw so walls follow x/y, ceiling height from the highest large horizontal plane. From here on, poses come from `align/`. |
| 4 | mesh | `mesh.tsdf` | `recon/`, `align/` → `mesh/` | `points.ply`: confident, edge-free pixels back-projected, averaged on a voxel grid, capped at `max_points`, binary PLY with colors (the viewer's default layer). `mesh.glb`: NumPy TSDF fusion + marching cubes. Bounds use percentiles so far outliers are ignored. |
| 5 | segment | `segment.sam3` | `recon/rgb` → `segment/` | SAM 3 through Ultralytics ([ADR-0002](../adr/0002-single-gpu-image-ultralytics-sam3.md)), every `frame_stride`-th Frame, prompted with the Vocabulary in [indoor-en.txt](../../backend/config/vocabularies/indoor-en.txt). |
| 6 | lift | `lift.maskclustering` | `recon/`, `align/`, `segment/` → `instances/` | In-house MaskClustering view consensus: masks → 3D points, cross-view consensus graph, iterative clustering, score × area label voting. Drops Instances seen in fewer than `min_views`; picks best views and saves crops. |
| 7 | embed | `embed.metaclip2` | `instances/` → `embeddings/` | MetaCLIP 2: score-weighted mean of crop embeddings, L2-normalized, 1024-d. `embed_text` serves query-time search (multilingual). |
| 8 | attributes | `attributes.none` | `instances/` → `attributes/` | Writes an empty entry per Instance and calls nothing ([ADR-0004](../adr/0004-skip-vlm-attributes.md)). `attributes.vlm_api` (OpenAI-compatible vision model, `VLM_*`) stays registered for switching back. |
| 9 | graph | `graph.geometric` | `align/`, `instances/`, `embeddings/`, `attributes/` → `graph/` | Fit gravity-aligned oriented boxes, apply every configured Relation rule to every Object pair, write the Scene Graph. Each Instance id becomes exactly one Object id. |

Live verification of the GPU adapters is tracked in [GPU-INTEGRATION.md](../GPU-INTEGRATION.md).

`instances/instances.json` is a JSON list of Instances for both real and fake lift Algorithms;
the older object wrapper is unsupported. Aligned Frame/RGB pairs and mask/label/score arrays must
have equal lengths; consumers fail on mismatches rather than silently truncating them.

## Relations

Rules live in [graph.py](../../backend/packages/scene-stages/src/scene_stages/graph.py), one class
per predicate, thresholds in meters: `on`, `above`, `under`, `inside`, `next_to`, `near`
(each with a surface distance in `value` where relevant) and `against_wall`. `left_of` / `right_of`
depend on the viewer and are answered at query time by the QA tool `relative_direction`.
