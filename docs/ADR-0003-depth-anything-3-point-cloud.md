# ADR-0003: Depth Anything 3 reconstruction, point cloud first

Status: accepted. Date: 2026-10-15.

## Context

The first real run on ScanNet `scene0000_01` used MapAnything. The viewer showed only the TSDF
mesh, which came out dark and full of holes, while the published `points.ply` held about 10,000
uncolored points per Frame and was never displayed. Depth Anything 3 (DA3) produces a complete,
dense colored point cloud from the same photos, which is the expected result. Uploaded files were
also renamed to random ids, so ingest read a sequential capture in random order.

## Decision

- `recon.da3` replaces `recon.mapanything`, which is removed from the code, the GPU image and the
  lockfile. It runs `depth-anything/DA3NESTED-GIANT-LARGE-1.1`, which predicts depth and poses in
  meters, on all Keyframes in one `inference()` call, with poses from the ray head.
- The mesh Stage writes `points.ply` as a dense colored point cloud: every pixel above the 40th
  confidence percentile (DA3's own export threshold) and off depth edges, averaged on a 1 cm voxel grid, at most
  3,000,000 points, binary PLY with colors. The TSDF mesh is still produced.
- The viewer shows the point cloud by default; the mesh and the Object boxes are toggleable layers.
- Uploads keep their sanitized original name plus a short random suffix, and ingest sorts names
  naturally, so Keyframes follow capture order.

## Alternatives considered

- **Keep MapAnything next to DA3 in one image.** DA3 requires NumPy < 2 and xformers, MapAnything
  required NumPy 2; one environment cannot hold both.
- **Lighter DA3 checkpoints (DA3-LARGE-1.1, DA3-BASE).** Cheaper and partly Apache-2.0, but their
  depth and poses are relative, which breaks the metric contract (sizes, distances, QA numbers).

## Consequences

- DA3 Nested Giant is licensed **CC BY-NC 4.0**: non-commercial use only, accepted for this
  learning project.
- The whole workspace now resolves NumPy 1.26 and pulls xformers, open3d and pycolmap into the GPU
  image. The GPU image must be rebuilt and redeployed before `recon.da3` can run.
- A GPU Target still needs at least 48 GB of VRAM; 80 Keyframes at `process_res` 504 go through
  one forward pass.
- Reconstruction quality and the inference arguments must be verified live (GPU-INTEGRATION).
