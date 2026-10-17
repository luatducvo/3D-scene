# ADR-0002: One GPU image, SAM 3 through Ultralytics

Status: accepted. Date: 2026-10-14. Amended 2026-10-15 by [ADR-0003](0003-depth-anything-3-point-cloud.md):
MapAnything is replaced by Depth Anything 3, which requires NumPy < 2; Ultralytics, GeoCalib and
MetaCLIP 2 accept that, so the single image stands.

## Context

Meta's `sam3` package requires `numpy>=1.26,<2`, while MapAnything requires NumPy 2. The GPU
Algorithms therefore shipped as two image variants, `recon` (MapAnything, GeoCalib) and
`perception` (SAM 3, MetaCLIP 2). Every provider needed two Targets, two deployments and two
rented instances per Job, and the pipeline needed `RECON_TARGET` and `PERCEPTION_TARGET`.

Ultralytics runs the same SAM 3 checkpoint (`facebook/sam3`, gated) through
`SAM3SemanticPredictor` and accepts NumPy 2 on Linux. On 2026-10-14, MapAnything, GeoCalib,
Ultralytics 8.4.177 and MetaCLIP 2 resolved together in one `uv` environment (NumPy 2.5.4,
Torch 2.14.1).

## Decision

`segment.sam3` runs SAM 3 through Ultralytics, and Meta's `sam3` package is removed. scene-compute
has one `gpu` extra holding every GPU Algorithm, built as one image (`gpu-<sha>`) and deployed as
one Target per provider, selected by `GPU_TARGET`. The Algorithm name stays `segment.sam3` because
the method and checkpoint are unchanged; only the runtime library differs.

The Executor keeps every loaded model in VRAM; it does not evict. A GPU Target needs at least
48 GB of VRAM.

## Alternatives considered

- **Keep two images with Meta's `sam3`.** No license change, but twice the deployments, Targets and
  rented instances, and search needs the second instance running.
- **Evict models between Stages** to fit a 24 GB GPU. Rejected for now: reloading costs time on
  every Job and on the first search after it, and the eviction code does not exist yet.

## Consequences

- Ultralytics is licensed under **AGPL-3.0**. Distributing this system, or offering it as a network
  service, requires releasing the complete source of the system under AGPL-3.0, or buying an
  Ultralytics Enterprise License. This is accepted for this learning project.
- One instance runs a whole Job; switching provider changes one Target setting.
- GPU offers below 48 GB VRAM are no longer suitable.
- Ultralytics' CLIP fork is a git dependency, declared so that Ultralytics never installs packages
  at runtime.
- Segmentation quality and the new code path must be verified live on the GPU image before the GPU
  quality tickets count as verified (GPU-INTEGRATION).
