# Google Colab GPU Target

Runs `scene-compute` on a Google Colab GPU runtime and exposes it to your machine through a free
Cloudflare Tunnel. The notebook [scene_compute_colab.ipynb](scene_compute_colab.ipynb) holds every
command; this guide explains the steps and what to configure locally.

## How it works

```
your machine                                        Google Colab
web · scene-api · postgres                          scene-compute (uvicorn, port 9000)
scene-worker ── HTTPS (tunnel URL, 100 MB chunks) ─> cloudflared → https://<random>.trycloudflare.com
```

Every Stage runs on Colab, and uploads are stored there too; only the results return to your
machine after the last Stage ([ADR-0005](../../../docs/adr/0005-whole-pipeline-on-gpu-host.md)).
Every request finishes in under 300 s and bodies stay under 100 MB, so the tunnel's limits never apply.

## Run the notebook

Open the notebook in Colab and run its cells in order:

1. **GPU check.** Runtime → Change runtime type → pick a GPU, then `nvidia-smi`.
2. **uv and Python 3.12.**
3. **Clone the repository** into `/content/3D-scene` (set `REPO_URL`; for a private repository use a
   token URL or upload a zip without `.venv`, `.git`, `data` and `models`).
4. **Install** `uv sync --python 3.12 --package scene-compute --extra gpu`. Drop `--extra gpu` for
   the fake image's dependencies when you only want to test the connection.
5. **Model cache.** Mounts Google Drive and sets `MODELS_DIR` there, so weights
   (over 10 GB) download once and survive runtime resets. Set `HF_TOKEN` for gated SAM 3 weights.
   Before downloading, the cell prints `cached` for each model already complete on Drive and
   `download` with the missing files for each model it will fetch. It then waits for Drive to
   finish uploading new weights (`drive.flush_and_unmount()`) and mounts Drive again, so a later
   runtime reset cannot lose a half-uploaded file.
6. **Tunnel.** Starts `cloudflared` for port 9000 and prints the public URL.
7. **Server.** Read `COMPUTE_TOKEN` from Colab secrets, then start uvicorn on port 9000, reusing
   the cache configuration from step 5 without printing the token. The cell sets
   `CLEAN_ON_START=1`, so every server start empties `/content/data`. Keep this cell running while
   you use the web app.

## Configure your machine

In `backend/.env`:

```dotenv
GPU_TARGET=colab
COLAB_URL=https://<random>.trycloudflare.com   # from step 6
COMPUTE_TOKEN=<same token as step 7>
PIPELINE_CONFIG=/app/backend/config/pipeline.fake-gpu.yaml   # first, to test the connection
# PIPELINE_CONFIG=/app/backend/config/pipeline.yaml          # then, real models
```

Then run `uv run main.py up` so the worker reads the new values.

## Smoke test

```bash
curl -i https://<random>.trycloudflare.com/ping
curl -H "X-Compute-Token: <token>" https://<random>.trycloudflare.com/info
```

`/ping` returns 200; `/info` lists the GPU name and the registered Algorithms. Then process a Scene
from <http://localhost:3000>.

## Limits

- **VRAM.** The Executor keeps every model loaded, and the real pipeline is sized for at least
  48 GB ([ADR-0002](../../../docs/adr/0002-single-gpu-image-ultralytics-sam3.md)). A T4 (about
  15 GB) is enough for the fake pipeline, not for every real model at once; for real models use an
  80 GB A100 runtime and keep `max_keyframes` in [pipeline.yaml](../../config/pipeline.yaml) at 80
  or lower.
- **Session lifetime.** Colab disconnects idle or closed tabs. A runtime restart or a server restart
  deletes uploads and intermediate outputs: create a new Scene and upload again. Already processed
  Scenes stay viewable locally; search needs the server running.
- **New URL per tunnel.** Each run of step 6 prints a new URL: update `COLAB_URL` and run
  `uv run main.py up` again.

Record live results in [GPU-INTEGRATION.md](../../../docs/GPU-INTEGRATION.md#live-check-log).
