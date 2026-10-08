# S3D: shared instructions for coding agents

## Start here

1. Read this file before planning or changing the repository.
2. Read [current status](docs/project-status.md) for the latest recorded delivery,
   verification evidence, remaining work and migration caveats. Check `git status
   --short` and recent commits to identify changes made since that record.
3. Read the scoped `AGENTS.md` for each directory you will change. These files
   extend this root file; paths in this file are relative to the repository root.
4. Read the issue and the contract relevant to the task using the map below.
   Begin implementation once the intended behavior and affected boundaries are clear.

User instructions take precedence over repository guidance. When code, a current
contract and a historical ticket disagree, identify the discrepancy and use the
confirmed current decision. ADR 0009 and ticket 25 supersede v1 input requirements.

## Architecture

S3D is a local, single-user application for exploring prepared indoor 3D Scenes
and answering English questions with measured Objects and Keyframe evidence.

```text
Outside S3D:
dataset/scans -> tools/scannet_prep.py (CPU) -> dataset/preprocessing/*.s3dpkg

Inside S3D:
browser upload -> FastAPI Import -> app-owned Package + SQLite job
  -> S1 extract -> S2 geometry -> S3 Mask3D -> S4a labels -> S4b embeddings
  -> optional S4c captions -> S5 Scene graph -> S6 mesh.bin -> ready Scene

question + viewer camera -> Lookup OR validated Program + deterministic Solver
  -> optional vision Tiebreak / Clarify -> SSE answer + highlights + Evidence
```

| Area | Responsibility | Read before changes |
| --- | --- | --- |
| `backend/` | FastAPI, SQLite, jobs, pipeline, retrieval, Solver, LLM orchestration | [backend guidance](backend/AGENTS.md) |
| `frontend/` | Next static web, React Three Fiber viewer, upload, SSE chat | [frontend guidance](frontend/AGENTS.md) |
| `tools/` | Independent ScanNet prep and evaluation/spike utilities | [tools guidance](tools/AGENTS.md) |
| `mask3d/` | Isolated CUDA inference service with shared-volume paths | [Mask3D guidance](mask3d/AGENTS.md) |
| `docs/` | Contracts, ADRs, verification records and project status | [docs guidance](docs/AGENTS.md) |
| `.scratch/` | Ticket specifications and acceptance tracking | [ticket guidance](.scratch/AGENTS.md) |
| `compose*.yaml`, `Dockerfile`, `docker/`, `models.lock` | Deployment, pinned runtimes and model assets | [setup](README.md), ADRs 0002–0004 and 0007–0008 |

## Boundaries to preserve

- **Input:** upload is the sole application input. Accept aligned `s3dpkg/2`
  Packages. Preprocessing applies source `axisAlignment` to mesh, normals and
  camera poses outside S3D; S1 validates/extracts without applying it again.
  Missing/invalid alignment fails prep. V1 input requires preparation from raw scans.
- **Storage:** upload copies the Package into application storage. Preserve the
  user's raw scans and preprocessing outputs. Mesh vertex order connects masks,
  superpoints and viewer Instance IDs and must remain consistent.
- **GPU:** the API runs in one process with one job worker and a shared GPU
  admission lock. GPU stages release the local LLM first and use child processes
  to reclaim VRAM. Read `gpu.py`, `pipeline.py` and relevant ADRs before changing
  concurrency or model residency.
- **Answers:** the Solver determines spatial results and counts. Model wording
  preserves verified facts and IDs; vision uses actual Keyframes. Web UI and
  questions are English (ADR 0006); project discussion/docs may be Vietnamese.
- **Deployment:** FastAPI serves the exported web app. Production Compose binds
  the host port to loopback and stores data/models in separate named volumes.
  Keep raw/preprocessing folders outside application mounts and build inputs.

## Read by task

- Domain names: [GLOSSARY.md](GLOSSARY.md) for Scan/Preprocessing/Package/Scene/Import;
  [CONTEXT.md](CONTEXT.md) for graph and question terminology.
- Input/prep/import: [Package contract](docs/s3dpkg-spec.md),
  [ADR 0009](docs/adr/0009-external-preprocessing-upload-only.md),
  [ticket 25](.scratch/s3d-v3/issues/25-external-preprocessing-upload-only.md).
- Mesh/masks/viewer: [binary mesh contract](docs/mesh-bin.md).
- Behavior/acceptance: relevant ticket in `.scratch/s3d-v3/issues/` and
  [implementation plan](docs/implement_plan.md), accounting for superseded requirements.
- Setup/commands: [README.md](README.md). Verification history and limitations:
  [docs/verification.md](docs/verification.md), then the linked evidence for the claim.

## Working and finishing

- Use an isolated data directory for tests; production Scene storage is user data.
  Preserve existing artifacts when a validation fails. Request user authorization
  for destructive volume resets or replacing real Scenes unless already authorized.
- Keep dependencies and models reproducible through the existing lockfiles and
  pinned images. Keep datasets, Packages, model weights, secrets and backups ignored.
- Verify the affected public behavior with focused tests/checks. For API changes,
  export `backend/openapi.json` and regenerate `frontend/src/generated/api.ts`
  together; read the scoped instructions for commands and additional checks.
- At task completion, update `docs/project-status.md` when delivery, verification,
  outstanding work or deployment state changes. Update the affected contract/ADR
  and ticket acceptance record in the same change. Record what was actually checked,
  including date, code revision, environment and limitations; distinguish local
  evidence from remote CI and a saved runtime snapshot from a live check.
- Keep `AGENTS.md` focused on durable guidance. Store changing delivery facts in
  the status file, detailed evidence in `docs/verification.md`/`docs/spikes/`, and
  commands in their owning configs or README. Report changed files, checks and
  remaining work to the user.
