# Local GPU and generic Docker hosts

Status: written for portability; not exercised during development. Docker with the NVIDIA
Container Toolkit and a Linux amd64 GPU host is required. The 6 GB local GPU may run fakes but
does not establish support for every real model.

## Local Compose profile

From the repository root, use `uv run tasks.py up-local-gpu`. Select `local_gpu` as the pipeline's
`default_gpu_target`. The compute service shares the Scene data volume with the API and worker,
so `shared_storage: true` skips HTTP file transfers. Model weights bind-mount the host cache.
Check `/ping` from inside the Compose network and inspect `/info`; no public port is required.

## Publish the portable image

Set `COMPUTE_IMAGE` to your registry/tag and authenticate Docker to that registry. From the repository root,
run `uv run tasks.py compute-image` then `uv run tasks.py push-compute-image`.
The build uses repository-root context and `--platform linux/amd64`. `--extras recon` or
`--extras perception` builds a real GPU variant; the default image runs contract fakes.
Registry credentials stay with Docker, outside the image.

## Generic host

Create a private environment file on the remote host containing `COMPUTE_TOKEN` and, if needed,
`HF_TOKEN`. Run this on the Docker host, substituting the image tag:

```sh
docker run -d --name scene-compute --gpus all --restart unless-stopped \
  --env-file compute.env -e PORT=9000 -e DATA_DIR=/data -e MODELS_DIR=/models \
  -e HF_HOME=/models/hf -e TORCH_HOME=/models/torch \
  -v scene-compute-data:/data -v scene-models:/models \
  -p 127.0.0.1:9000:9000 ghcr.io/OWNER/scene-compute:TAG
```

Expose it through an authenticated TLS reverse proxy or a private tunnel. For public reachability,
`COMPUTE_TOKEN` is mandatory; configure the proxy to preserve `X-Compute-Token` and allow bodies
of at least 25 MB. Set `GENERIC_COMPUTE_URL` and the matching token locally. The `generic`
entry in `config/compute.yaml` uses HTTP with non-shared storage; select `generic` in the pipeline.
The API and worker remain local. Check `/ping`, authenticated `/info`, then a fake Compute Run.

The model download task (`uv run tasks.py download-models`) populates the host model cache without
GPU inference. Full reset removes Scene/database state while retaining that cache. A remote cache
requires downloading on that host or copying the cache there; local download alone does not warm
the remote volume.
