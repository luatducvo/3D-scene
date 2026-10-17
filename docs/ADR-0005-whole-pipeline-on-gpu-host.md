# ADR-0005: Run the whole pipeline on the GPU host

Status: accepted. Date: 2026-10-17. Deviates from [SPEC](SPEC.md) user stories 18, 19, 20 and 57,
the Stage skip rule, and the out-of-scope line "the user's own machine is the source of truth".

## Context

GPU Stages ran on a remote Target and CPU Stages (ingest, mesh, lift, attributes, graph) ran
in-process on the worker. Every remote Compute Run uploaded its inputs and downloaded all of its
outputs, so the local machine stayed authoritative and any Stage could be rerun. On Colab behind a
Cloudflare Tunnel the downloads dominated: `recon` alone returns one depth/confidence/pose archive
per Keyframe (80 for a typical Scene), and the next CPU Stage needed them locally. The ability to
rerun from a chosen Stage or skip unchanged Stages was not used.

## Decision

- Every Stage in `pipeline.yaml` and `pipeline.fake-gpu.yaml` runs on `${GPU_TARGET}`. The worker
  refuses to start when Stages name more than one Target. The `gpu` extra of scene-compute also
  installs `mesh-tsdf`, so the single GPU image can run all nine Stages.
- Uploads go straight to the Target. `POST /uploads` streams each file into the Target's `raw/`
  through the pipeline backend; local Scene storage never holds them. Uploading needs the Target
  running and fails with `COMPUTE_UNAVAILABLE` otherwise.
- Each Stage is still its own Compute Run and leaves its outputs on the Target for the next Stage.
- After the last Stage the worker downloads only `RESULTS` (`graph`, `embeddings`, `mesh`,
  `recon/rgb`) into `DATA_DIR/staging`, publishes from there, and only then replaces the Scene's
  local copy. A failed Job leaves the previous results untouched. Intermediate outputs
  (`keyframes`, `recon/frames`, `align`, `segment`, `instances`, `attributes`) never leave the Target.
- Every Job runs from the start. The worker deletes the Stage outputs on the Target
  (`DELETE /workspaces/{id}/files?dirs=…`) but keeps `raw/`; there is no `from_stage` and no
  config-hash skip. The `jobs.from_stage` column is no longer written.
- With `CLEAN_ON_START=1` (set by the Colab notebook) the compute server deletes `DATA_DIR/scenes`
  and `DATA_DIR/runs` on start, so a restarted runtime holds nothing from earlier sessions.

## Consequences

- Uploads cross the tunnel once; each Job downloads its results once instead of once per Stage.
- The GPU host holds the only copy of uploads and intermediate outputs. After a runtime restart a
  Scene cannot be processed again; create a new Scene and upload again. Processed Scenes stay
  viewable (mesh, point cloud, Objects, relations, best views) with the GPU host off.
- Search and the QA tool `find_objects` still embed query text on the Target, so they need it running.
- `POST /process` takes no body options; the UI offers "Process again" without a Stage choice.
- Stage Runs are always `running`, `done` or `failed`; `skipped` remains in the API enum only for
  rows written before this change.
- The fake CPU pipeline (`pipeline.fake.yaml`) still runs every Stage in-process on one Target.
