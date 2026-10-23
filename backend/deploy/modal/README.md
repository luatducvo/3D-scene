# Modal targets

Status: API options verified against official documentation on 2026-10-13; live deployment,
browser processing and scale-to-zero recovery have not been exercised. They require the user's
Modal account and credentials. This guide does not claim M2 acceptance has passed.

## One-time setup

Create a Modal account and configure billing in the Modal dashboard. From a terminal, run
`uvx modal setup` and complete the browser login. Create a Modal Secret named `scene-compute`
in the dashboard containing a random `COMPUTE_TOKEN`, and `HF_TOKEN` when using gated models.
Keep the same compute token in the local backend environment. SAM 3 additionally requires
the Hugging Face account to have accepted its gated access terms.

## Deploy and connect

From the repository root, run `uv run main.py deploy-modal`. Modal prints the deployed URL. The deployment
uploads source and builds `Dockerfile.compute` remotely using the repository root
as build context; it does not require uploading a locally built CUDA image.

Set `MODAL_COMPUTE_URL` to the printed URL and `COMPUTE_TOKEN` locally. Select
`config/pipeline.fake-gpu.yaml` as `PIPELINE_CONFIG` and `config/compute.yaml` as `COMPUTE_CONFIG`,
set `GPU_TARGET=modal`, then run `uv run main.py up`. Every GPU Stage of the fake pipeline
uses `GPU_TARGET`. The default image contains fakes only.

The real pipeline uses the GPU image, which holds every GPU Algorithm:
`uv run main.py deploy-modal --variant gpu` deploys it as the Modal app `scene-compute-gpu`.
Set `MODAL_COMPUTE_URL` to the printed URL, select `config/pipeline.yaml` and keep
`GPU_TARGET=modal`. Choose a GPU with at least 48 GB of VRAM, because every model stays loaded
([compute.md](../../../docs/architecture/compute.md#the-gpu-image)).

The app uses one GPU container with concurrent HTTP requests so polling remains available during
a Compute Run. Model downloads persist in the `scene-models` Volume at `/models`; Scene files
under `/data` are disposable. An idle container may scale to zero after 600 seconds. The worker
retries readiness for up to 900 seconds and uploads missing inputs again by checksum.

## Acceptance to run with credentials

1. Check `/ping`, then authenticated `/info`; confirm version and installed Algorithms.
2. Create a Scene, upload synthetic images and Process in the browser with fake GPU Stages on Modal.
   Confirm eight completed Stages, ready status, mesh and boxes.
3. Verify transferred output checksums against local files and repeat to check unchanged-file skip.
4. Wait for scale-to-zero, process another Scene, and confirm cold start is awaited successfully.
5. Delete a Scene and verify its remote Workspace is absent.

Do not redeploy during a Compute Run: a replacement container does not inherit the old in-memory
execution. Keep one container until Compute Run state is made portable across workers.

## Verified API choices

`Image.from_dockerfile` accepts `context_dir` and `build_args`; see the
[Image reference](https://modal.com/docs/sdk/py/latest/Image#from_dockerfile).
`web_server` exposes an HTTP process with `startup_timeout`; see the
[web_server reference](https://modal.com/docs/sdk/py/latest/web_server).
`concurrent(max_inputs=16)` permits overlapping requests; see
[concurrent](https://modal.com/docs/sdk/py/latest/concurrent).
Function scaling supports `max_containers`, `min_containers`, `scaledown_window` and separate
startup timeout; see [App.function](https://modal.com/docs/sdk/py/latest/App).
These checks establish documented API support, not a successful image build or GPU inference.
