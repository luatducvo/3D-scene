# Vast.ai targets

Status: written for the first live provider check; not yet exercised. Instances are rented by hand in the Vast web
console; no provider code runs in the application. See the [Vast CLI hello world](https://docs.vast.ai/cli/hello-world)
and [template settings](https://docs.vast.ai/guides/templates/template-settings) for console details.

scene-compute runs on one Target, `vast`, which is one rented instance. The same Target runs
either the fake image or the GPU image, which holds every GPU Algorithm.

## 1. Publish the images

Create a public Docker Hub repository, run `docker login`, and set
`COMPUTE_IMAGE_REPO=<dockerhub-user>/scene-compute` in `backend/.env`. From the repository root:

```bash
uv run main.py push-compute-image
uv run main.py push-compute-image --extras gpu
```

Tags are `fake-<sha>` and `gpu-<sha>` for the current commit; each push prints the digest to record
with the live check. The GPU image exceeds 10 GB.

## 2. Account secrets

In the Vast console, open account settings → Environment Variables and add `COMPUTE_TOKEN` (the same
value as in `backend/.env`) and `HF_TOKEN` (gated SAM 3 weights). Never put them in a template:
template variables are visible to anyone holding the template link.

## 3. Template (one per image)

| Field | Value |
|---|---|
| Image | `<dockerhub-user>/scene-compute:fake-<sha>` or `:gpu-<sha>` |
| Launch mode | Interactive shell server, SSH |
| Docker options | `-p 9000:9000 -e PORT=9000 -e DATA_DIR=/data -e MODELS_DIR=/workspace/models -e HF_HOME=/workspace/models/hf -e TORCH_HOME=/workspace/models/torch` |
| Disk | fake 20 GB; GPU image: weights + 30 GB |
| Visibility | Private |

In SSH mode Vast does not run the image command, so the On-start script starts the server.
Weights download first; until uvicorn listens, the worker's readiness retries keep waiting.

```sh
export PATH=/app/.venv/bin:$PATH
mkdir -p /data /workspace/models
cd /app
python -m scene_compute.download_models > /var/log/scene-download.log 2>&1
nohup uvicorn scene_compute.server:app --host 0.0.0.0 --port 9000 > /var/log/scene-compute.log 2>&1 &
```

The fake image installs no heavy Algorithms, so the download step only prints `skip` lines.

## 4. Choose an offer

Filter: verified, on-demand (not interruptible), 1 GPU, CUDA ≥ 12.8 (the image uses CUDA 12.8.1),
reliability > 98%, enough disk. VRAM: GPU image ≥ 48 GB (every model stays loaded after it first
runs; Depth Anything 3 sees up to 200 keyframes in one pass; more than 80 needs 80 GB), fake any GPU. Sort by price. An interruptible
instance reclaimed during a Compute Run fails the Job; there is no transparent recovery.

## 5. Connect

Wait until the instance is running and `/var/log/scene-compute.log` shows uvicorn listening.
Open the instance's IP Port Info: the line `PUBLIC_IP:EXTERNAL_PORT -> 9000/tcp` gives the URL.
Inside the instance, `echo $VAST_TCP_PORT_9000` prints the same external port.

**Fake image (synthetic data):** connect directly. In `backend/.env`:

```sh
PIPELINE_CONFIG=/app/backend/config/pipeline.fake-gpu.yaml
GPU_TARGET=vast
VAST_URL=http://PUBLIC_IP:EXTERNAL_PORT
```

**Real captures:** room photos must not cross the internet unencrypted, so open an SSH tunnel
from a terminal that stays open for the whole Job (SSH host and port from the instance's connect
dialog):

```bash
ssh -p SSH_PORT root@SSH_HOST -N -L 9001:localhost:9000
```

```sh
PIPELINE_CONFIG=/app/backend/config/pipeline.yaml
GPU_TARGET=vast
VAST_URL=http://host.docker.internal:9001
```

The worker reads Targets once at startup and refuses to start when a selected Target is unset or
has no URL. After every edit, recreate the containers so they see the new values:

```bash
uv run main.py up
```

## 6. Smoke check

```bash
curl -i http://PUBLIC_IP:EXTERNAL_PORT/ping
```

```bash
curl -H "X-Compute-Token: $COMPUTE_TOKEN" http://PUBLIC_IP:EXTERNAL_PORT/info
```

`/ping` returns 200 when ready; `/info` lists the image's Algorithms and GPU. Then create a Scene
with the synthetic images and Process it with the fake pipeline: all eight Stages complete, files
round-trip by checksum, and deleting the Scene removes its remote Workspace.

## 7. Finish a session

Destroy the instance in the console. Stopping keeps the disk billed and may not restart if the
GPU is rented by someone else; destroying removes the Workspace and weights, which the next
On-start downloads again. Clear `VAST_URL` (or `GPU_TARGET`) and run `uv run main.py up`
so the worker reports the missing Target instead of waiting 900 s on a dead URL.

## Known limits

- Free-text Search embeds the query on `GPU_TARGET`. Without a running GPU instance it
  fails with `COMPUTE_UNAVAILABLE` (HTTP 503); the viewer, Object list and measurements
  still work.
- A new instance has a new URL; Stages already completed are not rerun after switching, because the
  config hash excludes the Target.
- A container restart during a Compute Run fails that Job.
