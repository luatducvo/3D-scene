# s3dpkg/1

A Package is an uncompressed POSIX tar file named `<scan>.s3dpkg`, where `<scan>` matches
`scene[0-9]{4}_[0-9]{2}`. The archive contains no ground truth labels. Member names are
relative, use `/`, and cannot contain `..` or symbolic links.

| Member | Content |
| --- | --- |
| `manifest.json` | UTF-8 JSON metadata described below |
| `mesh/vh_clean_2.ply` | ScanNet mesh, unchanged vertex order |
| `mesh/superpoints.npy` | 1-D `int32` NumPy array, one segment id per mesh vertex |
| `calib/intrinsics.json` | Color and depth 3×3 intrinsics, image dimensions, depth shift |
| `frames/index.parquet` | Rows with `frame_id` (int), `blur` (float), `valid` (bool) |
| `frames/color/<id>.jpg` | JPEG color image, long side at most 960 by default |
| `frames/depth/<id>.png` | 16-bit unsigned PNG depth image |
| `frames/pose/<id>.txt` | 4×4 camera-to-world float matrix in text form |

`manifest.json` has `format_version: "s3dpkg/1"`, `status: "complete"`, `scan_id`,
`script_version`, `parameters`, `sens_sha256`, `aligned` (boolean), `axis_alignment`
(4×4 row-major float matrix), and `files` (a mapping from every other member name to
its lowercase SHA-256 hex digest). Every listed file must be present exactly once and no
unlisted file is permitted. The manifest itself is excluded from `files` to avoid a
self-referential hash. `sens_sha256` identifies the source `.sens`; the `.sens` is not in
the Package. `aligned: false` requires identity `axis_alignment`.

The loader must reject unknown versions, incomplete status, bad member names, missing
members, size or checksum mismatches, and a superpoint count different from mesh vertices.
Frame IDs are the original zero-based indices in the `.sens` stream. Depth values are
raw sensor integers; metric metres equal `depth / depth_shift`.
