# s3dpkg/2

A Package is an uncompressed POSIX tar file named `<scan>.s3dpkg`, where `<scan>` matches
`scene[0-9]{4}_[0-9]{2}`. The archive contains no ground truth labels. Member names are
relative, use `/`, and cannot contain `..` or symbolic links.

| Member | Content |
| --- | --- |
| `manifest.json` | UTF-8 JSON metadata described below |
| `mesh/vh_clean_2.ply` | Axis-aligned ScanNet mesh and normals, unchanged vertex/face order and RGB |
| `mesh/superpoints.npy` | 1-D `int32` NumPy array, one segment id per mesh vertex |
| `calib/intrinsics.json` | Color and depth 3×3 intrinsics, image dimensions, depth shift |
| `frames/index.parquet` | Rows with `frame_id` (int), `blur` (float), `valid` (bool) |
| `frames/color/<id>.jpg` | JPEG color image, long side at most 960 by default |
| `frames/depth/<id>.png` | 16-bit unsigned PNG depth image |
| `frames/pose/<id>.txt` | 4×4 camera-to-aligned-world float matrix in text form |

`manifest.json` has `format_version: "s3dpkg/2"`, `status: "complete"`, `scan_id`,
`script_version`, `parameters`, `sens_sha256`, `coordinate_frame: "axis_aligned"`,
`source_axis_alignment` (4×4 row-major finite rigid transform), and `files`
(a mapping from every other member name to
its lowercase SHA-256 hex digest). Every listed file must be present exactly once and no
unlisted file is permitted. The manifest itself is excluded from `files` to avoid a
self-referential hash. `sens_sha256` identifies the source `.sens`; the `.sens` is not in
the Package. The source transform has affine last row `[0,0,0,1]`, an orthonormal
rotation and determinant +1. An explicitly supplied identity transform is valid.

Standalone prep applies `source_axis_alignment` to mesh points and poses and its
rotation to vertex normals **before** packaging. The matrix records provenance;
the application must never apply it again. Intrinsics and depth retain camera-space
meaning. Prep stops if source alignment metadata is missing or invalid.

S3D accepts only file uploads and only v2. It rejects v1 with instructions to rerun
standalone preprocessing; there is no raw-input, inbox or legacy-alignment path.
Default prep output is chosen with `--out dataset/preprocessing`; Import copies
that file into application storage without mutating the original.

The loader must reject unknown versions, incomplete status, bad member names, missing
members, size or checksum mismatches, and a superpoint count different from mesh vertices.
Frame IDs are the original zero-based indices in the `.sens` stream. Depth values are
raw sensor integers; metric metres equal `depth / depth_shift`.
