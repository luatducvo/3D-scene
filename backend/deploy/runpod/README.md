# RunPod targets

Status: documented only; neither Pod nor Serverless was exercised during development.
Both run the same registry image produced by `uv run tasks.py push-compute-image`.
Use a pinned tag or digest built for Linux amd64. A nonempty `COMPUTE_TOKEN` is mandatory behind
the public proxy, including when the provider also requires an API key.

## Pod

Create a custom GPU Pod template with the image and expose HTTP port `9000`. Preserve the image
start command. Set `PORT=9000`, `DATA_DIR=/data`, `MODELS_DIR=/workspace/models`,
`HF_HOME=/workspace/models/hf`, `TORCH_HOME=/workspace/models/torch`, `COMPUTE_TOKEN`, and
`HF_TOKEN` for gated weights. Attach persistent storage mounted at `/workspace`; keep model
weights there. Scene data is a disposable cache and can remain on container disk.

Set `RUNPOD_POD_URL=https://POD_ID-9000.proxy.runpod.net` locally. The `runpod_pod` target in
`config/compute.yaml` sends `X-Compute-Token`. Select it through the pipeline's Target variables.
Pods run until stopped; idle timeout and worker autoscaling settings below apply to Serverless.
See [RunPod HTTP ports](https://docs.runpod.io/pods/configuration/expose-ports).

## Serverless load-balancing endpoint

Import the registry image as a Serverless endpoint and select **Load Balancer**. This product routes
custom HTTP paths to the process; the queue-based handler product has a different contract.
Set maximum workers to **1** and minimum workers to **0** (or 1 to keep it warm). Set the idle
timeout to **600 seconds**, above the worker's 3-second poll interval. Preserve the image command.
Set `PORT=9000` and `PORT_HEALTH=9000`; health probes use `/ping`.

Attach a network volume, mounted at `/runpod-volume`. Set `MODELS_DIR=/runpod-volume/models`,
`HF_HOME=/runpod-volume/models/hf`, `TORCH_HOME=/runpod-volume/models/torch`, `DATA_DIR=/data`,
`COMPUTE_TOKEN`, and `HF_TOKEN` if required. Choose a GPU large enough for the selected methods.

Set `RUNPOD_SERVERLESS_URL=https://ENDPOINT_ID.api.runpod.ai` and `RUNPOD_API_KEY` locally.
The `runpod_serverless` config entry sends provider `Authorization: Bearer ...` and application
`X-Compute-Token` independently. Select that target in the pipeline.

RunPod documents a 30 MB body limit; configured chunks are 25,000,000 bytes. Calls finish in under
30 seconds and long Compute Runs are polled. Cold-start readiness retries last up to 900 seconds.
One worker is required because the active Compute Run belongs to the process that accepted it.
A container restart during a Compute Run is a failed execution, not transparent recovery.

See [load-balancing worker setup](https://docs.runpod.io/serverless/load-balancing/build-a-worker),
[endpoint settings](https://docs.runpod.io/serverless/endpoints/endpoint-configurations),
[network volumes](https://docs.runpod.io/storage/network-volumes), and
[RunPod's load-balancer reference](https://github.com/runpod/runpod-plugins-official/blob/main/plugins/runpod/skills/runpod/golden-paths/14-load-balancing-endpoint.md).
Check `/ping` and authenticated `/info`, run a fake pipeline, then verify file checksums and
Workspace deletion before using real captures. Record the result as a manual check when exercised.
