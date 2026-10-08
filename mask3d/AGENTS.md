# Mask3D guidance

Read [root AGENTS.md](../AGENTS.md) and [current status](../docs/project-status.md)
first. Read [ADR 0008](../docs/adr/0008-mask3d-spike-results.md) before changing
the model, build environment or voxel policy.

## Service boundary

- `server.py` exposes health and inference through volume paths confined to
  `/data`. It serializes requests and starts a child inference process; OOM retry
  uses a fresh process at the fallback voxel size.
- `infer.py` performs inference and writes masks aligned to the source mesh's
  vertex order. `backend/src/s3d_app/instances.py` supplies shared postprocessing
  code copied by the Docker build; inspect that file when changing mask outputs.
- The backend obtains GPU admission and unloads the local LLM before calling
  this service. Preserve that coordination and process exit to reclaim VRAM.
- This image has its own pinned Python/PyTorch/CUDA/MinkowskiEngine environment,
  separate from the backend `uv` environment. Use the Dockerfile as the source
  of build versions and architecture flags.

## Verification

Lint from the repository root with
`uv run --project backend --frozen ruff check mask3d`.
For mask/postprocessing changes, run `backend/tests/test_instances.py` through
the backend environment. Inference/build changes additionally need a real Docker
and GPU check against isolated Scene data: record voxel size, mask correspondence,
timing, measured VRAM and any retry. `spike.py` supports feasibility experiments;
the [existing measurements](../docs/spikes/mask3d.json) are historical evidence.

Preserve the user's compiled image backup and named volumes. Rebuild this costly
image when the changed service/build code requires it, then update the dated
verification record and current status.
