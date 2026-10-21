# Pipeline

## Stages

Every Job runs all nine Stages in this order. A Stage reads earlier Stages' folders and writes its own, inside the Scene's Target Workspace.

| Stage | Reads | Writes | Real Algorithm | Produces |
| --- | --- | --- | --- | --- |
| ingest | `raw` | `keyframes` | `ingest.opencv` | upright JPEG Keyframes; rejects blurry, badly exposed, duplicate and unreadable Frames; samples video with ffmpeg |
| recon | `keyframes` | `recon` | `recon.da3` | Depth Anything 3: per-Frame depth, confidence, intrinsics, poses (`recon/frames/*.npz`), RGB (`recon/rgb/*.png`), metric scale |
| align | `recon` | `align` | `align.geocalib_ransac` | gravity-aligned Frames (`align/frames/*.npz`), floor height, ceiling height, `walls.json` |
| mesh | `align`, `recon` | `mesh` | `mesh.tsdf` | `mesh/points.ply` coloured point cloud and `mesh/mesh.glb` TSDF mesh |
| segment | `recon` | `segment` | `segment.sam3` | SAM 3 masks per Frame for the concepts of a Vocabulary (`segment/masks/*.npz`) |
| lift | `segment`, `align`, `recon` | `instances` | `lift.maskclustering` | Instances from masks that agree across views: `instances.json`, 3D points, crops of Best Views |
| embed | `instances` | `embeddings` | `embed.metaclip2` | one 1024-d MetaCLIP 2 vector per Instance (`embeddings/objects.npz`) |
| attributes | `instances` | `attributes` | `attributes.none` | empty attributes; `attributes.vlm_api` (a vision LLM) exists but is not configured |
| graph | `instances`, `attributes`, `align`, `mesh` | `graph` | `graph.geometric` | `scene_graph.json` (Objects with oriented boxes, Relations, room) and `membership.bin` |

`STAGES` and `OUTPUTS` in `scene_core/contracts.py` define this table's first three columns. Each Stage's Manifest model is in the same file; the Executor validates the Algorithm's return value against it and writes it as `<folder>/manifest.json`.

`mesh.tsdf` and `lift.maskclustering` compute with CuPy when their params say `device: cuda` and with NumPy otherwise (`scene_stages/arrays.py`).

## Algorithms

- An Algorithm subclasses `StageAlgorithm` (`scene_core/ports.py`) and declares `name`, `stage`, `reads`, `writes` and `manifest_type`. `run(workspace, params)` returns its Manifest. `setup()` loads models once per process; `download_weights()` fetches weights into `MODELS_DIR`.
- `self.progress(done, total, unit)` reports progress. The worker stores at most one report every two seconds, always keeping the last.
- Algorithms are found through `scene_stages` entry points (`scene_core/registry.py`) and selected by name in a pipeline file. The Executor keeps one instance per Algorithm and runs one at a time.
- Relations come from `RelationRule`s registered as `scene_relations` entry points: `on`, `under`, `above`, `inside`, `next_to`, `near`, `against_wall`. The graph Stage evaluates the ones its `relations` param lists, skipping pairs farther apart than a rule's `reach`.
- Object Membership: a point of `points.ply` or a vertex of `mesh.glb` belongs to an Object when it lies within `membership_radius_m` of that Object's lifted points.

## Workspace layout

A Target Workspace, at `scenes/{scene_id}/` under the Target's data folder:

```
raw/            uploads, kept across Jobs
keyframes/      ingest
recon/          frames/*.npz, rgb/*.png
align/          frames/*.npz, walls.json
mesh/           points.ply, mesh.glb
segment/        masks/*.npz
instances/      instances.json, points/*.npy, crops/*.jpg
embeddings/     objects.npz (ids, vectors)
attributes/     attributes.json
graph/          scene_graph.json, membership.bin
```

Each output folder also holds its `manifest.json`. A Publication, at `DATA_DIR/scenes/{scene_id}/{job_id}/` on the API host, holds only `graph/`, `embeddings/` and `mesh/` (`SceneResults.DIRECTORIES`).

## Jobs

The worker (`scene_worker/runner.py`) loops:

1. Claim the oldest queued Job (`FOR UPDATE SKIP LOCKED`) and mark it running.
2. Delete every Stage output folder on the Target; `raw/` stays.
3. For each Stage: record the Stage Run as running, run the Algorithm on the Target, record it done with its Manifest.
4. Publish (below).
5. On any exception, record the failure on the Stage Run, the Job and the Scene.

At start the worker fails every Job left running by a previous process with `WORKER_INTERRUPTED`. It assumes it is the only worker for its database.

A Scene has at most one queued or running Job (a unique index enforces it). Stage Runs describe only the latest Job: enqueueing deletes the old ones.

## Publishing

`TargetWorkspace.replace_results` and `SceneStore.publish`:

1. Download `graph/`, `embeddings/` and `mesh/` from the Target into `DATA_DIR/staging/{scene}/{job}`, checking each file's SHA-256.
2. Rename the staging folder to `DATA_DIR/scenes/{scene}/{job}`. It is never modified again.
3. `SceneResults.load` checks the Scene Graph, embeddings and membership agree (same Object ids, 1024-d finite vectors) or raises `RESULTS_INVALID`.
4. In one transaction: replace the Scene's Objects and Relations, store the room, set `scenes.publication` to the Job id, mark the Job done and the Scene ready.
5. Delete the Scene's other Publication folders.

If any step before the commit fails, the new folder is removed and the previous Publication keeps being served.
