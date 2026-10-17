# 3D Scene Understanding System

[English](README.md) | [Tiếng Việt](README.vi.md)

Turns RGB photos or a short video of a room into a metric 3D Scene: Keyframe selection, camera
poses and depth, gravity alignment, a dense point cloud and mesh, open-vocabulary 3D Objects, a
Scene Graph, and an interactive 3D viewer with grounded question answering in English or Vietnamese.

Local and single user. Everything runs with Docker Compose; heavy Stages run on a GPU host you
configure. New to the project? Read [docs/architecture/overview.md](docs/architecture/overview.md).

## Services

| Service | Port | Role |
|---|---|---|
| `postgres` (pgvector) | internal 5432 | Scenes, Job queue, progress events, Objects and embeddings |
| `scene-api` | `127.0.0.1:8000` | REST + SSE API, search, question answering |
| `scene-worker` | none | Runs Jobs on the GPU Target and publishes results |
| `scene-compute` *(profile `local-gpu`)* | internal 9000 | GPU server on a local NVIDIA GPU |
| `web` | `127.0.0.1:3000` | Next.js UI: upload, progress, 3D viewer, measuring, chat |

Storage: the `scene-data` and `postgres-data` Docker volumes hold all system state and are removed
by a reset. Model weights are cached in the host folder `./models`, which a reset keeps.

## Prerequisites

- Docker Engine 24+ with Compose v2.
- [uv](https://github.com/astral-sh/uv) for the task runner and Python tooling.
- A GPU Target: a remote host (Vast.ai, Colab, Modal, RunPod, any Docker host) or a local NVIDIA GPU
  with the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html).
  The real pipeline needs at least 48 GB of VRAM. The fake pipeline needs no GPU.
- Node.js 20+ and npm, only to run the frontend outside Docker.

## Configure

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

On Windows PowerShell use `Copy-Item backend\.env.example backend\.env` (and the same for frontend).

Key variables in `backend/.env` (the example file documents the rest):

| Variable | Meaning |
|---|---|
| `PIPELINE_CONFIG` | `pipeline.fake.yaml` (fakes on CPU, no GPU), `pipeline.fake-gpu.yaml` (fakes on `GPU_TARGET`) or `pipeline.yaml` (real models) |
| `GPU_TARGET` | Name of a Target in [compute.yaml](backend/config/compute.yaml). There is no default; the worker refuses to start without it when the pipeline needs it. |
| `VAST_URL`, `COLAB_URL`, `MODAL_COMPUTE_URL`, ... | URL of the Target you use |
| `COMPUTE_TOKEN` | Shared secret protecting remote GPU endpoints |
| `HF_TOKEN` | Hugging Face token for gated weights (SAM 3) |
| `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` | Any OpenAI-compatible endpoint for question answering |
| `COMPUTE_IMAGE_REPO` | Docker Hub repository for the GPU image |

`frontend/.env` sets `NEXT_PUBLIC_API_URL` (browser → API), `API_INTERNAL_URL` (Next.js server → API
over the `scene-net` network) and `NEXT_PUBLIC_API_MODE` (`http` or `mock`).

## Run

From the repository root:

```bash
uv run tasks.py up
```

Starts Postgres, the API, the worker and the web UI (`docker compose up -d --build`). With a local
GPU, use `uv run tasks.py up-local-gpu` instead. Stop with `uv run tasks.py down`; delete every Scene
and the database while keeping model weights with `uv run tasks.py reset`.

Then open:

- Web UI: <http://localhost:3000>. Create a Scene, upload photos or a video, press Process, then
  explore, measure and ask questions.
- API docs: <http://localhost:8000/docs>.

Logs: `docker compose logs -f scene-worker` (or `scene-api`, `web`).

Frontend only, against a mock backend (no Docker, no GPU):

```bash
cd frontend
npm ci
NEXT_PUBLIC_API_MODE=mock npm run dev
```

## Tasks

`uv run tasks.py --help` lists every task. The common ones:

| Task | Command |
|---|---|
| Run the backend tests (disposable test database) | `uv run tasks.py test` |
| Export the API contract | `uv run tasks.py openapi`, then `cd frontend && npm run api:sync` |
| Download model weights into `./models` | `uv run tasks.py download-models` |
| Show volume and model cache sizes | `uv run tasks.py disk-usage` |
| Build / push the GPU image | `uv run tasks.py compute-image` / `push-compute-image` |
| Deploy to Modal (built remotely) | `uv run tasks.py deploy-modal` |

## Build and push the GPU image

Vast.ai, RunPod and generic Docker hosts pull the `scene-compute` image from Docker Hub; Modal builds
it itself. Two variants:

| Variant | Flag | Contents | Tag |
|---|---|---|---|
| fake | *(none)* | Contract fakes only; small, for testing a provider connection | `fake-<git short sha>` |
| gpu | `--extras gpu` | Every real GPU Algorithm in one image ([ADR-0002](docs/adr/0002-single-gpu-image-ultralytics-sam3.md)); over 10 GB | `gpu-<git short sha>` |

1. Create a Docker Hub repository (public for Vast.ai) and `docker login -u <user>` with a personal
   access token.
2. Set `COMPUTE_IMAGE_REPO=<user>/scene-compute` in `backend/.env`.
3. Commit first: the tag comes from `HEAD`, but the build context is the working tree.
4. Run `uv run tasks.py push-compute-image --extras gpu` (or without `--extras` for the fake image).
   It builds for `linux/amd64` (no GPU needed on the build machine), pushes, and prints the tag and
   digest. Use the tag or digest, never `latest`, and record the digest with the live check in
   [GPU-INTEGRATION.md](docs/GPU-INTEGRATION.md).
5. Check it on a GPU machine: `docker run --rm --gpus all -p 127.0.0.1:9000:9000 <image>`, then
   open `http://localhost:9000/ping` and `/info`.

Then configure the provider ([backend/deploy/](backend/deploy/)) and set `GPU_TARGET`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `network scene-net declared as external, but could not be found` | Start the backend first, or `docker network create scene-net` |
| `could not select device driver "" with capabilities: [[gpu]]` | Install the NVIDIA Container Toolkit, or use `up` instead of `up-local-gpu` |
| `SCENE_BUSY` / `SCENE_LOCKED` | A Job is running, or the Scene was already processed: wait, or create a new Scene |
| `COMPUTE_UNAVAILABLE` on upload or search | The GPU Target is not running or its URL in `backend/.env` is stale; fix it and run `uv run tasks.py up` |
| `Pass --image or set COMPUTE_IMAGE_REPO` | Set `COMPUTE_IMAGE_REPO` in `backend/.env` or pass `--image` |
| `denied: requested access to the resource is denied` on push | `docker login` again with a read/write token; the tag must start with your user name |
| Edits to `pipeline.yaml`, `compute.yaml` or `.env` have no effect | The worker reads them at startup: `uv run tasks.py up` recreates the containers |

## Documentation

| Document | Contents |
|---|---|
| [docs/architecture/](docs/architecture/overview.md) | How the system works, starting with the overview |
| [docs/SPEC.md](docs/SPEC.md) | Scope, user stories, acceptance criteria, test seams |
| [CONTEXT.md](CONTEXT.md) | Domain language |
| [docs/adr/](docs/adr/) | Architecture decisions |
| [docs/GPU-INTEGRATION.md](docs/GPU-INTEGRATION.md) | Model interfaces and the live GPU check log |
| [backend/deploy/](backend/deploy/) | Per-provider deployment guides |
| [frontend/README.md](frontend/README.md) | UI decisions and frontend validation |
