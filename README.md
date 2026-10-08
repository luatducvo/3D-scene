# S3D — Explore and Query 3D Scenes

S3D runs locally on your machine, accepts preprocessed ScanNet data, and creates 3D
Scenes to explore, select objects, and ask questions about their locations, counts, or
attributes. Results are highlighted on the 3D model and accompanied by real keyframe
photographs from the scan.

**The web interface and questions are in English.**

## Architecture

```text
External preprocessing
  dataset/scans → prep script → dataset/preprocessing/*.s3dpkg
                                         │
                                    user upload
                                         ↓
S3D system
  Web → API → validate Package → analyze Scene → persist data
   ↑                                                │
   └────────── 3D model, objects, and evidence ─────┘

  Question → object retrieval / spatial solver → answer + highlights
```

| Component | Role |
| --- | --- |
| Preprocessing script | Runs on CPU, aligns mesh and camera poses, packages `.s3dpkg`. Runs independently of S3D. |
| Web UI | Displays the 3D Scene, object list, and chat interface; served directly by the API. |
| API & Pipeline | Validates files, manages job progress; extracts geometry, predicts labels with YOLOE, generates embeddings with MobileCLIP2, and builds spatial scene graphs. |
| Mask3D | Dedicated GPU service segmenting the 3D mesh into distinct object instances. |
| LLM & Solver | LLM interprets questions; deterministic Solver computes spatial queries and counts. Vision model uses real keyframes to tiebreak candidates or describe objects. |

Docker Compose runs three services: `api`, `mask3d`, and `llm`. GPU workloads are
orchestrated to share VRAM safely. By default, data and models stay local; the
web interface binds only to localhost.

## Prerequisites

- Docker Desktop with WSL2 and NVIDIA GPU support; NVIDIA driver installed.
- `uv` to run the preprocessing script if starting from raw ScanNet scans.
- Licensed ScanNet data, or prepared `.s3dpkg` v2 package files.
- Internet access for the initial build and model downloads; operates offline with downloaded models afterward.

The verified baseline hardware is an NVIDIA RTX 3050 6 GiB Laptop GPU. The Mask3D
image is currently built for SM 8.6 GPU architecture; for other GPUs, see
[GPU notes](docs/adr/0008-mask3d-spike-results.md) and
[development guide](docs/development.md).

The commands below are run from the repository root using PowerShell.

## 1. Prepare Data

If you already have `.s3dpkg` v2 files, proceed to step 2.

Place each raw scan in `dataset/scans/<scan_id>/`. For example:

```text
dataset/scans/scene0000_00/
  scene0000_00.sens
  scene0000_00_vh_clean_2.ply
  scene0000_00_vh_clean_2.0.010000.segs.json
  scene0000_00.txt                         # contains axisAlignment
```

Preprocess and verify the output:

```powershell
uv run tools/scannet_prep.py pack dataset/scans/scene0000_00 --out dataset/preprocessing
uv run tools/scannet_prep.py verify dataset/preprocessing/scene0000_00.s3dpkg
```

The file to upload is **`dataset/preprocessing/scene0000_00.s3dpkg`**. Replace the scan ID
in the command to process other scans. For processing multiple scans at once, see the `batch` command in the
[script guide](docs/operations.md#chuẩn-hoá-nhiều-scan).

The script applies all alignment transformations and leaves the raw data intact. A missing or invalid
`axisAlignment` halts with an error. The system only accepts `s3dpkg/2` Packages;
v1 files must be regenerated from raw scans using this script.

## 2. Start the System

Initial startup:

```powershell
docker compose build
docker compose run --rm --no-deps api s3d models pull
docker compose up -d
```

The first build may take some time as GPU libraries are compiled.
Once completed, open [S3D in your browser](http://127.0.0.1:8000).

For subsequent runs, simply execute `docker compose up -d`. Stop the system with
`docker compose down`; all data persists in the Docker volumes.

## 3. Upload and Open a Scene

1. Under **Import a Package**, select or drag and drop a file from `dataset/preprocessing/`.
2. Monitor pipeline progress. Once the Scene reaches **ready** status, click **Open mesh**.
3. Orbit, pan, and zoom the 3D model; select objects directly or from the
   **Objects** list to inspect labels, colors, and spatial relationships.

Uploading creates an application-owned copy in storage, leaving the preprocessing file untouched.
The application consumes pre-aligned data and does not re-apply any alignment transformations.

If a scan ID already exists with a different Package, the UI prompts to **Replace**. Confirming
replaces the old Scene and restarts processing. **Reprocess** restarts the pipeline from a selected stage;
**Delete** removes the Scene, with an option to also purge the stored Package copy.

## 4. Ask Questions

In **Ask about this Scene**, enter questions in English, for example:

| Intent | Example |
| --- | --- |
| Locate objects | `chairs` or `something to sit on` |
| Count | `How many stools?` |
| Spatial relations | `the stool closest to the desk` |
| Follow-up on selected object | `What color is it?` |

Results are highlighted in the viewer. If multiple candidates exist, select an object using the
clarification buttons; photographic keyframe evidence appears when available. The pronoun `it` refers
to the currently selected object or the preceding single result. Egocentric directions (left/right/front/back)
default to the current viewer camera orientation, so rotating the camera may alter the answer.

## Where Is Data Stored?

| Data | Default Location |
| --- | --- |
| Raw scans | `dataset/scans/` — external to the system |
| Prepared files for upload | `dataset/preprocessing/` — external to the system |
| Imported Packages, Scenes, query history, and pipeline artifacts | Docker volume `s3d-data`, at `/data` inside containers |
| Downloaded model weights | Docker volume `s3d-models`, at `/models` inside containers |

Actual volume names are prefixed by the Compose project name. Data and models are not committed
to the repository. Review [backup and restore](docs/operations.md#sao-lưu-và-khôi-phục)
before transferring machines or deleting volumes.

## Troubleshooting

| Issue | Resolution |
| --- | --- |
| API unavailable / web UI does not open | Run `docker compose ps` and check logs with `docker compose logs --tail 100 api mask3d llm`. |
| Legacy v1 file or alignment error | Re-run the preprocessing script on raw scans containing a valid `axisAlignment` matrix. |
| Scene fails due to out-of-memory (VRAM) | Close other GPU-intensive applications, then choose **Reprocess** from the failed stage. |
| Legacy Scene cannot be reprocessed from S1 | Prepare an `s3dpkg/2` package, upload it, and choose **Replace**. |

## Further Documentation

- [Operations](docs/operations.md): batch preprocessing, backups, LLM configuration, and licenses.
- [Development](docs/development.md): native setup, testing, and API schema updates.
- [Architecture & Terminology](CONTEXT.md), [Package specification](docs/s3dpkg-spec.md).
- [Project status & verification](docs/project-status.md).
- [Coding agent instructions](AGENTS.md) — read before modifying the repository.
