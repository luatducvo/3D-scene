# GPU integration evidence

Checked 2026-10-13. These are implementation references, not successful inference results.
Live checks need a configured GPU provider (Vast.ai first, see the [Vast runbook](../backend/deploy/vast/README.md)),
gated SAM 3 access and the user's room capture.

| Adapter | Verified upstream interface | Local artifact |
|---|---|---|
| Depth Anything 3 | `DepthAnything3.from_pretrained`, `inference(images, use_ray_pose, ref_view_strategy, process_res, process_res_method)`; `Prediction.depth`, `conf`, `extrinsics` (world-to-camera), `intrinsics`, `processed_images`, `is_metric` | `recon/rgb/*.png`, `recon/frames/*.npz` |
| GeoCalib | `GeoCalib().load_image`, `calibrate`, `gravity.vec3d` | aligned Frame archives, transform Manifest and planes |
| SAM 3 (Ultralytics) | `SAM3SemanticPredictor(overrides=...)`, `set_image`, `inference_features(features, src_shape, text=[...])`; boolean masks and `(x1, y1, x2, y2, score, class)` boxes | masks, labels and scores per selected Frame |
| MetaCLIP 2 | Transformers 4.x `AutoModel`, `AutoProcessor`, `get_image_features`, `get_text_features` | normalized 1024-dimensional image/text vectors |

Depth Anything 3's [README](https://github.com/ByteDance-Seed/Depth-Anything-3) and its
`api.py`/`specs.py` define the inference arguments and the `Prediction` fields. The adapter uses
`depth-anything/DA3NESTED-GIANT-LARGE-1.1` (CC BY-NC 4.0), whose depth and poses are already metric;
it refuses a Prediction with `is_metric` unset. Extrinsics are OpenCV world-to-camera and are
inverted to camera-to-world poses. The least confident 10 % of pixels and invalid depth are masked.
DA3 pins `numpy<2` and depends on xformers, which fixes the Torch version. xformers 0.0.35, the
newest release, ships kernels built for Torch 2.10 + CUDA 12.8; with Torch 2.14 they fail to load and
DA3 falls back to slower, memory-hungry attention. The `gpu` extra therefore pins Torch 2.10,
torchvision 0.25 and xformers 0.0.35 (NumPy 1.26.4; 2026-10-17). See [ADR-0003](adr/0003-depth-anything-3-point-cloud.md).

GeoCalib's [inference example](https://github.com/cvg/GeoCalib#setup-and-demo) defines the model call.
Its [Gravity class](https://github.com/cvg/GeoCalib/blob/main/geocalib/gravity.py) exposes `vec3d`;
at zero roll/pitch the vector is `(0,-1,0)`, upward in OpenCV camera axes. The adapter rotates it
through camera poses, robustly combines estimates, fits horizontal/vertical planes and aligns
the floor and Manhattan wall directions. Absence of a floor or walls fails clearly.

SAM 3 runs through [Ultralytics](https://docs.ultralytics.com/models/sam-3/) (AGPL-3.0, see
[ADR-0002](adr/0002-single-gpu-image-ultralytics-sam3.md)). The adapter was written against
`ultralytics==8.4.177`: `SAM3SemanticPredictor.inference_features` filters by `args.conf`, applies
per-class NMS and returns masks already resized to the source image, with the class column indexing
the text batch. `quantize: 16` selects fp16. The gated `sam3.pt` comes from `facebook/sam3` through
`hf_hub_download`. Ultralytics' [CLIP fork](https://github.com/ultralytics/CLIP) is declared as a
dependency so nothing is installed at runtime. Every GPU Algorithm resolves in one environment. The compute
Dockerfile uses CUDA 12.8.1. NumPy 1.26.4 (required by Depth Anything 3) also satisfies Ultralytics. PyTorch/Torchvision pins still require a complete GPU image build and
inference check; compatible declared versions do not prove every kernel works together.

MetaCLIP's [model configuration](https://huggingface.co/facebook/metaclip-2-worldwide-huge-quickgelu/blob/main/config.json)
sets projection dimension 1024, matching the database. The adapter checks it at runtime.
The [Transformers 4.57.6 implementation](https://github.com/huggingface/transformers/blob/v4.57.6/src/transformers/models/metaclip_2/modeling_metaclip_2.py)
returns feature tensors. Use `transformers>=4.56,<5` for this adapter; a major-version update needs
its output contract checked. Image and text vectors use the same model and L2 normalization.

## Manual acceptance still required

1. Build and push the GPU image, inspect `/info`, and download weights into the provider's cache.
2. Process a room capture on the configured provider. Confirm a dense, complete colored point cloud in the viewer, plausible metric dimensions, z=0 floor and axis-aligned walls.
3. Inspect mask alignment with RGB, multi-view Object identities, boxes and evidence crops.
4. Search visible objects in both English and Vietnamese and check the ranking/highlights.
5. Record model versions, image digest and observed results before marking GPU quality tickets verified.

No fallback model substitutes for an unavailable dependency or failed inference. The fake pipeline
is explicitly configured and only validates application/transport behavior.

## Live check log

Live checks are manual and recorded here, separately from local tests. One row per check.

| Date | Provider / Target | Image tag and digest | GPU | Check | Result |
|---|---|---|---|---|---|
| | Vast.ai / `vast` | `fake-<sha>` | | fake pipeline end to end, checksums, Workspace delete | not yet run |
| | Vast.ai / `vast` | `gpu-<sha>` | ≥ 48 GB | room capture, acceptance items 2–4 | not yet run |
