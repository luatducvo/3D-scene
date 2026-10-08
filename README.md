# S3D

S3D imports prepared ScanNet scenes, segments and labels Objects, and answers
English questions about their geometry and appearance. A local web viewer shows
Instance masks, bboxes, relations, and real Keyframe evidence. Lookup uses CPU
MobileCLIP2; spatial questions use a validated Program and deterministic Solver.

## Prerequisites

- Docker Desktop with WSL2 GPU support and an NVIDIA driver
- For native development: Python 3.12 through `uv`, Node.js 24, and npm
- Licensed local ScanNet data for Package preparation

## Prepare a Package

The prep script is a standalone PEP 723 script; it does not import the service.
From the repository root:

```powershell
uv run tools/scannet_prep.py pack dataset/scans/scene0000_00 --out inbox
uv run tools/scannet_prep.py verify inbox/scene0000_00.s3dpkg
uv run tools/scannet_prep.py batch dataset/scans --list scenes.txt --out inbox --workers 2
uv run tools/test_scannet_prep.py
```

`pack` writes a `.partial` file, verifies it, then renames it to `.s3dpkg`.
The [Package contract](docs/s3dpkg-spec.md) is the only contract between prep
and import. Packages contain no ground-truth labels.

## Run with Compose

```powershell
New-Item -ItemType Directory -Force inbox | Out-Null
docker compose build
docker compose run --rm --no-deps api s3d models pull
docker compose up -d
```

Open [S3D](http://127.0.0.1:8000), import an inbox Package or upload a `.s3dpkg`,
then open its Scene when processing finishes. Try `stools`, `something to sit on`,
`How many stools?`, or `the stool closest to the desk`. Follow-up `it` uses the
last single Target or the Object clicked in the viewer. Clarify buttons resolve
ambiguous Programs. The API, web, `mask3d`, and `llm` share the local
Compose network; the host binds the web port to loopback. The default inbox is
`./inbox`; set `S3D_INBOX` to another host directory before `docker compose up`
if needed. The app stores Scene data and models in separate named volumes.
Model sources and hashes are pinned in `models.lock`; `models pull` skips files
whose SHA-256 already matches and rejects corrupt existing files. After pulling,
the model files do not need network access.

The first build compiles MinkowskiEngine and pointnet2 for the RTX 3050's SM 8.6.
It can take several minutes. S3 defaults to 3 cm voxels; the measured device-memory
increase was about 3.2 GiB on the two supplied scans. The service retries OOM in a
new process with 4 cm voxels. GPU stages unload the LLM first and use the same
admission lock. Insufficient VRAM, failed stages, and corrupt Packages appear in
the web UI. Optional captions for the N largest Objects are enabled with
`S3D_CAPTIONS_TOP_N=N` (default 0, maximum 20).

To preserve the compiled image after a successful build:

```powershell
New-Item -ItemType Directory -Force .backups | Out-Null
docker save s3d-mask3d:1 -o .backups/s3d-mask3d.tar
# Restore with: docker load -i .backups/s3d-mask3d.tar
```

## Native development

```powershell
uv sync --project backend --extra dev --frozen
npm ci --prefix frontend
npm run build --prefix frontend
$env:S3D_DATA_DIR = Join-Path (Resolve-Path .).Path '.local-data'
$env:S3D_INBOX_DIR = Join-Path (Resolve-Path .).Path 'inbox'
$env:S3D_MODEL_DIR = Join-Path (Resolve-Path .).Path 'models'
$env:S3D_LLM_BASE_URL = 'http://127.0.0.1:8080'
$env:S3D_MASK3D_URL = 'http://127.0.0.1:9000'
uv run --project backend --frozen s3d models pull
docker compose -f compose.yaml -f compose.dev.yaml up -d llm mask3d
uv run --project backend --frozen s3d serve
```

`s3d serve` binds `127.0.0.1:8000`. For hot reload, run `npm run dev` in
`frontend/` with `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000` and set
`S3D_DEV=1` on the API to allow the two localhost dev origins. The dev Compose
file binds `.local-data` and `models` to the GPU services; Windows paths sent to
Mask3D are translated to that shared `/data` directory. Production uses relative
API URLs and does not enable CORS.

## LLM configuration

The default is the pinned local llama.cpp router. To select an OpenAI-compatible
endpoint, set these environment variables before recreating `api`:

```powershell
$env:S3D_LLM_BASE_URL = 'https://your-endpoint.example/v1'
$env:S3D_LLM_MANAGED = '0'
$env:S3D_LLM_MODEL = 'your-model-name'
$env:S3D_LLM_API_KEY = 'your-key'
docker compose up -d api
```

Cloud mode calls chat completions directly and does not call local model-management
endpoints or take the GPU lock. It sends the question, label/context text, and real
Keyframes for vision requests. Packages and full meshes stay local. Debug Program
input is enabled with `S3D_DEBUG_PROGRAM=1`; it is off by default. Captions are lazy
and cached in SQLite.

## Verification

```powershell
cd backend
uv run --frozen pytest
uv run --frozen ruff check . ../tools ../mask3d
uv run --frozen python -m s3d_app.export_openapi --check
cd ../frontend
npm run types:api
npm run typecheck
npm test
npm run build
cd ..
uv run tools/test_scannet_prep.py
# Local models and a processed Scene are required for this optional evaluation:
# Enable S3D_DEBUG_PROGRAM=1 on api, then:
uv run --project backend python tools/query_eval.py
```

The committed OpenAPI schema and generated TypeScript types must be updated
together when the API changes. Export with `uv run --project backend python -m
s3d_app.export_openapi`, then run `npm run types:api --prefix frontend`. The web
build checks hashes of the OpenAPI contract and API source; stale types fail the
build. CI runs CPU tests, standalone prep tests, lint, contract checks, and web
tests/build.

Both supplied scans completed S1–S6 with real Mask3D, YOLOE, and MobileCLIP2 on
2026-10-08. Cold-stage timing and sampled GPU usage are recorded in
`docs/spikes/stage-runs.json`. GPU feasibility is documented in
[ADR 0007](docs/adr/0007-llm-spike-results.md) and
[ADR 0008](docs/adr/0008-mask3d-spike-results.md). The local question comparison is
in `docs/spikes/query-eval.json`; it compares the model with hand-authored Programs
on measured Objects and is not a ground-truth ScanRefer benchmark. Vision Tiebreak
and caption cache timings are in `docs/spikes/vision-validation.json`.

## Back up and restore Scene data

Stop the API before backing up SQLite and the Package/artifact files together.
These PowerShell commands were tested with the default Compose project name
`3d-scene`. If your checkout has a different name, substitute the data volume
shown by `docker volume ls`.

```powershell
$backupDir = Join-Path (Resolve-Path .).Path '.backups'
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
docker compose stop api
docker run --rm --mount 'type=volume,src=3d-scene_s3d-data,dst=/data,readonly' --mount "type=bind,src=$backupDir,dst=/backup" alpine:3.22 tar -C /data -czf /backup/s3d-backup.tar.gz .
docker compose up -d api
```

Restore into an empty data volume while the API is stopped. Keep a copy of the
archive outside the volume. The following replaces the default data volume:

```powershell
$backupDir = Join-Path (Resolve-Path .).Path '.backups'
docker compose down
docker volume rm 3d-scene_s3d-data
docker volume create 3d-scene_s3d-data
docker run --rm --mount 'type=volume,src=3d-scene_s3d-data,dst=/data' --mount "type=bind,src=$backupDir,dst=/backup,readonly" alpine:3.22 tar -C /data -xzf /backup/s3d-backup.tar.gz
docker compose up -d
```

A backup was restored to a disposable volume and checked for both Scene records
and source Packages on 2026-10-08.

## Licenses and data

- Ultralytics YOLOE weights and code: AGPL-3.0; review its terms before use.
- Apple MobileCLIP2: Apple's model and code license applies.
- Mask3D: MIT code license; checkpoint terms should be verified before use.
- Qwen3-VL: Apache-2.0. llama.cpp: MIT.
- ScanNet: research/non-commercial terms of use. Do not publish raw scans or
  derived Packages without permission.
