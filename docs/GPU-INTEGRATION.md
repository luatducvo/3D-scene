# GPU integration

What each GPU adapter assumes about its upstream model, what still has to be checked on a real GPU,
and the log of those checks. Automated tests cover only the fakes and the NumPy paths; nothing here
is proven until a row in the [live check log](#live-check-log) says so. Live checks need a
configured GPU provider ([compute.md](architecture/compute.md#providers)), gated SAM 3 access and a
room capture. Package pins and the GPU image are in [compute.md](architecture/compute.md#the-gpu-image).

## Adapter contracts

Interfaces checked against upstream source on 2026-10-13.

**Depth Anything 3** (`recon.da3`, [README](https://github.com/ByteDance-Seed/Depth-Anything-3),
`api.py`/`specs.py`, [ADR-0003](adr/0003-depth-anything-3-point-cloud.md)).
`DepthAnything3.from_pretrained`, then `inference(images, use_ray_pose, ref_view_strategy,
process_res, process_res_method)` returns a `Prediction` with `depth`, `conf`, `extrinsics`,
`intrinsics`, `processed_images` and `is_metric`. The model is `depth-anything/DA3NESTED-GIANT-LARGE-1.1`
(CC BY-NC 4.0), whose depth and poses are already metric; the adapter refuses a Prediction with
`is_metric` unset. Extrinsics are OpenCV world-to-camera and are inverted to camera-to-world poses.
The least confident 10 % of pixels and invalid depth are masked. Writes `recon/rgb/*.png` and
`recon/frames/*.npz`.

**GeoCalib** (`align.geocalib_ransac`, [inference example](https://github.com/cvg/GeoCalib#setup-and-demo),
[Gravity class](https://github.com/cvg/GeoCalib/blob/main/geocalib/gravity.py)).
`GeoCalib().load_image`, `calibrate`, then `gravity.vec3d`; at zero roll/pitch the vector is
`(0,-1,0)`, upward in OpenCV camera axes. The adapter rotates it through the camera poses and
combines the estimates robustly; plane fitting and alignment are described in
[pipeline.md](architecture/pipeline.md). A capture without a floor or walls fails clearly.

**SAM 3** (`segment.sam3`, [Ultralytics](https://docs.ultralytics.com/models/sam-3/) 8.4.177, AGPL-3.0,
[ADR-0002](adr/0002-single-gpu-image-ultralytics-sam3.md)).
`SAM3SemanticPredictor(overrides=...)`, `set_image`, then `inference_features(features, src_shape,
text=[...])`. It filters by `args.conf`, applies per-class NMS and returns boolean masks already
resized to the source image, with `(x1, y1, x2, y2, score, class)` boxes whose class column indexes
the text batch. `quantize: 16` selects fp16. The gated `sam3.pt` comes from `facebook/sam3` through
`hf_hub_download`.

**MetaCLIP 2** (`embed.metaclip2`, [model configuration](https://huggingface.co/facebook/metaclip-2-worldwide-huge-quickgelu/blob/main/config.json),
[Transformers 4.57.6 implementation](https://github.com/huggingface/transformers/blob/v4.57.6/src/transformers/models/metaclip_2/modeling_metaclip_2.py)).
`AutoModel`, `AutoProcessor`, `get_image_features` and `get_text_features` return feature tensors.
The configuration sets projection dimension 1024, matching the database; the adapter checks it at
runtime. Image and text vectors use the same model and L2 normalization. The pin
`transformers>=4.56,<5` holds this contract; a major-version update needs it checked again.

## Manual acceptance still required

1. Build and push the GPU image, inspect `/info`, and download weights into the provider's cache.
2. Process a room capture on the configured provider. Confirm a dense, complete colored point cloud
   in the viewer, plausible metric dimensions, z=0 floor and axis-aligned walls.
3. Inspect mask alignment with RGB, multi-view Object identities and evidence crops. Check that one
   physical thing is one Object (segment `containment_threshold`, lift `merge_overlap`) and that
   parts such as handles and outlets remain their own Objects.
4. Search visible objects in both English and Vietnamese and check the ranking/highlights
   (`SEARCH_MARGIN`).
5. Check Object Membership ([ADR-0009](adr/0009-show-objects-by-membership.md)): the Scene's
   `membership_url` is set, hover labels and highlights match the right points in point cloud and
   mesh view, nested parts pick before their whole, and hovering stays smooth on the full cloud.
6. Confirm `mesh.tsdf` and `lift.maskclustering` run on CuPy (`device: cuda`) and match the NumPy
   path the tests cover. If SAM 3 runs out of memory, lower `prompt_batch_size`.
7. Record model versions, image digest and observed results below before marking GPU quality

