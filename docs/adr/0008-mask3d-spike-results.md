# Mask3D: use 3 cm voxels on this RTX 3050

Measured on 2026-10-08 with Windows running, RTX 3050 6 GiB, pinned CUDA 11.3.1 image, PyTorch 1.12.1, and CUDA-enabled MinkowskiEngine 0.5.4. The checkpoint is pinned in `models.lock`. Raw-coordinate positional embeddings receive actual mesh coordinates; the packaged upstream README incorrectly passed RGB features at this seam.

| Scan | Voxel | Baseline used MiB | Peak device used MiB | Increase MiB | Torch reserved MiB | Seconds | Proposals ≥100 vertices |
| --- | --- | --- | --- | --- | --- | --- | --- |
| scene0000_00 | 2 cm | 1698 | 5571 | 3873 | 2292 | 7.18 | 87 |
| scene0000_00 | 3 cm | 1835 | 5017 | 3182 | 1682 | 7.21 | 58 |
| scene0000_01 | 2 cm | 1743 | 5602 | 3859 | 2280 | 7.59 | 84 |
| scene0000_01 | 3 cm | 1742 | 4969 | 3227 | 1650 | 7.69 | 64 |

The 2 cm configuration exceeds the 3.5 GiB stage budget. Both 3 cm runs fit that budget, so S3 uses Mask3D at 3 cm by default. These are proposals before NMS and ownership filtering. Runtime S3 performs both and discards instances owning fewer than 100 original vertices. If CUDA OOM occurs, the service retries in a new process at 4 cm and reports the applied voxel size. The parent API owns the GPU lock for the complete HTTP call.

Device measurements include the existing Windows desktop allocation. The increase is the difference between sampled peak device usage and baseline, rather than PyTorch's allocation alone. Sampling uses `nvidia-smi` at 100 ms intervals; short peaks can fall between samples. Full measurements are in `docs/spikes/mask3d.json` and can be repeated with `mask3d/spike.py`.

The inference subprocess exits after each request. The service process does not import torch or own a CUDA context. The backend and service share only volume paths and small JSON responses.

Both supplied scans completed the real pipeline and the bed, desks, cabinets and
stools were inspected in the viewer. The final CUDA-enabled image was rebuilt
from a fresh clone and saved with `docker save` to `.backups/s3d-mask3d.tar`
(5,486,678,528 bytes for the initial backup; the refreshed image is also saved).
The unaligned Package completed all GPU stages at 3 cm; its measurements are in
`docs/spikes/unaligned-pipeline.json`.
