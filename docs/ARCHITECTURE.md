# 3D Scene Understanding System — Architecture

> Turns RGB photos or a short video of a room, captured with a phone, into a metric-scale 3D scene with open-vocabulary objects and a scene graph. Users can then ask about it in natural language (Vietnamese or English).
>
> - **Baseline reconstruction:** Depth Anything 3 (`DA3NESTED-GIANT-LARGE-1.1`), shown as a dense colored point cloud.
> - **Design:** SOLID. Every capability is a replaceable component chosen in configuration.
> - **Deployment:** local, single user. Docker Compose for everything; `uv` manages Python, `npm` manages the Next.js frontend.
> - **Storage:** system state (scene files and PostgreSQL) lives in named Docker volumes, so `docker compose down -v` returns the system to a fresh, empty state. Only the model weight cache is bind-mounted to the host (`./models`) to avoid re-downloading tens of gigabytes. Users keep their original photos on their own computer. No Redis, no object store.
> - **Compute:** each pipeline stage runs either in-process (CPU) or on a GPU target: local GPU, Modal, RunPod, Vast.ai or any Docker host. No provider is the default; the operator names the Targets before starting the system. Every GPU target runs the same Docker image behind the same HTTP contract, so switching provider changes configuration and a deployment file, never application code.
> - **Language:** all code, identifiers, comments, logs, API messages and documentation are in English. Only the user-facing UI strings are localized (`en`, `vi`).
> - **Scope:** learning project. No fallbacks, no benchmarks.

---

## Table of contents

1. [Overview](#1-overview)
2. [Design principles and conventions](#2-design-principles-and-conventions)
3. [Repository layout](#3-repository-layout)
4. [Domain model and data contracts](#4-domain-model-and-data-contracts)
5. [Ports (interfaces)](#5-ports-interfaces)
6. [Compute layer: where stages run](#6-compute-layer-where-stages-run)
7. [Pipeline orchestration](#7-pipeline-orchestration)
8. [Pipeline stages](#8-pipeline-stages)
9. [Backend API](#9-backend-api)
10. [Frontend](#10-frontend)
11. [Docker Compose and tooling](#11-docker-compose-and-tooling)
12. [Extending and replacing components](#12-extending-and-replacing-components)
13. [Running the system](#13-running-the-system)

---

## 1. Overview

### 1.1 Capabilities

1. The user captures many photos (or a short video) around one room. Input is RGB only: no depth, no camera poses.
2. The user uploads them through the web app.
3. The system automatically:
   - checks image quality and selects keyframes;
   - reconstructs the scene: camera poses, depth, metric scale, gravity axis, mesh;
   - detects objects with an open vocabulary;
   - builds a scene graph.
4. The user explores the 3D scene, searches objects with free text, and asks about location, spatial relations, counts, attributes and distances.

### 1.2 System diagram

```mermaid
flowchart LR
  subgraph FE[frontend · own compose project]
    WEB[Next.js app<br/>upload · viewer · chat]
  end

  subgraph BE[backend · own compose project]
    API[scene-api<br/>FastAPI]
    WK[scene-worker<br/>pipeline runner]
    PG[(postgres<br/>+ pgvector<br/>jobs · events · graph)]
    FS[(./data<br/>local storage)]
    CMP[scene-compute<br/>local GPU, optional]
  end

  subgraph CLOUD[Remote GPU, optional · same scene-compute image]
    MOD[Modal]
    RP[RunPod<br/>Pod or Serverless]
    VM[Any Docker host]
  end

  WEB -->|REST + SSE /api/v1| API
  API --> PG
  API --> FS
  WK --> PG
  WK --> FS
  WK -->|HTTP compute contract| CMP
  WK -->|HTTP compute contract| MOD & RP & VM
  API -->|query-time embedding| CMP & MOD & RP & VM
  CMP --- FS
```

The only boundary between frontend and backend is `WEB → API` over HTTP. The frontend never reads the filesystem or the database; every file URL it uses is returned by the API.

### 1.3 Pipeline stages

| # | Stage | Port | Default algorithm | Default target |
|---|---|---|---|---|
| 1 | Ingest + quality check | `StageAlgorithm` | `ingest.opencv` | GPU target |
| 2 | 3D reconstruction | `StageAlgorithm` | `recon.da3` | GPU target |
| 3 | Gravity alignment | `StageAlgorithm` | `align.geocalib_ransac` | GPU target |
| 4 | Mesh | `StageAlgorithm` | `mesh.tsdf` | GPU target |
| 5 | 2D segmentation | `StageAlgorithm` | `segment.sam3` | GPU target |
| 6 | 2D → 3D lifting | `StageAlgorithm` | `lift.maskclustering` | GPU target |
| 7 | Object embeddings | `StageAlgorithm` | `embed.metaclip2` | GPU target |
| 8 | Attributes | `StageAlgorithm` | `attributes.none` ([ADR-0004](ADR-0004-skip-vlm-attributes.md)); `attributes.vlm_api` available | GPU target |
| 9 | Scene graph | `StageAlgorithm` | `graph.geometric` | GPU target |

Every Stage runs on one Target, the GPU image in the real pipeline ([ADR-0005](ADR-0005-whole-pipeline-on-gpu-host.md)). Uploaded files are stored on that Target too, never in local Scene storage. The fake pipeline runs all of them on `cpu`.

At query time, the API uses:
- `TextEmbedder`: the `embed.metaclip2` algorithm, invoked on its configured target.
- `LLMClient`: any OpenAI-compatible endpoint, either a cloud API or a local server (e.g. vLLM, Ollama).
- `QAAgent`: lives in `scene-api`.

### 1.4 Processing sequence

```mermaid
sequenceDiagram
  participant W as Web
  participant A as scene-api
  participant D as ./data
  participant P as Postgres
  participant K as scene-worker
  participant C as Compute target

  W->>A: POST /scenes
  W->>A: POST /scenes/{id}/uploads (multipart)
  A->>D: write raw/
  W->>A: POST /scenes/{id}/process
  A->>P: INSERT job + NOTIFY jobs_queued
  K->>P: claim job (SKIP LOCKED)
  loop Each stage
    K->>C: run(algorithm, scene_id, params)
    C->>D: read inputs / write outputs (shared or transferred)
    C-->>K: manifest
    K->>P: save stage_run + NOTIFY scene_events
    P-->>A: event
    A-->>W: SSE progress
  end
  K->>P: publish graph and embeddings atomically; mark ready
  W->>A: POST /scenes/{id}/queries
  A-->>W: SSE answer + object_ids + evidence
```

---

## 2. Design principles and conventions

### 2.1 SOLID

| Principle | Application |
|---|---|
| **S** — Single Responsibility | An algorithm class only transforms workspace inputs into outputs. It does not know where it runs, how files are transferred, or how progress is reported. Each of those concerns has its own component. |
| **O** — Open/Closed | A new method is a new class registered under a new name, selected in `pipeline.yaml`. A new GPU provider is a new deployment of the same image plus a URL in `compute.yaml`. Nothing else changes. Spatial relations (`RelationRule`) and QA tools (`AgentTool`) extend the same way. |
| **L** — Liskov Substitution | All algorithms for the same stage read the same inputs, write the same workspace layout and return the same manifest type. All compute backends return the same result for the same algorithm. Output geometry is always in meters, z-up, floor at z = 0 (after the align stage). |
| **I** — Interface Segregation | Small ports: `TextEmbedder` is separate from object embedding, `FileStore` is separate from `ComputeBackend`, `EventPublisher` is separate from `SceneRepository`. |
| **D** — Dependency Inversion | The runner, the API routes and the QA agent depend only on ports in `scene-core`. Concrete classes are wired in a composition root (`container.py`) from configuration. |

### 2.2 Layering

```
scene-core     domain models, contracts, ports, pure geometry   (no heavy deps)
   ▲
scene-stages   algorithm implementations                        (heavy deps as optional extras)
   ▲
scene-api · scene-worker · scene-compute                        (runtimes and adapters)
```

`scene-core` never imports `torch`, `modal`, `fastapi` or a database driver.

### 2.3 Naming conventions

All names are descriptive English. No product codename appears in code; the deployment name is set once through `COMPOSE_PROJECT_NAME`.

| Item | Convention | Example |
|---|---|---|
| Directories, repositories, Docker services, Python distributions, npm package | kebab-case | `scene-worker`, `scene-stages` |
| Python modules and packages | snake_case | `scene_core.ports` |
| Python classes | PascalCase | `DepthAnything3Reconstruction` |
| Python functions, variables | snake_case | `load_scene_graph` |
| Algorithm registry keys | `<stage>.<method>` lowercase | `recon.da3` |
| TypeScript variables, functions | camelCase | `subscribeProgress` |
| React components, TS types | PascalCase | `SceneCanvas`, `SceneDetail` |
| Environment variables | UPPER_SNAKE_CASE | `DATA_DIR` |
| REST paths | lowercase, plural nouns, kebab-case | `/api/v1/scenes/{scene_id}/objects` |
| JSON fields, DB tables and columns | snake_case | `scene_id`, `stage_runs` |
| Config files | kebab-case or lowercase `.yaml` | `pipeline.yaml`, `compute.yaml` |
| Compose file | `compose.yaml` (Compose Specification default name) | |
| Commits | Conventional Commits | `feat(recon): add depth-anything-3 algorithm` |
| Versioning | SemVer | `1.2.0` |
| Dates and times | ISO 8601, UTC | `2026-10-12T16:58:00Z` |
| Units | SI (meters, seconds, radians) | `distance_m` |

---

## 3. Repository layout

Two independent projects. They can live in one parent folder or in two repositories; neither imports or builds from the other.

### 3.1 Backend

```
backend/
├── compose.yaml
├── .env.example
├── tasks.py
├── README.md
├── pyproject.toml                 # uv workspace root
├── uv.lock
├── config/
│   ├── pipeline.yaml              # which algorithm and which target per stage
│   ├── compute.yaml               # compute targets (cpu, local GPU, Modal, HTTP hosts)
│   └── vocabularies/
│       └── indoor-en.txt          # default open-vocabulary prompts for segmentation
├── openapi/
│   └── openapi.json               # API contract, generated, committed
├── models/                        # model weight cache, git-ignored, bind-mounted (see 4.3)
├── docker/
│   ├── python.Dockerfile          # scene-api and scene-worker
│   └── compute.Dockerfile         # scene-compute: the single portable GPU image
├── deploy/                        # provider-specific deployment only, no application code
│   ├── modal/app.py
│   ├── runpod/README.md           # Pod and Serverless settings
│   └── generic/README.md          # any Docker host with a GPU
├── migrations/
│   └── 001_init.sql
├── packages/
│   ├── scene-core/
│   │   ├── pyproject.toml
│   │   └── src/scene_core/
│   │       ├── domain/            # Scene, Instance3D, SceneObject, SceneGraph...
│   │       ├── contracts/         # stage manifests, workspace layout
│   │       ├── ports/             # abstract interfaces
│   │       ├── geometry/          # OBB fitting, distances (numpy only)
│   │       ├── executor.py        # shared by worker and compute server
│   │       └── registry.py
│   └── scene-stages/
│       ├── pyproject.toml         # one optional extra per heavy algorithm
│       └── src/scene_stages/
│           ├── ingest/opencv.py
│           ├── recon/da3.py
│           ├── align/geocalib_ransac.py
│           ├── mesh/tsdf.py
│           ├── segment/sam3.py
│           ├── lift/maskclustering.py
│           ├── embed/metaclip2.py
│           ├── attributes/vlm_api.py
│           └── graph/
│               ├── geometric.py
│               └── relations/     # one RelationRule per file
└── services/
    ├── scene-api/
    │   ├── pyproject.toml
    │   └── src/scene_api/
    │       ├── main.py
    │       ├── container.py       # composition root
    │       ├── routes/
    │       ├── qa/                # QAAgent + AgentTool implementations
    │       └── adapters/          # postgres, local files, LLM client
    ├── scene-worker/
    │   ├── pyproject.toml
    │   └── src/scene_worker/
    │       ├── main.py            # job loop
    │       ├── container.py
    │       ├── runner.py
    │       ├── queue.py           # Postgres job queue
    │       └── compute/           # InProcessBackend, HttpBackend, compute.yaml loader
    └── scene-compute/
        ├── pyproject.toml
        └── src/scene_compute/
            ├── server.py          # implements the compute contract (section 6.2)
            ├── runs.py            # run registry
            └── files.py           # chunked upload, ranged download, checksums
```

### 3.2 Frontend

```
frontend/
├── compose.yaml
├── Dockerfile
├── .env.example
├── README.md
├── package.json
├── package-lock.json
├── next.config.ts
├── openapi/openapi.json           # copy of the backend contract (npm run api:sync)
├── messages/
│   ├── en.json
│   └── vi.json
├── public/
└── src/                           # see 10.2
```

### 3.3 uv workspace

`backend/pyproject.toml`:

```toml
[project]
name = "scene-backend"
version = "0.1.0"
requires-python = ">=3.12"

[tool.uv]
package = false

[tool.uv.workspace]
members = ["packages/*", "services/*"]
```

`packages/scene-stages/pyproject.toml`. Heavy dependencies are optional extras, one per algorithm, so each runtime installs only what it runs:

```toml
[project]
name = "scene-stages"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["scene-core", "numpy>=1.26", "pillow>=11", "opencv-python-headless>=4.10", "trimesh>=4"]

[project.optional-dependencies]
recon-da3         = ["torch", "torchvision", "depth-anything-3 @ git+https://github.com/ByteDance-Seed/Depth-Anything-3.git"]
align-geocalib    = ["torch", "geocalib @ git+https://github.com/cvg/GeoCalib.git", "open3d>=0.18"]
mesh-tsdf         = ["open3d>=0.18"]
segment-sam3      = ["torch", "ultralytics", "clip @ git+https://github.com/ultralytics/CLIP.git"]
lift-maskclustering = ["torch", "open3d>=0.18", "scikit-learn"]
embed-metaclip2   = ["torch", "transformers>=4.56"]
attributes-vlm    = ["openai>=1.50"]

[tool.uv.sources]
scene-core = { workspace = true }

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

All GPU extras resolve in one environment. Depth Anything 3 requires NumPy < 2 and xformers; SAM 3 through Ultralytics, GeoCalib and MetaCLIP 2 accept that, so scene-compute has a single `gpu` extra and a single GPU image (6.8, [ADR-0002](ADR-0002-single-gpu-image-ultralytics-sam3.md)). The real extras live in `backend/packages/scene-stages/pyproject.toml`; the block above shows the shape, not the exact pins.

Common commands:

```bash
uv sync                                          # whole workspace, light deps
uv sync --package scene-compute --extra gpu      # compute runtime of the GPU image
uv add --package scene-worker httpx              # add a dependency to one service
uv run --package scene-api pytest
```

---

## 4. Domain model and data contracts

### 4.1 Domain (`scene_core.domain`)

```python
from enum import StrEnum
from pydantic import BaseModel

class SceneStatus(StrEnum):
    CREATED = "created"
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"

class OrientedBox(BaseModel):
    center: tuple[float, float, float]      # meters, z-up
    size: tuple[float, float, float]        # length, width, height
    yaw: float                              # radians around z

class BestView(BaseModel):
    frame_id: str
    bbox: tuple[int, int, int, int]
    score: float

class Instance3D(BaseModel):
    id: str
    label: str                              # English vocabulary label
    score: float
    num_views: int
    points_file: str                        # path relative to the scene workspace
    best_views: list[BestView]

class SceneObject(BaseModel):
    id: str
    label: str
    label_vi: str | None = None
    box: OrientedBox
    attributes: dict[str, list[str]] = {}   # color, material, state...
    best_views: list[BestView]

class Relation(BaseModel):
    subject_id: str
    predicate: str                          # on, under, above, inside, next_to, near, against_wall
    object_id: str | None = None
    value: float | None = None

class SceneGraph(BaseModel):
    scene_id: str
    floor_z: float
    ceiling_height: float | None
    objects: list[SceneObject]
    relations: list[Relation]
```

### 4.2 Stage manifests (`scene_core.contracts`)

Every stage returns a small JSON manifest. Bulk data lives in the workspace.

```python
class IngestManifest(BaseModel):
    num_inputs: int
    num_keyframes: int
    rejected: dict[str, list[str]]          # {"blur": [...], "duplicate": [...], "exposure": [...]}

class ReconManifest(BaseModel):
    num_frames: int
    frame_ids: list[str]
    metric_scale: float
    image_size: tuple[int, int]             # (width, height) used by the model

class AlignManifest(BaseModel):
    world_to_aligned: list[list[float]]     # 4x4: z-up, floor at z = 0
    floor_z: float
    ceiling_height: float | None

class MeshManifest(BaseModel):
    mesh_file: str                          # mesh/mesh.glb
    points_file: str                        # mesh/points.ply, dense colored point cloud
    num_faces: int
    num_points: int

class SegmentManifest(BaseModel):
    num_masks: int
    vocabulary_size: int

class LiftManifest(BaseModel):
    num_instances: int
    instances_file: str                     # instances/instances.json

class EmbedManifest(BaseModel):
    model_id: str
    dim: int
    embeddings_file: str                    # embeddings/objects.npz

class AttributesManifest(BaseModel):
    num_objects: int

class GraphManifest(BaseModel):
    num_objects: int
    num_relations: int
```

### 4.3 Storage layout

Two kinds of storage, chosen by whether the data is **system state** or a **rebuildable cache**:

| Data | Storage | Survives `docker compose down -v`? |
|---|---|---|
| Scene files (uploads, stage outputs) and compute run records | Named volume `scene-data` → `/data` (`DATA_DIR`) | No |
| PostgreSQL database | Named volume `postgres-data` → `/var/lib/postgresql/data` | No |
| Model weights | Bind mount `./models` (`HOST_MODELS_DIR`) → `/models` (`MODELS_DIR`) | Yes |
| Code, Python environment, `node_modules`, Next.js build, CUDA libraries | Docker images | Rebuilt by `docker compose build` |
| Temporary files, logs | Container layer and stdout | No |

Consequences:

- `docker compose down` stops the system and keeps everything.
- `docker compose down -v` (or `uv run tasks.py reset`) returns the system to a fresh, empty state. Original photos are the user's own copies on their computer; uploads inside the system are working copies.
- Model weights are a cache, not state: keeping them on the host avoids downloading tens of gigabytes after every reset. Deleting `./models` is always safe.

Inside the `scene-data` volume:

```
/data
├── scenes/{scene_id}/           # one folder per scene (below)
└── runs/                        # run records written by the local scene-compute
```

Model cache on the host:

```
models/                          # HOST_MODELS_DIR → /models
├── hf/                          # HF_HOME: Hugging Face weights (Depth Anything 3, SAM 3, Meta CLIP 2...)
└── torch/                       # TORCH_HOME: torch.hub weights (e.g. GeoCalib)
```

Scene folder:

```
/data
└── scenes/{scene_id}/
    ├── raw/                     # uploaded originals
    ├── keyframes/               # 0000.jpg ... (EXIF orientation applied, metadata stripped)
    ├── recon/
    │   ├── rgb/0000.png         # images at the resolution the model used
    │   ├── frames/0000.npz      # depth, conf, pose (camera-to-world 4x4, meters), K
    │   └── manifest.json
    ├── align/
    │   ├── frames/0000.npz      # gravity-aligned poses
    │   └── manifest.json
    ├── mesh/
    │   ├── mesh.glb
    │   ├── points.ply
    │   └── manifest.json
    ├── segment/
    │   ├── masks/0000.npz       # masks (N,H,W) bool, labels, scores
    │   └── manifest.json
    ├── instances/
    │   ├── instances.json
    │   ├── points/{id}.npy
    │   ├── crops/{id}_{k}.jpg
    │   └── manifest.json
    ├── embeddings/
    │   ├── objects.npz          # ids, vectors
    │   └── manifest.json
    ├── attributes/
    │   └── attributes.json
    └── graph/
        └── scene_graph.json
```

```python
class SceneWorkspace:
    """Resolves paths inside one scene folder. Knows nothing about where the folder lives."""

    def __init__(self, data_dir: Path, scene_id: str) -> None:
        self.root = Path(data_dir) / "scenes" / scene_id

    def dir(self, *parts: str) -> Path:
        path = self.root.joinpath(*parts)
        path.mkdir(parents=True, exist_ok=True)
        return path
```

### 4.4 Where data lives

| Data | Written by | Location |
|---|---|---|
| Uploaded photos and videos (working copies) | `scene-api` (streamed to disk) | `scene-data` volume: `/data/scenes/{scene_id}/raw/` |
| Stage outputs (keyframes, depth and poses, mesh, masks, instances, embeddings, attributes, scene graph) | the stage's algorithm | `scene-data` volume: `/data/scenes/{scene_id}/<stage>/` with a `manifest.json` |
| Which stages are complete, with algorithm and config hash (used to skip or rerun) | `scene-worker` | PostgreSQL table `stage_runs` (`postgres-data` volume) |
| Scenes, jobs, objects, relations, embeddings, chat history | `scene-api`, `scene-worker` | PostgreSQL (`postgres-data` volume) |
| Run records of the local GPU server | `scene-compute` | `scene-data` volume: `/data/runs/` |
| Model weights (local GPU) | `scene-compute` on first use or `uv run tasks.py download-models` | Host folder `./models` |
| Copies on remote GPU hosts | `HttpBackend` file sync | Provider disk or volume. Holds every intermediate output during a Job; only `RESULTS` are pulled back into `scene-data` after the last Stage ([ADR-0005](ADR-0005-whole-pipeline-on-gpu-host.md)) |
| Model weights on remote hosts | the remote `scene-compute` | Provider volume mounted at `MODELS_DIR` (Modal Volume `scene-models`, RunPod `/workspace/models` or a network volume) |

The frontend stores no data.

---

## 5. Ports (interfaces)

All ports live in `scene_core.ports`.

```python
from abc import ABC, abstractmethod
from typing import Any, ClassVar
import numpy as np
from pydantic import BaseModel

# ---------- Algorithms ----------
class StageAlgorithm(ABC):
    """A pure transformation of a scene workspace. Runtime-agnostic."""
    name: ClassVar[str]                          # registry key, e.g. "recon.da3"
    stage: ClassVar[str]                         # e.g. "recon"
    manifest_type: ClassVar[type[BaseModel]]
    reads: ClassVar[list[str]]                   # workspace subdirs consumed
    writes: ClassVar[list[str]]                  # workspace subdirs produced

    def download_weights(self) -> None:
        """Fetch model weights into MODELS_DIR without loading them on a GPU. Used by `uv run tasks.py download-models`."""

    def setup(self) -> None:
        """Load models. Called once per process before the first run."""

    @abstractmethod
    def run(self, workspace: SceneWorkspace, params: dict[str, Any]) -> BaseModel: ...

    def progress(self, done: int, total: int, unit: str) -> None:
        """Report progress inside run(), e.g. progress(48, 155, "object"). A no-op unless the
        Executor attached a sink for this run; the Executor never changes run()'s signature."""

class TextEmbedder(ABC):
    @abstractmethod
    def embed_text(self, texts: list[str]) -> np.ndarray: ...

class RelationRule(ABC):
    predicate: ClassVar[str]
    @abstractmethod
    def evaluate(self, a: SceneObject, b: SceneObject, context: SceneGraphContext) -> Relation | None: ...

# ---------- Where algorithms run ----------
class ComputeBackend(ABC):
    @abstractmethod
    def run(self, algorithm: str, scene_id: str, params: dict[str, Any],
            reads: list[str], writes: list[str]) -> dict[str, Any]:
        """Run an algorithm on a scene and make its outputs available in local storage."""

    @abstractmethod
    def invoke(self, algorithm: str, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Synchronous, stateless call (e.g. text embedding at query time)."""

# ---------- Infrastructure ----------
class FileStore(ABC):
    @abstractmethod
    def save_upload(self, scene_id: str, filename: str, stream: BinaryIO) -> str: ...
    @abstractmethod
    def resolve(self, scene_id: str, relative_path: str) -> Path: ...
    @abstractmethod
    def delete_scene(self, scene_id: str) -> None: ...

class SceneRepository(ABC): ...       # scenes, stage_runs, objects, relations, embeddings, messages
class JobQueue(ABC):
    @abstractmethod
    async def enqueue(self, scene_id: str, payload: dict) -> int: ...
    @abstractmethod
    async def claim(self) -> Job | None: ...
    @abstractmethod
    async def complete(self, job_id: int, error: str | None = None) -> None: ...

class EventPublisher(ABC):
    @abstractmethod
    async def publish(self, scene_id: str, event: dict) -> None: ...

class EventSubscriber(ABC):
    @abstractmethod
    def subscribe(self, scene_id: str) -> AsyncIterator[dict]: ...

class LLMClient(ABC):
    @abstractmethod
    async def chat(self, messages: list[dict], tools: list[dict] | None = None, stream: bool = False) -> Any: ...
```

---

## 6. Compute layer: where stages run

### 6.1 Principle: one image, one HTTP contract

There is no cross-provider standard API for GPU compute. Modal's native model is its Python SDK (`.remote()` calls); RunPod's native models are Pods and Serverless handlers (`/run`, `/runsync`). Code written against either SDK is locked to that provider.

What every provider does accept is the same pair:

- an **OCI (Docker) image** for `linux/amd64` with CUDA;
- an **HTTP server** inside it, listening on `0.0.0.0:<port>`.

| Provider | How it runs our image | Request time limit | Request size limit | Auth in front |
|---|---|---|---|---|
| Local GPU (Compose) | `scene-compute` service | none | none | none (private network) |
| Modal | `modal.Image.from_dockerfile` + `@modal.web_server(port)` | 150 s per request | 4 GiB body | Modal proxy auth (optional) or our token |
| RunPod Pod | Custom image, exposed HTTP port, `https://<pod-id>-<port>.proxy.runpod.net` | 100 s (Cloudflare 524) | not documented | none (public proxy) → our token |
| RunPod Serverless (load balancing endpoint) | Same image, `https://<endpoint-id>.api.runpod.ai/<path>`, health check on `/ping` | 5.5 min per request | 30 MB request and response | RunPod API key |
| Vast.ai | Registry image on a rented instance (SSH launch mode, On-start starts uvicorn), `http://<public-ip>:<random external port>` | none (direct) | none (direct) | our token; SSH tunnel for real captures |
| Any Docker host (a VM, a lab server) | `docker run --gpus all -p 9000:9000 …` | depends on proxy | depends on proxy | our token |

So the system defines its **own** small HTTP contract (6.2), designed to fit inside the strictest limits above, and runs **one image** (`scene-compute`) that implements it everywhere. The worker has a single `HttpBackend`. Switching provider means:

1. deploying the same image there (a provider-specific file under `deploy/`, or console settings);
2. adding its URL and headers to `compute.yaml`.

Algorithms, the executor, the compute server and the worker never change.

```mermaid
flowchart LR
  R[PipelineRunner] --> CB{ComputeBackend}
  CB --> IP[InProcessBackend<br/>cpu stages, inside scene-worker]
  CB --> HB[HttpBackend<br/>one implementation]
  HB -->|compute contract| L[scene-compute<br/>local GPU · shared ./data]
  HB -->|compute contract| M[scene-compute<br/>on Modal]
  HB -->|compute contract| P[scene-compute<br/>on RunPod Pod / Serverless]
  HB -->|compute contract| V[scene-compute<br/>on Vast.ai or any Docker host]
  IP & L & M & P & V --> EX[Executor<br/>registry → StageAlgorithm.run]
```

### 6.2 The compute contract

Rules every deployment of `scene-compute` satisfies:

1. Listens on `0.0.0.0:${PORT}` (default `9000`).
2. `GET /ping` returns `200` when ready and `204` while loading. This matches RunPod's load-balancer health check and works as a readiness probe anywhere.
3. **Every request completes in under 30 s.** Long work runs in the background and is polled.
4. **Every request and response body is at most `chunk_size_mb` (default 25 MB)**, so it passes RunPod Serverless's 30 MB limit. Files are moved in chunks.
5. Application auth uses the `X-Compute-Token` header (checked against `COMPUTE_TOKEN` when set). `Authorization` stays free for the provider's own key.
6. Runs are **self-contained**: before each run the worker makes sure all inputs are present (by checksum) and re-uploads what is missing. Losing a container between runs only costs a re-upload.
7. Errors use the same JSON shape as the main API: `{"error": {"code": "...", "message": "..."}}`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/ping` | `200` ready, `204` initializing |
| GET | `/info` | Image version, GPU name, installed algorithms |
| GET | `/workspaces/{scene_id}/files?dirs=recon,align` | List files under the given subdirs with `size` and `sha256` |
| PUT | `/workspaces/{scene_id}/files/{path}?offset=&total=&sha256=` | Write one chunk at `offset`; when `offset + len == total` the server verifies `sha256` |
| GET | `/workspaces/{scene_id}/files/{path}` | Download a file; supports the standard `Range` header for chunked download |
| DELETE | `/workspaces/{scene_id}` | Remove a scene workspace on that host |
| POST | `/runs` | `{algorithm, scene_id, params}` → `202 {run_id}` |
| GET | `/runs/{run_id}` | `{state: queued\|running\|done\|failed, manifest?, error?, progress?}`; `progress` is the Algorithm's latest `{done, total, unit}`, which the worker forwards on each poll |
| POST | `/invoke/{algorithm}/{method}` | Short synchronous call, e.g. `embed_text` (must finish in < 30 s) |

When `shared_storage: true` (local GPU container mounting the same `./data`), the worker skips the file endpoints entirely.

### 6.3 Compute targets (`config/compute.yaml`)

The executable [compute configuration](../backend/config/compute.yaml) defines `targets`; query-time
text embedding reuses the pipeline's embed Stage. Each Target selects `inprocess` or `http`; HTTP Targets specify URL, token,
provider headers, shared-storage mode, chunk size in bytes and startup/poll intervals in seconds.
Environment expansion supplies secrets and provider URLs. The worker defaults to a 900-second
readiness deadline and transfers at most 25,000,000 bytes per request. Local GPU uses shared storage.
The worker refuses to start when a Target named by the pipeline is unset, unknown, or an HTTP Target
without a URL. Query-time embedding waits at most 10 s for readiness and otherwise answers
`COMPUTE_UNAVAILABLE` (HTTP 503).

### 6.4 Backends in the worker (`scene_worker.compute`)

**`InProcessBackend`**: imports the algorithm through the registry and runs it directly on `DATA_DIR`. Used by the fake pipeline; the worker image only installs light extras.

Since [ADR-0005](ADR-0005-whole-pipeline-on-gpu-host.md), `HttpBackend.run` uploads only inputs present locally and never downloads outputs; `fetch(scene_id, RESULTS)` downloads results once after the last Stage. The sketch below predates that change.

**`HttpBackend`**: the only remote backend.

```python
class HttpBackend(ComputeBackend):
    def __init__(self, target: HttpTarget, data_dir: Path):
        self._t, self._data_dir = target, data_dir
        self._client = httpx.Client(base_url=target.url, headers=target.headers, timeout=target.request_timeout_s)

    # ---- ComputeBackend ----
    def run(self, algorithm, scene_id, params, reads, writes):
        self._wait_until_ready()
        if not self._t.shared_storage:
            self._sync_up(scene_id, reads)
        run_id = self._call("POST", "/runs", json={"algorithm": algorithm, "scene_id": scene_id, "params": params}).json()["run_id"]
        result = self._poll(run_id)
        if result["state"] == "failed":
            raise ComputeError(result["error"])
        if not self._t.shared_storage:
            self._sync_down(scene_id, writes)
        return result["manifest"]

    def invoke(self, algorithm, method, payload):
        self._wait_until_ready()
        return self._call("POST", f"/invoke/{algorithm}/{method}", json=payload).json()

    # ---- helpers ----
    def _wait_until_ready(self):
        deadline = time.monotonic() + self._t.startup_timeout_s
        while time.monotonic() < deadline:
            try:
                if self._client.get("/ping").status_code == 200:
                    return
            except httpx.TransportError:
                pass                                   # container still starting
            time.sleep(self._t.poll_interval_s)
        raise ComputeError(f"Target {self._t.url} not ready after {self._t.startup_timeout_s} s")

    def _poll(self, run_id):
        while True:
            result = self._call("GET", f"/runs/{run_id}").json()
            if result["state"] in ("done", "failed"):
                return result
            time.sleep(self._t.poll_interval_s)

    def _sync_up(self, scene_id, dirs):
        local_root = self._data_dir / "scenes" / scene_id
        remote = {f["path"]: f["sha256"] for f in self._list_remote(scene_id, dirs)}
        for path in iter_files(local_root, dirs):
            rel, digest, size = path.relative_to(local_root).as_posix(), sha256_file(path), path.stat().st_size
            if remote.get(rel) == digest:
                continue                               # already on the host
            for offset, chunk in read_chunks(path, self._t.chunk_bytes):
                self._call("PUT", f"/workspaces/{scene_id}/files/{rel}",
                           params={"offset": offset, "total": size, "sha256": digest}, content=chunk)

    def _sync_down(self, scene_id, dirs):
        local_root = self._data_dir / "scenes" / scene_id
        for f in self._list_remote(scene_id, dirs):
            target = local_root / f["path"]
            if target.exists() and sha256_file(target) == f["sha256"]:
                continue
            download_in_ranges(self._client, f"/workspaces/{scene_id}/files/{f['path']}", target, f["size"], self._t.chunk_bytes)

    def _list_remote(self, scene_id, dirs):
        return self._call("GET", f"/workspaces/{scene_id}/files", params={"dirs": ",".join(dirs)}).json()["files"]

    def _call(self, method, url, **kwargs):
        response = self._client.request(method, url, **kwargs)
        response.raise_for_status()
        return response
```

### 6.5 Executor (`scene_core.executor`)

Shared by the compute server and `InProcessBackend`.

```python
class Executor:
    """Loads algorithms lazily, keeps every loaded one warm, runs one job at a time per GPU."""

    def __init__(self, data_dir: Path):
        self._data_dir = data_dir
        self._loaded: dict[str, StageAlgorithm] = {}
        self._lock = threading.Lock()

    def get(self, name: str) -> StageAlgorithm:
        if name not in self._loaded:                          # never evicted: size the GPU for all models (6.8)
            algorithm = registry.create("StageAlgorithm", name)
            algorithm.setup()
            self._loaded[name] = algorithm
        return self._loaded[name]

    def run(self, name: str, scene_id: str, params: dict) -> dict:
        with self._lock:
            algorithm = self.get(name)
            workspace = SceneWorkspace(self._data_dir, scene_id)
            manifest = algorithm.run(workspace, params)
            (workspace.dir(algorithm.stage) / "manifest.json").write_text(manifest.model_dump_json(indent=2))
            return manifest.model_dump()
```

### 6.6 Compute server (`scene_compute.server`)

```python
app = FastAPI(title="Scene Compute", version="1.0.0", lifespan=lifespan)
executor = Executor(Path(os.environ.get("DATA_DIR", "/data")))
runs = RunRegistry()                      # in-memory dict + JSON copy under DATA_DIR/runs/
pool = ThreadPoolExecutor(max_workers=1)  # one GPU job at a time
ready = threading.Event()

@app.get("/ping")
def ping():
    return Response(status_code=200 if ready.is_set() else 204)

@app.post("/runs", status_code=202)
def create_run(body: RunRequest, _: None = Depends(require_token)):
    run = runs.create(body)
    pool.submit(_execute, run.id, body)
    return {"run_id": run.id}

@app.get("/runs/{run_id}")
def get_run(run_id: str, _: None = Depends(require_token)):
    return runs.get(run_id)

def _execute(run_id: str, body: RunRequest):
    runs.update(run_id, state="running")
    try:
        manifest = executor.run(body.algorithm, body.scene_id, body.params)
        runs.update(run_id, state="done", manifest=manifest)
    except Exception as exc:
        runs.update(run_id, state="failed", error=str(exc))

# file endpoints: chunked PUT with offset/total/sha256, GET with Range, listing with sha256
# /invoke/{algorithm}/{method}: getattr(executor.get(algorithm), method)(**payload)
```

At import time `scene_compute` sets `HF_HOME=$MODELS_DIR/hf` and `TORCH_HOME=$MODELS_DIR/torch` unless they are already set, so every provider only needs to mount a folder at `MODELS_DIR`. `lifespan` optionally preloads the algorithms listed in `PRELOAD_ALGORITHMS` and then sets `ready`. `require_token` compares `X-Compute-Token` with `COMPUTE_TOKEN` when the variable is set. Paths are validated against traversal before any file access.

### 6.7 Deploying the image to a provider

All provider-specific material lives in `deploy/`. None of it imports application code.

**Local GPU** — Compose profile `local-gpu` (see 11.2). Requires the NVIDIA Container Toolkit.

**Modal** — [deployment and setup](../backend/deploy/modal/README.md) builds remotely from
`docker/compute.Dockerfile` using `Image.from_dockerfile(context_dir=..., build_args=...)`.
One container serves the portable HTTP process, a Volume caches weights, and concurrency permits
polls during active Compute Runs. The worker waits through cold starts.

**RunPod Pod and Serverless** — [deployment guide](../backend/deploy/runpod/README.md) uses the
registry image. Serverless uses the load-balancing product, one worker, and an idle timeout longer
than polling. The shared compute token is mandatory behind public proxies.

**Vast.ai** — [runbook](../backend/deploy/vast/README.md) rents one instance by
hand from the web console, pulls the image pushed to Docker Hub, and starts the server from the
On-start script. Each instance has a new URL; for real captures the worker reaches it through an
SSH tunnel. Instances are destroyed after each session.

**Generic Docker host** — [deployment guide](../backend/deploy/generic/README.md) uses the same
image, persistent model cache and authenticated HTTP endpoint.

Official provider API references are linked in the guides. API verification does not establish
successful deployment: live checks require the user's provider account and credentials. Vast.ai is
the first provider exercised live; Modal, local GPU, RunPod and generic hosts are not exercised during
development. Remote disks
hold every intermediate output during a Job; only results return to local Scene storage ([ADR-0005](ADR-0005-whole-pipeline-on-gpu-host.md)).

### 6.8 GPU image and sizing

Every GPU Algorithm ships in one image, `EXTRAS=gpu` (Depth Anything 3, GeoCalib, SAM 3 through Ultralytics, MetaCLIP 2), deployed as one Target per provider (`vast`, `modal`, ...). `pipeline.yaml` assigns every GPU Stage to it through `GPU_TARGET`; a Stage can still be moved by editing its `target`. See [ADR-0002](ADR-0002-single-gpu-image-ultralytics-sam3.md) for the license and VRAM trade-off.

| Algorithm | Suggested GPU | Notes |
|---|---|---|
| `recon.da3` | ≥ 40 GB for ≤ 80 keyframes at `process_res` 504; 80 GB (A100/H100) for more, up to the pipeline's `max_keyframes` (200) | 1.4B parameters, all views in one pass |
| `align.geocalib_ransac` | ≥ 8 GB | |
| `segment.sam3` | ≥ 16 GB | Ultralytics `SAM3SemanticPredictor`; gated `sam3.pt` on Hugging Face |
| `embed.metaclip2` | ≥ 16 GB | Also serves query-time text embedding |

The Executor never unloads a model, so all of them stay in VRAM together after a full Job. A GPU Target needs **at least 48 GB of VRAM**; captures with more than 80 keyframes (the pipeline allows 200) need 80 GB (A100/H100).

---

## 7. Pipeline orchestration

### 7.1 Registry (`scene_core.registry`)

Registration uses package entry points only: `scene_stages` for Algorithms and `scene_relations`
for Relation rules. Discovery reads metadata without importing heavy dependencies. Selecting an
implementation loads its class lazily. Duplicate names fail clearly. Installing a method's optional
extra makes its implementation usable.

```toml
[project.entry-points."scene_stages"]
"recon.da3" = "scene_stages.gpu:DepthAnything3Reconstruction"
[project.entry-points."scene_relations"]
"on" = "scene_stages.graph.relations.on:OnRule"
```

### 7.2 Pipeline configuration (`config/pipeline.yaml`)

The executable [real pipeline](../backend/config/pipeline.yaml) maps the nine Stage names to
Algorithm, Target and parameters in processing order. GPU Stages (recon, align, segment, embed) name their Target through
`${GPU_TARGET}`, in the real and the fake GPU pipeline alike. No provider is the default, so the operator sets these in `.env`;
an unset variable stays literal and the worker reports it by name. Every Stage names the same
Target; the worker refuses a pipeline split across Targets ([ADR-0005](ADR-0005-whole-pipeline-on-gpu-host.md)).
The [fake GPU example](../backend/config/pipeline.fake-gpu.yaml) exercises the same remote contract
without model weights. The default walking skeleton uses fake Algorithms on CPU. Real-model
configuration requires the selected optional dependencies and verified model access.

### 7.3 Job queue on PostgreSQL (replaces Redis)

```sql
-- claim the next job; safe with several workers
UPDATE jobs
SET state = 'running', started_at = now()
WHERE id = (
  SELECT id FROM jobs WHERE state = 'queued'
  ORDER BY id
  FOR UPDATE SKIP LOCKED
  LIMIT 1
)
RETURNING *;
```

A worker that restarts finds Jobs still `running` from its previous process, marks them, their running Stage and their Scene `failed` with code `WORKER_INTERRUPTED`, and emits the matching events, so the Scene can be processed again. This assumes one worker per database, as in the Compose deployment.

- The API inserts a job and runs `NOTIFY jobs_queued`.
- The worker `LISTEN`s on `jobs_queued` and also polls every 5 s, so a missed notification only delays a job.
- Progress events use `NOTIFY scene_events, '<json>'` (payloads stay far below the 8 KB limit). The API listens and forwards them over SSE.

### 7.4 Runner (`scene_worker.runner`)

Every Job runs all Stages from the uploaded inputs: the runner deletes the remote Workspace and local Stage outputs, runs each Stage as its own Compute Run, fetches `RESULTS` and publishes ([ADR-0005](ADR-0005-whole-pipeline-on-gpu-host.md)). The skip logic sketched below was removed.

```python
class PipelineRunner:
    def __init__(self, stages: list[StageSpec], backends: dict[str, ComputeBackend],
                 repo: SceneRepository, events: EventPublisher):
        self._stages, self._backends, self._repo, self._events = stages, backends, repo, events

    async def run(self, scene_id: str, from_stage: str | None = None) -> None:
        await self._repo.set_status(scene_id, SceneStatus.PROCESSING)
        force = False
        total = len(self._stages)
        try:
            for index, spec in enumerate(self._stages):
                force = force or spec.stage == from_stage
                config_hash = spec.config_hash()
                if not force and await self._repo.has_stage_run(scene_id, spec.stage, config_hash):
                    await self._emit(scene_id, spec.stage, "skipped", index, total)
                    continue
                await self._emit(scene_id, spec.stage, "running", index, total)
                backend = self._backends[spec.target]
                manifest = await asyncio.to_thread(
                    backend.run, spec.algorithm, scene_id, spec.params, spec.reads, spec.writes)
                await self._repo.save_stage_run(scene_id, spec.stage, spec.algorithm, config_hash, manifest)
                await self._emit(scene_id, spec.stage, "done", index, total)
                force = True                                  # downstream stages depend on new outputs
            await self._repo.publish_workspace(scene_id)  # graph + embeddings transaction
            await self._repo.set_status(scene_id, SceneStatus.READY)
            await self._events.publish(scene_id, {"type": "status", "status": "ready"})
        except Exception as exc:
            await self._repo.set_status(scene_id, SceneStatus.FAILED, error=str(exc))
            await self._events.publish(scene_id, {"type": "status", "status": "failed", "error": str(exc)})
            raise

    async def _emit(self, scene_id, stage, state, index, total):
        await self._events.publish(scene_id, {"type": "stage", "stage": stage, "state": state, "index": index, "total": total})
```

`spec.reads` and `spec.writes` come from the algorithm class metadata, so remote backends transfer only what is needed.

---

## 8. Pipeline stages

Each section lists the contract that every replacement algorithm must honor.

### 8.1 Ingest — `ingest.opencv` (cpu)

- **Reads:** `raw/`. **Writes:** `keyframes/`.
- Images: apply EXIF orientation, strip metadata (including GPS), resize the long side to `long_side`.
- Video: extract frames with `ffmpeg -vf fps={video_fps}`.
- Reject blurry frames (variance of Laplacian < `blur_threshold`), badly exposed frames (> 25 % of pixels below 10 or above 245), and duplicates (perceptual hash distance < `phash_distance`). `quality_filter: false` skips all three and keeps every readable frame; `pipeline.yaml` sets it.
- If more than `max_keyframes` remain, sample uniformly in time.
- The manifest lists rejected files by reason; the UI shows them.

Ingest defaults to `min_keyframes: 10`. Fewer usable Keyframes fails early with
`NOT_ENOUGH_KEYFRAMES` and rejection counts for blur, exposure and duplicates.

### 8.2 Reconstruction — `recon.da3` (GPU)

- **Reads:** `keyframes/`. **Writes:** `recon/`.
- **Contract:** `recon/rgb/*.png` at model resolution; `recon/frames/*.npz` with `depth` (H,W, meters), `conf` (H,W), `pose` (camera-to-world 4×4, meters), `K` (3×3). Any world frame is allowed; the align stage normalizes it. Pixels without usable depth have `depth = conf = 0`.
- Model: [Depth Anything 3](https://github.com/ByteDance-Seed/Depth-Anything-3) `depth-anything/DA3NESTED-GIANT-LARGE-1.1` (1.4B parameters, CC BY-NC 4.0). The nested checkpoint predicts any-view depth and poses already in meters, so no scale conversion is applied. A non-metric checkpoint fails with `INVALID_MODEL_OUTPUT` unless `require_metric: false`.
- All Keyframes go through **one** `inference()` call, so every view shares one world frame; ingest's `max_keyframes` (200) bounds VRAM.
- Parameters: `process_res` (504, the model's training resolution), `process_res_method` (`upper_bound_resize`), `use_ray_pose` (true: poses from the ray head, more accurate than the camera head), `ref_view_strategy` (`saddle_balanced`), `confidence_percentile` (10: the least confident pixels across all views are masked).
- DA3 returns OpenCV world-to-camera `extrinsics` (N×3×4); the adapter stores their inverse as `pose`. `processed_images`, `depth`, `conf` and `intrinsics` share the processed resolution.

```python
prediction = model.inference(
    [str(path) for path in keyframes],
    use_ray_pose=True, ref_view_strategy="saddle_balanced",
    process_res=504, process_res_method="upper_bound_resize",
)
# prediction.depth (N,H,W) m · conf (N,H,W) · extrinsics (N,3,4) w2c · intrinsics (N,3,3)
# processed_images (N,H,W,3) uint8 · is_metric · scale_factor
```

> The inference arguments and `Prediction` fields follow DA3's `api.py` and `specs.py`. Check them against the installed commit.

### 8.3 Gravity alignment — `align.geocalib_ransac` (GPU)

- **Reads:** `recon/`. **Writes:** `align/`.
1. Run GeoCalib on `num_calibration_frames` frames to get gravity in camera coordinates. Rotate each into world coordinates with the camera rotation and take the spherical median → estimated up vector.
2. Fuse a point cloud from depth and pose (filtered by `conf`). RANSAC planes whose normal is within 15° of up. The lowest large horizontal plane is the floor; its normal becomes the final up vector.
3. Rotate so up is +z and translate so the floor is at z = 0.
4. Manhattan alignment: histogram the normals of vertical planes to find the dominant yaw; rotate so walls align with the x and y axes.
5. The highest large horizontal plane gives `ceiling_height`.

From this stage on, every stage reads poses from `align/`, not `recon/`.

### 8.4 Mesh — `mesh.tsdf` (cpu)

- **Reads:** `recon/`, `align/`. **Writes:** `mesh/`.
- **Point cloud** (`points.ply`, the viewer's primary layer): back-project every pixel of every aligned Frame whose confidence is at least the `points_confidence_percentile` (default 40) of all valid pixels, as DA3's own point cloud export does, colored from `recon/rgb`. Pixels whose depth jumps by more than `points_edge_threshold` (default 0.05, relative) to a valid 4-neighbor are dropped: they float between a foreground object and the wall behind it. Average positions and colors per `points_voxel_m` voxel (default 0.01; `0` keeps every point), then subsample to `max_points` (default 3,000,000) with a fixed seed. Written as binary little-endian PLY: float32 `x y z`, uint8 `red green blue`.
- **Mesh** (`mesh.glb`): NumPy projective TSDF fusion with `voxel_size_m` and `sdf_trunc_m`, confidence-weighted color integration, scikit-image marching cubes, exported via trimesh.
- The volume spans the `bounds_percentile`–(100 − `bounds_percentile`) range of the points on each axis (default 1), plus `2 × sdf_trunc_m`, so sparse far outliers neither inflate it past `max_voxels` nor enter the mesh or `points.ply`. `0` keeps every point. Checked on ScanNet `scene0011_00`: the 1–99 % range of the reconstruction is 8.5 × 6.9 m against 8.75 × 6.72 m for the ground-truth mesh, while all points span 14 × 13 m.

### 8.5 2D segmentation — `segment.sam3` (GPU)

- **Reads:** `recon/rgb`. **Writes:** `segment/`.
- Run SAM 3 through Ultralytics `SAM3SemanticPredictor` with the gated `facebook/sam3` checkpoint, in fp16 unless `half: false`.
- Process every `frame_stride`-th frame: encode the image once, then prompt the concepts from `config/vocabularies/<vocabulary_file>` (200–400 English noun phrases) in batches of `prompt_batch_size`.
- Keep masks with score ≥ `score_threshold`; merge masks with IoU > 0.8 within a frame, keeping the higher score.

### 8.6 2D → 3D lifting — `lift.maskclustering` (cpu)

- **Reads:** `recon/`, `align/`, `segment/`. **Writes:** `instances/`.
- Implement MaskClustering view consensus in-house: lift masks through aligned depth and poses, build a mask graph weighted by cross-view consensus, and iteratively cluster masks. The research repository is not vendored.
- Pure NumPy, so it runs in-process on the worker. Agglomeration keeps summed group-to-group affinity and a shared-Frame conflict matrix, updating one row and column per merge. On ScanNet `scene0011_00` (876 masks, 40 Frames) this took 64 s instead of 16 min, with identical `instances.json`.
- Label each instance by score × area weighted voting over SAM 3 labels. Drop instances seen in fewer than `min_views` views.
- Select `num_best_views` views by mask area × (1 − border contact ratio); save crops with 15 % padding.

### 8.7 Embeddings — `embed.metaclip2` (GPU)

- **Reads:** `instances/`. **Writes:** `embeddings/`.
- `run()`: encode each instance's crops, take a score-weighted mean, L2-normalize.
- `embed_text(texts)`: exposed through `ComputeBackend.invoke` for query time. Accepts Vietnamese or English directly because Meta CLIP 2 is multilingual.

### 8.8 Attributes — `attributes.vlm_api` (cpu)

The configured pipeline runs `attributes.none` instead, which writes an empty entry per Instance and calls no endpoint; see [ADR-0004](ADR-0004-skip-vlm-attributes.md). The VLM Algorithm below is kept for switching back.


- **Reads:** `instances/`. **Writes:** `attributes/`.
- Sends 1–3 crops per object to an OpenAI-compatible vision model and asks for JSON: `{color: [], material: [], state: [], label_vi: ""}`.
- Endpoint and model come from `VLM_BASE_URL`, `VLM_API_KEY`, `VLM_MODEL`; a local server works as well as a cloud API.
- Each request has a total deadline of `request_timeout_s` (default 90), checked while streaming the body because some endpoints send keep-alive bytes that reset socket timeouts, and is retried `max_retries` times (default 2) on timeouts, transport errors, 429 and 5xx. An Object still without an answer is recorded in `attributes/errors.json`; other 4xx responses fail the Stage. 429 and 5xx wait before retrying (`Retry-After` when given, otherwise 1 s, 2 s, … capped at 10 s).
- Objects are described in parallel with up to `concurrency` requests in flight (default 8); `attributes.json` and `errors.json` keep the Instance order.
- Optional params: `max_crops` (default 3), `max_tokens`, and `extra_body`, a mapping merged into every request body for provider-specific options such as OpenRouter's `reasoning: {enabled: false}` or `provider: {sort: throughput}`.

### 8.9 Scene graph — `graph.geometric` (cpu)

- **Reads:** `align/`, `instances/`, `embeddings/`, `attributes/`. **Writes:** `graph/` only.
1. Fit gravity-aligned oriented boxes: height from z extent, yaw from 2D PCA of the footprint.
2. Apply every configured `RelationRule` to every object pair (a room has well under 200 objects).
3. Write the Scene Graph file, preserving each Instance id as exactly one Object id.

After all Stages succeed, the worker publishes this file and `embeddings/objects.npz` through
the Scene repository in one database transaction. Algorithms never access the database; see
[ADR-0001](ADR-0001-worker-publishes-scene-graph.md).

| Predicate | Condition (meters, z-up) |
|---|---|
| `on(A,B)` | \|bottom(A) − top(B)\| < 0.05 and footprint overlap > 50 % of A |
| `under(A,B)` | footprint overlap > 30 % and top(A) < bottom(B) |
| `above(A,B)` | footprint overlap > 30 % and bottom(A) > top(B) + 0.05 |
| `inside(A,B)` | > 80 % of A's points inside B's box |
| `next_to(A,B)` | surface distance < 0.5 and not `on` / `inside` |
| `near(A,B)` | surface distance < 1.0 |
| `against_wall(A)` | a box face within 0.1 of the nearest wall |

`left_of` / `right_of` are view-dependent and computed at query time.

```python
class OnRule(RelationRule):
    predicate = "on"

    def evaluate(self, a, b, context):
        a_bottom = a.box.center[2] - a.box.size[2] / 2
        b_top = b.box.center[2] + b.box.size[2] / 2
        if abs(a_bottom - b_top) < 0.05 and footprint_overlap_ratio(a.box, b.box) > 0.5:
            return Relation(subject_id=a.id, predicate="on", object_id=b.id)
        return None
```

### 8.10 Question answering — `QAAgent` (scene-api)

The LLM plans and phrases; **all numbers come from tools**.

```python
class AgentTool(ABC):
    name: ClassVar[str]
    description: ClassVar[str]
    parameters: ClassVar[dict]              # JSON Schema
    @abstractmethod
    async def execute(self, scene_id: str, arguments: dict) -> dict: ...
```

| Tool | Behavior |
|---|---|
| `find_objects(query, top_k)` | `TextEmbedder` + pgvector cosine search, combined with `label` / `label_vi` matching |
| `count_objects(query)` | `find_objects` + similarity threshold |
| `measure_distance(a_id, b_id, mode)` | Surface-to-surface or center-to-center, meters |
| `get_relations(object_id, predicate?)` | Reads stored relations |
| `relative_direction(a_id, b_id, viewpoint)` | Left/right/front/behind from the viewer camera or an object's front |
| `get_object(object_id)` | Label, size, attributes, evidence image URLs |
| `get_room_info()` | Floor size, ceiling height, object counts by label |

Flow:
1. The system prompt requires answering in the question's language, using only tool results, and listing the relevant `object_ids`.
2. Function-calling loop, at most 6 steps.
3. Final result `{answer, object_ids, evidence}` is streamed over SSE; the frontend highlights the objects and flies the camera to them.

---

## 9. Backend API

### 9.1 Contract rules

- **Versioned prefix:** everything under `/api/v1`.
- **OpenAPI is the source of truth:** `uv run tasks.py openapi` writes `openapi/openapi.json` from the FastAPI models; the frontend generates its types from that file.
- **Error format:** `{"error": {"code": "SCENE_NOT_FOUND", "message": "Scene not found."}}` with a matching HTTP status. Codes are UPPER_SNAKE_CASE English. Search answers `COMPUTE_UNAVAILABLE` (503) when the embed Stage's Target is unset or unreachable.
- **File URLs are issued by the API:** responses contain absolute URLs such as `mesh_url`. The frontend never builds storage paths.
- **Units:** meters; coordinates z-up with the floor at z = 0.
- **Single user, local:** no authentication. Ports are bound to `127.0.0.1` in Compose. `CORS_ORIGINS` lists the frontend origin.

```python
# scene_api/main.py
app = FastAPI(title="Scene Understanding API", version="1.0.0", lifespan=lifespan)   # dependencies wired in lifespan
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"])
app.include_router(api_router, prefix="/api/v1")
```

```python
# scene_api/export_openapi.py
import json, sys
from scene_api.main import app
json.dump(app.openapi(), sys.stdout, ensure_ascii=False, indent=2)
```

### Scene lifecycle guards

Uploads are accepted only in `created` or `uploaded`. Uploads after processing or failure return
HTTP 409 `SCENE_LOCKED`. An active Job makes Process, upload and delete return HTTP 409
`SCENE_BUSY`; a partial unique index on queued/running Jobs enforces one active Job per Scene.
Failed Scenes may be reprocessed but their capture stays immutable. Deletion removes database
rows, local Scene files and every non-shared remote Workspace.

### 9.2 Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/scenes` | Create a scene `{name}` → `{scene_id}` |
| GET | `/api/v1/scenes` | List scenes |
| GET | `/api/v1/scenes/{scene_id}` | Status, stage runs, ingest report, `mesh_url` |
| DELETE | `/api/v1/scenes/{scene_id}` | Delete database rows and the scene folder (and remote copies) |
| POST | `/api/v1/scenes/{scene_id}/uploads` | Multipart upload of images or a video, streamed to `raw/` |
| POST | `/api/v1/scenes/{scene_id}/process` | Enqueue processing of every Stage from the start |
| GET | `/api/v1/scenes/{scene_id}/events` | SSE progress |
| GET | `/api/v1/scenes/{scene_id}/objects` | Objects with boxes, attributes, evidence URLs |
| GET | `/api/v1/scenes/{scene_id}/search?q=` | Free-text object search |
| POST | `/api/v1/scenes/{scene_id}/queries` | `{question, camera?}` → SSE answer stream |
| GET | `/api/v1/scenes/{scene_id}/files/{path}` | Serve a published file (`mesh/`, `instances/crops/`, `keyframes/`) |

The files endpoint only serves whitelisted subdirectories and rejects path traversal (`..`, absolute paths).

### 9.3 SSE events

**Progress** (`GET …/events`, consumed with `EventSource`). On connect the API first sends the current state from `stage_runs`, then streams live events:

```jsonc
{"type": "stage", "stage": "attributes", "status": "running", "started_at": "…", "updated_at": "…"}
{"type": "progress", "stage": "attributes", "done": 48, "total": 155, "unit": "object"}
{"type": "stage", "stage": "attributes", "status": "done", "started_at": "…", "updated_at": "…"}
{"type": "stage", "stage": "mesh", "status": "skipped"}
{"type": "status", "status": "ready"}
{"type": "status", "status": "failed", "error": {...}}
```

The worker stores and emits `progress` at most every 2 seconds per Stage and always emits the final
report (`done == total`). The latest report and the Stage start time live in `stage_runs.progress`
and `stage_runs.started_at` (`migrations/002_stage_progress.sql`), so the replay on connect carries
them. Stages that report: ingest (image), align, mesh and segment (frame), lift (mask), embed and
attributes (object); recon and graph report nothing and show an indeterminate bar.

**Answers** (`POST …/queries`, read with `fetch` and a `ReadableStream`):

```jsonc
{"type": "tool", "name": "measure_distance"}
{"type": "delta", "text": "The table is about "}
{"type": "final", "answer": "...", "object_ids": ["o12", "o7"],
 "evidence": [{"object_id": "o12", "image_url": "http://localhost:8000/api/v1/scenes/.../files/instances/crops/o12_0.jpg"}]}
```

`ProgressEvent` and `QueryEvent` are pydantic models referenced in the route `responses`, so they appear in `openapi.json`.

### 9.4 Database schema (`migrations/001_init.sql`)

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE scenes (
  id             uuid PRIMARY KEY,
  name           text NOT NULL,
  status         text NOT NULL,
  error          text,
  floor_z        real,
  ceiling_height real,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE jobs (
  id          bigserial PRIMARY KEY,
  scene_id    uuid NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
  payload     jsonb NOT NULL DEFAULT '{}',
  state       text NOT NULL DEFAULT 'queued',      -- queued | running | done | failed
  error       text,
  created_at  timestamptz NOT NULL DEFAULT now(),
  started_at  timestamptz,
  finished_at timestamptz
);
CREATE INDEX jobs_queued_idx ON jobs (id) WHERE state = 'queued';

CREATE TABLE stage_runs (
  scene_id    uuid NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
  stage       text NOT NULL,
  algorithm   text NOT NULL,
  config_hash text NOT NULL,
  manifest    jsonb NOT NULL,
  finished_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (scene_id, stage)
);

CREATE TABLE objects (
  scene_id   uuid NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
  id         text NOT NULL,
  label      text NOT NULL,
  label_vi   text,
  box        jsonb NOT NULL,
  attributes jsonb NOT NULL DEFAULT '{}',
  best_views jsonb NOT NULL,
  embedding  vector(1024),          -- must equal the embedding model's dimension
  PRIMARY KEY (scene_id, id)
);
CREATE INDEX objects_embedding_idx ON objects USING hnsw (embedding vector_cosine_ops);

CREATE TABLE relations (
  scene_id   uuid NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
  subject_id text NOT NULL,
  predicate  text NOT NULL,
  object_id  text,
  value      real
);

CREATE TABLE messages (
  id         bigserial PRIMARY KEY,
  scene_id   uuid NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
  role       text NOT NULL,
  content    jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
```

Changing to an embedding model with a different dimension requires migrating `objects.embedding`; it is the only implementation-specific detail in the schema.

---

## 10. Frontend

The frontend is an independent Next.js application. It knows the backend only through `NEXT_PUBLIC_API_URL` (browser), `API_INTERNAL_URL` (server-side rendering) and `openapi/openapi.json`.

### 10.1 Stack

- Next.js (App Router, TypeScript), managed with `npm`.
- Tailwind CSS and shadcn/ui.
- TanStack Query for server state; Zustand for viewer state (selection, highlights, camera).
- React Three Fiber and drei for the 3D viewer (`useGLTF`, `CameraControls`).
- next-intl for UI strings in `en` and `vi`. All code, keys and comments are English; only `messages/vi.json` contains Vietnamese.
- `openapi-typescript` + `openapi-fetch` for a typed API client.
- MSW (Mock Service Worker) for a mock backend during UI development.

### 10.2 Source layout

```
src/
├── app/[locale]/
│   ├── page.tsx                    # scene list + "New scene"
│   ├── scenes/new/page.tsx         # capture guide + upload
│   └── scenes/[sceneId]/page.tsx   # progress → viewer
├── components/
│   ├── capture/CaptureGuide.tsx
│   ├── upload/UploadDropzone.tsx
│   ├── upload/QualityBadge.tsx
│   ├── progress/StageStepper.tsx
│   ├── viewer/SceneCanvas.tsx
│   ├── viewer/layers/
│   │   ├── MeshLayer.tsx
│   │   ├── ObjectBoxesLayer.tsx
│   │   └── index.ts
│   ├── viewer/MeasureTool.tsx
│   ├── search/SearchBar.tsx
│   ├── objects/ObjectList.tsx
│   └── chat/ChatPanel.tsx
├── lib/
│   ├── api/schema.d.ts             # generated, do not edit
│   ├── api/port.ts                 # SceneApi interface
│   ├── api/http.ts                 # real backend
│   ├── api/mock/                   # mock implementation + fixtures
│   ├── api/index.ts                # selects http or mock
│   ├── quality/blurWorker.ts       # Laplacian variance in a Web Worker
│   └── store/viewerStore.ts
└── i18n/
```

### 10.3 API layer

```ts
// lib/api/port.ts
import type { components } from "./schema";
type Schemas = components["schemas"];

export type ProgressEvent = Schemas["ProgressEvent"];
export type QueryEvent = Schemas["QueryEvent"];

export interface SceneApi {
  createScene(name: string): Promise<Schemas["SceneCreated"]>;
  uploadFiles(sceneId: string, files: File[], onProgress?: (ratio: number) => void): Promise<void>;
  startProcessing(sceneId: string, fromStage?: string): Promise<void>;
  listScenes(): Promise<Schemas["SceneSummary"][]>;
  getScene(sceneId: string): Promise<Schemas["SceneDetail"]>;
  listObjects(sceneId: string): Promise<Schemas["SceneObject"][]>;
  searchObjects(sceneId: string, query: string): Promise<Schemas["SearchHit"][]>;
  subscribeProgress(sceneId: string, onEvent: (event: ProgressEvent) => void): () => void;
  askQuestion(sceneId: string, body: Schemas["QueryRequest"], onEvent: (event: QueryEvent) => void, signal?: AbortSignal): Promise<void>;
}
```

```ts
// lib/api/index.ts
import { httpSceneApi } from "./http";
import { mockSceneApi } from "./mock";

export const sceneApi: SceneApi =
  process.env.NEXT_PUBLIC_API_MODE === "mock" ? mockSceneApi : httpSceneApi;
```

Uploads use `XMLHttpRequest` (or `fetch` with a stream) against the multipart endpoint so the UI can show a progress bar.

Schema names (`SceneDetail`, `QueryRequest`…) must match the backend pydantic model names.

`package.json` scripts:

```json
{
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint",
    "api:sync": "cp ../backend/openapi/openapi.json openapi/openapi.json && npm run api:types",
    "api:sync:live": "openapi-typescript http://localhost:8000/openapi.json -o src/lib/api/schema.d.ts",
    "api:types": "openapi-typescript openapi/openapi.json -o src/lib/api/schema.d.ts"
  }
}
```

### 10.4 Replaceable viewer layers

```ts
export interface SceneLayerProps {
  sceneId: string;
  assets: SceneAssets;              // { meshUrl, pointsUrl, ... }
}
export type SceneLayer = React.ComponentType<SceneLayerProps>;

// viewer/layers/index.ts — a new rendering method is a new entry
export const sceneLayers: Record<string, SceneLayer> = {
  points: PointCloudLayer,          // default: dense colored point cloud from points.ply
  mesh: MeshLayer,                  // TSDF mesh, off by default
  boxes: ObjectBoxesLayer,
};
```

The viewer store keeps per-layer visibility (`points` and `boxes` on, `mesh` off) and the toolbar toggles it. `PointCloudLayer` frames the camera on the cloud's bounds once loaded and only listens for clicks while measuring, with a 2 cm raycast threshold.

`SearchBar` and `ChatPanel` only write `highlightedIds` to the store; `ObjectBoxesLayer` reads it to draw highlights and fly the camera.

### 10.5 User flow

1. **New scene:** three capture tips (walk along the walls, shoot at two heights, turn the lights on), then a dropzone for photos or a video.
2. **Upload:** a Web Worker scores sharpness and exposure for each image (green / amber / red badge); upload shows progress; a "Process" button starts the pipeline.
3. **Processing:** `StageStepper` follows SSE and shows plain-language stage names, a Job bar where every Stage weighs 1/9 and the running one adds its reported share, elapsed time per Stage, and for the running Stage a bar with "done/total unit" plus a linear time estimate once 5 % and 10 s have passed.
4. **Viewer:** full-screen 3D canvas, a search bar on top, a side panel (bottom sheet on mobile) with "Objects" and "Ask" tabs, and a two-point measuring tool. Tapping an object shows its name, size, evidence photos and suggested questions.
5. **Answer:** text answer, highlighted objects, camera fly-to and evidence images.

---

## 11. Docker Compose and tooling

Each project has its own `compose.yaml`. On one machine they share a Docker network named `scene-net`: the backend creates it, the frontend joins it as `external`. Server-side Next.js calls `http://scene-api:8000`; the browser calls `http://localhost:8000`.

### 11.1 Backend `.env.example`

```dotenv
# Compose
COMPOSE_PROJECT_NAME=scene-backend

# Storage (see 4.3)
DATA_DIR=/data                       # container path of the scene-data volume
MODELS_DIR=/models                   # container path of the model cache
HOST_MODELS_DIR=./models             # host folder for the model cache (survives down -v)

# PostgreSQL
POSTGRES_USER=scene
POSTGRES_PASSWORD=scene
POSTGRES_DB=scene
DATABASE_URL=postgresql://scene:scene@postgres:5432/scene

# API
API_PUBLIC_URL=http://localhost:8000
CORS_ORIGINS=http://localhost:3000

# Compute
PIPELINE_CONFIG=/app/config/pipeline.yaml
COMPUTE_CONFIG=/app/config/compute.yaml
COMPUTE_TOKEN=                       # shared secret sent as X-Compute-Token to every remote target
GPU_TARGET=                          # compute.yaml Target name for every GPU Stage; no provider is the default
COMPUTE_IMAGE_REPO=<dockerhub-user>/scene-compute   # tags {fake|gpu}-<git short sha>

# Provider keys (only for the targets you use)
RUNPOD_API_KEY=

# Hugging Face (gated weights for local GPU)
HF_TOKEN=

# LLM and VLM (OpenAI-compatible; cloud or local)
LLM_BASE_URL=
LLM_API_KEY=
LLM_MODEL=
VLM_BASE_URL=
VLM_API_KEY=
VLM_MODEL=
```

### 11.2 Backend `compose.yaml`

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - postgres-data:/var/lib/postgresql/data
      - ./migrations:/docker-entrypoint-initdb.d:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 5s
      retries: 10

  scene-api:
    build:
      context: .
      dockerfile: docker/python.Dockerfile
      args: { PACKAGE: scene-api }
    command: ["uvicorn", "scene_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
    env_file: .env
    ports: ["127.0.0.1:8000:8000"]
    volumes:
      - scene-data:/data
      - ./config:/app/config:ro
    depends_on:
      postgres: { condition: service_healthy }

  scene-worker:
    build:
      context: .
      dockerfile: docker/python.Dockerfile
      args: { PACKAGE: scene-worker, SYSTEM_PACKAGES: ffmpeg }
    command: ["python", "-m", "scene_worker.main"]
    env_file: .env
    volumes:
      - scene-data:/data
      - ./config:/app/config:ro
    depends_on:
      postgres: { condition: service_healthy }

  scene-compute:
    profiles: ["local-gpu"]
    build:
      context: .
      dockerfile: docker/compute.Dockerfile
      args: { EXTRAS: "${LOCAL_GPU_EXTRAS:-}" }
    env_file: .env
    environment:
      PORT: "9000"
      COMPUTE_TOKEN: ""              # private network, no token needed locally
    expose: ["9000"]
    volumes:
      - scene-data:/data
      - ${HOST_MODELS_DIR}:/models
      - ./config:/app/config:ro
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]

volumes:
  scene-data:        # uploads, stage outputs, run records — removed by `down -v`
  postgres-data:     # database — removed by `down -v`

networks:
  default:
    name: scene-net
```

The local GPU service requires the NVIDIA Container Toolkit on the host.

Notes on storage:
- `docker compose down` keeps all data; `docker compose down -v` deletes `scene-data` and `postgres-data`, so the next `up` starts with an empty database (migrations run again) and no scenes.
- `./models` is a bind mount and is never touched by Docker cleanup. `uv run tasks.py init-storage` creates it with your user as owner before the first start.
- The PostgreSQL image tag is pinned (`pg16`) because the data format is tied to the major version.

### 11.3 `docker/python.Dockerfile` (API and worker)

```dockerfile
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ARG PACKAGE
ARG SYSTEM_PACKAGES=""
RUN if [ -n "$SYSTEM_PACKAGES" ]; then \
      apt-get update && apt-get install -y --no-install-recommends $SYSTEM_PACKAGES && rm -rf /var/lib/apt/lists/*; \
    fi

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY packages packages
COPY services services
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package ${PACKAGE}

ENV PATH="/app/.venv/bin:$PATH"
```

### 11.4 Portable GPU image

The [compute Dockerfile](../backend/docker/compute.Dockerfile) is the single build definition for
all GPU providers. Build context is the repository root (where `pyproject.toml` and `uv.lock` live).
Empty `EXTRAS` installs the fake contract pipeline; `gpu` installs every real GPU Algorithm.
Modal builds this file remotely. Other providers consume its published Linux amd64 image.

### 11.5 Cross-platform tasks

Run `uv run tasks.py --help` from the repository root for the stdlib-only task runner. Tasks cover
start/stop/reset, tests, OpenAPI export, model download, image build/push and Modal deployment.
`reset` removes Scene and database volumes while preserving the host model cache.
The implementation in `tasks.py` is the command reference on Windows and POSIX hosts.

### 11.6 Frontend `.env.example`

```dotenv
COMPOSE_PROJECT_NAME=scene-frontend
NEXT_PUBLIC_API_URL=http://localhost:8000    # browser
API_INTERNAL_URL=http://scene-api:8000       # server-side, over scene-net
NEXT_PUBLIC_API_MODE=http                    # http | mock
```

### 11.7 Frontend `compose.yaml`

```yaml
services:
  web:
    build:
      context: .
      args:
        NEXT_PUBLIC_API_URL: ${NEXT_PUBLIC_API_URL}
        NEXT_PUBLIC_API_MODE: ${NEXT_PUBLIC_API_MODE}
    env_file: .env
    ports: ["127.0.0.1:3000:3000"]
    networks: [scene-net]

networks:
  scene-net:
    external: true
```

To run the frontend in mock mode without the backend, create the network first (`docker network create scene-net`) or use `npm run dev`.

### 11.8 Frontend `Dockerfile`

```dockerfile
FROM node:24-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:24-alpine AS build
WORKDIR /app
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_API_MODE=http
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL NEXT_PUBLIC_API_MODE=$NEXT_PUBLIC_API_MODE
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:24-alpine
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
```

`next.config.ts` must set `output: "standalone"`.

---

## 12. Extending and replacing components

### 12.1 Replace an algorithm (example: another reconstruction method)

1. Add a `StageAlgorithm` such as `recon.mymethod` in `packages/scene-stages/src/scene_stages/`, with the same `reads`, `writes` and `ReconManifest` as `recon.da3`. If the model is not metric, the class itself must convert to meters; that is part of the contract.
2. Add an extra `recon-mymethod`, include it in the `gpu` extra of scene-compute, and add an entry point.
3. Set `algorithm: recon.mymethod` in `pipeline.yaml`.
4. Rebuild and redeploy the compute image (`uv run tasks.py up-local-gpu`, or `uv run tasks.py push-compute-image` and redeploy on the provider).
5. Process the Scene again (every Job runs all Stages).

No change to the runner, other stages, the API or the frontend.

### 12.2 Move a stage to another provider

Point `GPU_TARGET` in `.env` at another Target (or change `target` for that stage in `pipeline.yaml`). If the target is new, deploy the image there (6.7) and add its URL and headers to `compute.yaml`. No code changes.

### 12.3 Add a provider

- **It can run a Docker image and expose an HTTP port** (almost every GPU cloud): deploy `scene-compute`, add a target with `backend: http`. Put any provider-specific deploy file under `deploy/<provider>/`.
- **It cannot** (it only accepts its own function or handler format): add a thin adapter under `deploy/<provider>/` that runs inside the provider and forwards to the same `Executor`, or choose a different product of that provider that runs containers. The worker side stays `HttpBackend`.

### 12.4 Change points at a glance

| To change | Write | Configure |
|---|---|---|
| A pipeline method | A `StageAlgorithm` class + uv extra | `pipeline.yaml` → `algorithm` |
| Where a stage runs | Nothing | `pipeline.yaml` → `target`, `compute.yaml` |
| GPU provider | A deploy file or console settings under `deploy/<provider>/` | `compute.yaml` (URL + headers) |
| Embedding model | A `StageAlgorithm` with `embed_text` | `pipeline.yaml` (queries reuse the embed Stage's Algorithm and Target), migrate `vector(dim)` |
| LLM / VLM | Nothing (OpenAI-compatible) or an `LLMClient` adapter | `.env` |
| Spatial relation | A `RelationRule` | `graph.params.relations` |
| QA capability | An `AgentTool` | `scene_api/container.py` |
| 3D rendering | A `SceneLayer` component | `sceneLayers` |
| API contract | Backend routes and models, then `uv run tasks.py openapi` | Frontend: `npm run api:sync` |

---

## 13. Running the system

### 13.1 Backend

```bash
cd backend
cp .env.example .env              # LLM_*, VLM_*, COMPUTE_TOKEN, provider keys you need
uv sync                           # local tooling and tests

# Pick where GPU stages run: GPU_TARGET in .env

# A. Local GPU
uv run tasks.py up-local-gpu

# B. Remote GPU (Vast.ai, Modal, RunPod, any Docker host)
# Vast.ai: uv run tasks.py push-compute-image [--extras gpu], then deploy/vast/README.md
uv run tasks.py deploy-modal       # remote build from Dockerfile; no registry push
# Other providers use the registry image (section 6.7).
#   and put the endpoint URL in config/compute.yaml
uv run tasks.py up

uv run tasks.py openapi                      # refresh the API contract
#   API docs: http://localhost:8000/docs
```

### 13.2 Frontend

```bash
cd frontend
cp .env.example .env
npm ci
npm run api:sync                  # copy the contract and generate types
docker compose up -d --build      # joins scene-net
#   Web: http://localhost:3000

# UI development without the backend
NEXT_PUBLIC_API_MODE=mock npm run dev
```

### 13.3 Day-to-day

- Changed an algorithm: rebuild and redeploy the compute image, then `POST /api/v1/scenes/{scene_id}/process`.
- Changed `pipeline.yaml`, `compute.yaml` or a Target variable in `.env`: `uv run tasks.py up` (recreates the containers with the new values).
- Check a target: `curl -H "X-Compute-Token: $COMPUTE_TOKEN" <url>/info`.
- Disk usage: `uv run tasks.py disk-usage` (Docker volumes and the model cache). Remove one scene with `DELETE /api/v1/scenes/{scene_id}`.
- Start over: `uv run tasks.py reset` (same as `docker compose down -v`) deletes every scene and the database; model weights in `./models` stay. Delete `./models` manually to free that space too.
