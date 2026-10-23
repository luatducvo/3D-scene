# 3D Scene Understanding

Turn photos or one short video of a room into a metric 3D Scene: a point cloud and mesh, the Objects in it with their sizes and spatial Relations, and text Search over those Objects.

The pipeline runs Depth Anything 3 for reconstruction, GeoCalib for gravity alignment, TSDF fusion for the mesh, SAM 3 for open-vocabulary segmentation, mask clustering to lift masks into 3D Objects and MetaCLIP 2 for embeddings. Every model Stage also has a fake that runs on a CPU, so the whole system works without a GPU.

## Requirements

- [uv](https://docs.astral.sh/uv/) (Python 3.12 is installed by uv)
- Docker with Compose
- Node.js 24 and npm, for frontend development
- For real models: a CUDA GPU host with at least 48 GB of VRAM, local or rented

## Quick start

```bash
uv run main.py up        # Postgres, scene-api, scene-worker and the frontend
```

Open http://localhost:3000. On first run `main.py` creates `backend/.env` from `backend/.env.example`; with the defaults every Stage runs as a fake on the CPU.

`uv run main.py --help` lists every command, including `down`, `reset` (deletes all Scenes), `test` and `lint`.

## Frontend only

```bash
cd frontend
npm install
NEXT_PUBLIC_API_MODE=mock npm run dev
```

Mock mode serves a demo Scene from the browser; no backend is needed.

## Real models on a GPU

1. Build and push the GPU image: set `COMPUTE_IMAGE_REPO` in `backend/.env`, then `uv run main.py push-compute-image --extras gpu`.
2. Run it on a Provider following `backend/deploy/<provider>/README.md` (Modal, RunPod, Vast.ai, Colab, or any Docker host).
3. In `backend/.env`, set the Provider's URL variable, `COMPUTE_TOKEN`, `GPU_TARGET` to the Target name from `backend/config/compute.yaml`, and `PIPELINE_CONFIG=/app/backend/config/pipeline.yaml`. Try `pipeline.fake-gpu.yaml` first to check the connection.
4. `uv run main.py up`.

With a local NVIDIA GPU, `uv run main.py download-models` and `uv run main.py up-local-gpu` run scene-compute on this machine (`GPU_TARGET=local_gpu`, `LOCAL_GPU_EXTRAS=gpu`).

## Documentation

- [GLOSSARY.md](GLOSSARY.md): the domain terms
- [docs/architecture/overview.md](docs/architecture/overview.md): how it fits together
- [docs/extending.md](docs/extending.md): adding Algorithms, Relations, endpoints and Targets
