# Input flow revision

## Confirmed by the user

- Raw ScanNet scans are under `dataset/scans/`.
- Preprocessing is a standalone utility outside the running S3D system.
- Prepared files are saved under `dataset/preprocessing/`.
- The user uploads a prepared file into S3D to create and use a Scene.
- Upload is the sole input method; inbox is removed from UI, API and Compose.
- Preprocessing applies coordinate alignment to mesh and camera poses before
  producing the Package; S1 does not transform coordinates.
- New Packages use `format_version: s3dpkg/2` and retain the `.s3dpkg` extension.
- Upload rejects `s3dpkg/1` and instructs the user to rerun standalone preprocessing.
- Missing or invalid source `axisAlignment` stops preprocessing with a clear error;
  no uploadable Package is produced for that run.

```text
dataset/scans/<scan>
    → standalone Preprocessing
    → dataset/preprocessing/<scan>.s3dpkg
    → manual upload
    → Import / Scene processing
```

## Facts recorded before implementation (`2ed393e`)

- The script already accepts a separate output directory through `--out`.
- Raw mesh and camera poses currently remain unchanged in the Package.
- S1 applies `axis_alignment` inside the application.
- `aligned` currently records the availability of source alignment metadata.
- Inbox is an existing second input method in UI, API and Compose.
- `dataset/preprocessing/` exists and is empty; its output is not yet ignored by Git.
- Upload copies the Package into application storage without changing the user's file.

## Decision tree

1. Input methods — confirmed: upload only.
   - Remove inbox UI/API/mount and update import contracts/docs.
2. Alignment ownership — confirmed: outside.
   - Prep transforms mesh and poses; revise the coordinate-frame contract so S1
     cannot apply alignment twice.
   - Old-Package compatibility — confirmed: reject v1; rerun preprocessing to
     produce v2. No legacy alignment path or v1 converter in the application.
   - Missing/invalid source alignment — confirmed: stop preprocessing and report
     an error. Identity is valid only when explicitly supplied as valid source metadata.
3. Shared understanding — confirmed: the user answered “Đúng, triển khai thiết kế này”.

Implementation follows ticket 25 and ADR 0009.
