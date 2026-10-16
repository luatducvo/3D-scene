# Plan: run scene-compute on Vast.ai

Status: accepted 2026-10-14. Implements the decisions from the Vast.ai design session. Where this
plan and SPEC disagree, update SPEC as part of this plan (step 1). Amended the same day by
[ADR-0002](ADR-0002-single-gpu-image-ultralytics-sam3.md): one GPU image and one Vast Target
replace the recon/perception pair; the decisions below reflect the amendment.

## Decisions

### Provider selection
- No provider is the default. Modal, Vast, RunPod and generic are equal deploy guides; the operator
  configures Targets before starting the system. Vast is the first provider exercised live.
- GPU Stages name their Target through `${GPU_TARGET}` in `pipeline.yaml` and
  `pipeline.fake-gpu.yaml` alike. The `gpu` alias and `default_gpu_target` are removed.
- `PipelineConfig.load` expands `${VAR}` like `ComputeConfig.load`.
- The config hash stays algorithm + params only, so changing provider never reruns Stages.
- The worker refuses to start when a Stage's Target is empty, unknown, or an HTTP Target without a
  URL; the message names the missing variable or Target.
- The API starts without GPU Targets. Search returns HTTP 503 `COMPUTE_UNAVAILABLE` when the embed
  Stage's Target is unconfigured, unreachable or not ready within 10 s. The answer stream has already
  sent HTTP 200, so Object-finding QA tools end it with an `error` event carrying the same code. Mesh,
  Objects and measurement keep working.

### Targets
- `compute.yaml` gains `vast` (`VAST_URL`), HTTP, non-shared storage, 25,000,000-byte chunks,
  900 s startup timeout. The fake and the GPU image both run on it (`GPU_TARGET=vast`).

### Image
- Built and pushed from the local machine to a public Docker Hub repository.
- Tags: `<COMPUTE_IMAGE_REPO>:{fake|gpu}-<git short sha>`.
- `uv run tasks.py push-compute-image --extras {""|gpu}` derives the tag from
  `COMPUTE_IMAGE_REPO`, the image (`fake` or `gpu`) and `git rev-parse --short HEAD`, and prints the pushed digest.
  `--image` still overrides the full name. SPEC story 55 (remote Dockerfile build) applies to Modal only.

### Vast instances (manual, web UI)
- Launch mode **SSH**. The image CMD does not run in this mode, so the On-start script downloads
  weights into `MODELS_DIR` and then starts `uvicorn scene_compute.server:app` on port 9000.
- `COMPUTE_TOKEN` and `HF_TOKEN` are account-level environment variables, never template variables.
- Offer filters: verified, on-demand (not interruptible), CUDA >= 12.8, 1 GPU, reliability > 98%,
  VRAM >= 48 GB for the GPU image, disk >= weights + 30 GB.
- One instance runs during a Job.
- Network: direct `http://PUBLIC_IP:EXTERNAL_PORT` plus token for the fake image; for real captures
  an SSH tunnel (`-L 9001:localhost:9000`) with URL `http://host.docker.internal:9001`.
- Instances are destroyed after each session. A new instance means a new URL in `backend/.env`
  and a worker restart (the worker reads `compute.yaml` once at startup).
- Known limit: search needs the GPU instance running.

### Pipeline
- `ingest.max_keyframes` is 200 and `ingest.quality_filter` is false; Depth Anything 3 sees every Keyframe in one forward pass, so more than 80 Keyframes needs an 80 GB GPU.

### Vocabulary
- GLOSSARY is unchanged. Docs say "scene-compute on Target `vast`", never "GPU worker"
  (the worker is the local `scene-worker`). "Instance" and "offer" are provider words.

## Steps

1. **Docs.** SPEC: remove "Modal is the development GPU target"; M2 acceptance targets "a configured
   remote Target" (cold-start wording only for scale-to-zero providers); stories 53/55 reflect one
   GPU Target and Modal-only remote builds. ARCHITECTURE §6.1, §6.3, §6.7, §6.8 and the
   pipeline configuration section. GPU-INTEGRATION gains a Vast live-check log.
2. **Config.** `compute.yaml`, `pipeline.yaml`, `pipeline.fake-gpu.yaml`, `backend/.env.example`
   (`GPU_TARGET`, `VAST_URL`, `COMPUTE_IMAGE_REPO`).
3. **Target selection.** `scene_core/config.py` (env expansion, no `gpu` alias), the worker
   runner and the API's query embedder resolve Targets directly from Stage config.
4. **Startup validation.** The worker rejects missing or URL-less Targets with a named error.
5. **`COMPUTE_UNAVAILABLE`.** Search and QA tools map unconfigured/unreachable embed Targets to 503.
6. **Image tagging.** `tasks.py` `fake`/`gpu` tags and digest output.
7. **Runbook.** `backend/deploy/vast/README.md`: account env vars, template fields, offer filters,
   On-start script, finding the external port, tunnels, `.env` update and worker restart, smoke
   checks (`/ping`, authenticated `/info`, fake pipeline), destroy, known search limit.
8. **Live check (manual, recorded separately).** Fake image on `vast` end to end, then the GPU
   image with the user's capture; record image digests, GPUs and results in
   GPU-INTEGRATION.

## Tests (local, fake Algorithms)
- Pipeline config expands `${GPU_TARGET}`-style variables.
- The worker refuses to start with an unset Target variable or an HTTP Target without a URL.
- Search returns 503 `COMPUTE_UNAVAILABLE` when the embed Target is unreachable.
- Existing REST API and compute contract seams keep passing with env-selected Targets.

## Information the user supplies later
- Docker Hub username/repository (`COMPUTE_IMAGE_REPO`) and `docker login` on the local machine.
- Vast.ai account, credit, and account-level `COMPUTE_TOKEN` / `HF_TOKEN`.
- Instance URL (`VAST_URL`) after renting.
- Results of the live checks.
