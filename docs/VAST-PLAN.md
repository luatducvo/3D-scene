# Plan: run scene-compute on Vast.ai

Status: accepted 2026-10-14. Implements the decisions from the Vast.ai design session. Where this
plan and SPEC disagree, update SPEC as part of this plan (step 1).

## Decisions

### Provider selection
- No provider is the default. Modal, Vast, RunPod and generic are equal deploy guides; the operator
  configures Targets before starting the system. Vast is the first provider exercised live.
- GPU Stages name their Target through environment variables: recon and align use
  `${RECON_TARGET}`; segment, lift and embed use `${PERCEPTION_TARGET}`. `pipeline.fake-gpu.yaml`
  uses `${GPU_TARGET}` for every GPU Stage. The `gpu` alias and `default_gpu_target` are removed.
- `PipelineConfig.load` expands `${VAR}` like `ComputeConfig.load`.
- The config hash stays algorithm + params only, so changing provider never reruns Stages.
- The worker refuses to start when a Stage's Target is empty, unknown, or an HTTP Target without a
  URL; the message names the missing variable or Target.
- The API starts without GPU Targets. Search returns HTTP 503 `COMPUTE_UNAVAILABLE` when the embed
  Stage's Target is unconfigured, unreachable or not ready within 10 s. The answer stream has already
  sent HTTP 200, so Object-finding QA tools end it with an `error` event carrying the same code. Mesh,
  Objects and measurement keep working.

### Targets
- `compute.yaml` gains `vast_recon` (`VAST_RECON_URL`) and `vast_perception`
  (`VAST_PERCEPTION_URL`), HTTP, non-shared storage, 25,000,000-byte chunks, 900 s startup timeout.
- The fake image runs on `vast_recon` (`GPU_TARGET=vast_recon`).

### Image
- Built and pushed from the local machine to a public Docker Hub repository.
- Tags: `<COMPUTE_IMAGE_REPO>:{fake|recon|perception}-<git short sha>`.
- `uv run tasks.py push-compute-image --extras {""|recon|perception}` derives the tag from
  `COMPUTE_IMAGE_REPO`, the variant and `git rev-parse --short HEAD`, and prints the pushed digest.
  `--image` still overrides the full name. SPEC story 55 (remote Dockerfile build) applies to Modal only.

### Vast instances (manual, web UI)
- Launch mode **SSH**. The image CMD does not run in this mode, so the On-start script downloads
  weights into `MODELS_DIR` and then starts `uvicorn scene_compute.server:app` on port 9000.
- `COMPUTE_TOKEN` and `HF_TOKEN` are account-level environment variables, never template variables.
- Offer filters: verified, on-demand (not interruptible), CUDA >= 12.8, 1 GPU, reliability > 98%,
  VRAM >= 24 GB for recon and >= 16 GB for perception, disk >= weights + 30 GB.
- Two instances run side by side during a Job (one per image variant).
- Network: direct `http://PUBLIC_IP:EXTERNAL_PORT` plus token for the fake image; for real captures
  an SSH tunnel per instance (`-L 9001:localhost:9000`, `-L 9002:localhost:9000`) with URLs
  `http://host.docker.internal:9001` and `:9002`.
- Instances are destroyed after each session. A new instance means a new URL in `backend/.env`
  and a worker restart (the worker reads `compute.yaml` once at startup).
- Known limit: search needs the perception instance running.

### Pipeline
- `ingest.max_keyframes` becomes 80 so MapAnything fits 24 GB with memory-efficient inference.

### Vocabulary
- GLOSSARY is unchanged. Docs say "scene-compute on Target `vast_recon`", never "GPU worker"
  (the worker is the local `scene-worker`). "Instance" and "offer" are provider words.

## Steps

1. **Docs.** SPEC: remove "Modal is the development GPU target"; M2 acceptance targets "a configured
   remote Target" (cold-start wording only for scale-to-zero providers); stories 53/55 reflect two
   variant Targets and Modal-only remote builds. ARCHITECTURE §6.1, §6.3, §6.7, §6.8 and the
   pipeline configuration section. GPU-INTEGRATION gains a Vast live-check log.
2. **Config.** `compute.yaml`, `pipeline.yaml`, `pipeline.fake-gpu.yaml`, `backend/.env.example`
   (`RECON_TARGET`, `PERCEPTION_TARGET`, `GPU_TARGET`, `VAST_RECON_URL`, `VAST_PERCEPTION_URL`,
   `COMPUTE_IMAGE_REPO`).
3. **Target selection.** `scene_core/config.py` (env expansion, no `gpu` alias), the worker
   runner and the API's query embedder resolve Targets directly from Stage config.
4. **Startup validation.** The worker rejects missing or URL-less Targets with a named error.
5. **`COMPUTE_UNAVAILABLE`.** Search and QA tools map unconfigured/unreachable embed Targets to 503.
6. **Image tagging.** `tasks.py` variant tags and digest output.
7. **Runbook.** `backend/deploy/vast/README.md`: account env vars, template fields, offer filters,
   On-start script, finding the external port, tunnels, `.env` update and worker restart, smoke
   checks (`/ping`, authenticated `/info`, fake pipeline), destroy, known search limit.
8. **Live check (manual, recorded separately).** Fake image on `vast_recon` end to end, then real
   recon and perception with the user's capture; record image digests, GPUs and results in
   GPU-INTEGRATION.

## Tests (local, fake Algorithms)
- Pipeline config expands `${RECON_TARGET}`-style variables.
- The worker refuses to start with an unset Target variable or an HTTP Target without a URL.
- Search returns 503 `COMPUTE_UNAVAILABLE` when the embed Target is unreachable.
- Existing REST API and compute contract seams keep passing with env-selected Targets.

## Information the user supplies later
- Docker Hub username/repository (`COMPUTE_IMAGE_REPO`) and `docker login` on the local machine.
- Vast.ai account, credit, and account-level `COMPUTE_TOKEN` / `HF_TOKEN`.
- Instance URLs (`VAST_RECON_URL`, `VAST_PERCEPTION_URL`) after renting.
- Results of the live checks.
