# GPU integration evidence

Checked 2026-10-13. These are implementation references, not successful inference results.
Live checks need a configured GPU provider (Vast.ai first, see the [Vast runbook](../backend/deploy/vast/README.md)),
gated SAM 3 access and the user's room capture.

| Adapter | Verified upstream interface | Local artifact |
|---|---|---|
| MapAnything | `MapAnything.from_pretrained`, `load_images`, `infer`; per-view metric depth, confidence, validity mask, RGB, intrinsics and camera-to-world pose | `recon/rgb/*.png`, `recon/frames/*.npz` |
| GeoCalib | `GeoCalib().load_image`, `calibrate`, `gravity.vec3d` | aligned Frame archives, transform Manifest and planes |
| SAM 3 | `build_sam3_image_model`, `Sam3Processor.set_image`, `set_text_prompt`; masks and scores | masks, labels and scores per selected Frame |
| MetaCLIP 2 | Transformers 4.x `AutoModel`, `AutoProcessor`, `get_image_features`, `get_text_features` | normalized 1024-dimensional image/text vectors |

MapAnything's [official README](https://github.com/facebookresearch/map-anything#image-only-inference)
documents the inference arguments and output keys. Its outputs are already metric; the adapter
records the scaling factor without scaling depth or translation twice. Invalid geometry is masked.
The project leaves Torch and CUDA versions unpinned.

GeoCalib's [inference example](https://github.com/cvg/GeoCalib#setup-and-demo) defines the model call.
Its [Gravity class](https://github.com/cvg/GeoCalib/blob/main/geocalib/gravity.py) exposes `vec3d`;
at zero roll/pitch the vector is `(0,-1,0)`, upward in OpenCV camera axes. The adapter rotates it
through camera poses, robustly combines estimates, fits horizontal/vertical planes and aligns
the floor and Manhattan wall directions. Absence of a floor or walls fails clearly.

SAM 3's [setup](https://github.com/facebookresearch/sam3#installation) requires Python >=3.12,
Torch >=2.7 and CUDA >=12.6; it currently recommends Torch 2.10.0 with CUDA 12.8.
Its [package metadata](https://github.com/facebookresearch/sam3/blob/main/pyproject.toml) requires
NumPy >=1.26,<2, which must be respected across the workspace. The compute Dockerfile uses CUDA
12.8.1. PyTorch/Torchvision pins still require a complete GPU image build and inference check;
compatible declared versions do not prove every kernel works together.

MetaCLIP's [model configuration](https://huggingface.co/facebook/metaclip-2-worldwide-huge-quickgelu/blob/main/config.json)
sets projection dimension 1024, matching the database. The adapter checks it at runtime.
The [Transformers 4.57.6 implementation](https://github.com/huggingface/transformers/blob/v4.57.6/src/transformers/models/metaclip_2/modeling_metaclip_2.py)
returns feature tensors. Use `transformers>=4.56,<5` for this adapter; a major-version update needs
its output contract checked. Image and text vectors use the same model and L2 normalization.

## Manual acceptance still required

1. Build and push the heavy images, inspect `/info`, and download weights into the provider's cache.
2. Process a room capture on the configured provider. Confirm plausible metric dimensions, z=0 floor and axis-aligned walls.
3. Inspect mask alignment with RGB, multi-view Object identities, boxes and evidence crops.
4. Search visible objects in both English and Vietnamese and check the ranking/highlights.
5. Record model versions, image digest and observed results before marking GPU quality tickets verified.

No fallback model substitutes for an unavailable dependency or failed inference. The fake pipeline
is explicitly configured and only validates application/transport behavior.

## Live check log

Live checks are manual and recorded here, separately from local tests. One row per check.

| Date | Provider / Target | Image tag and digest | GPU | Check | Result |
|---|---|---|---|---|---|
| | Vast.ai / `vast_recon` | `fake-<sha>` | | fake pipeline end to end, checksums, Workspace delete | not yet run |
| | Vast.ai / `vast_recon` + `vast_perception` | `recon-<sha>`, `perception-<sha>` | | room capture, acceptance items 2–4 | not yet run |
