# Current project status

Last updated: **2026-10-09** (Asia/Bangkok).
Application baseline: **`b060319`**. Current documentation changes establish shared
agent instructions and a usage-focused README; they do not change application behavior.

Read this file after the root `AGENTS.md`. This is the maintained summary of
delivery state; consult linked contracts and evidence for detail. Check the local
Git state and runtime before treating a saved observation as current.

## Delivered

- Tickets 01–24: initial S3D application implemented, including GPU Scene
  processing, 3D viewer, Lookup/Program/Solver, Sessions, Clarify and Evidence.
- Ticket 25 / ADR 0009: external preprocessing and upload-only input implemented
  and reviewed. This is the current input policy and supersedes historical v1
  and inbox requirements in the initial tickets.
- Shared agent guidance: root and scoped `AGENTS.md` files, with thin entry files
  for Claude Code and GitHub Copilot. All entry files point to the same guidance
  and this status record.
- README reorganized as an English usage guide with architecture, prep,
  startup, upload, questions, storage, and troubleshooting. Native development and
  advanced operation instructions live in `development.md` and `operations.md`.

## Current architecture and input

The architecture map and durable boundaries are in [root AGENTS.md](../AGENTS.md).
Setup commands are in [README.md](../README.md).

The confirmed flow is:

```text
dataset/scans -> independent CPU prep -> dataset/preprocessing/*.s3dpkg
  -> user upload -> app-owned Package -> Scene pipeline -> viewer and questions
```

Prep fully aligns mesh, normals and camera poses. The current
[Package contract](s3dpkg-spec.md) is `s3dpkg/2`; S1 validates/extracts without
reapplying alignment. Missing/invalid source alignment fails prep. Old v1
Packages need prep from raw scans. See [ADR 0009](adr/0009-external-preprocessing-upload-only.md)
and [ticket 25](../.scratch/s3d-v3/issues/25-external-preprocessing-upload-only.md).

## Last recorded verification

Application checks recorded for the changes delivered in `b060319`:

| Check | Result | Evidence |
| --- | --- | --- |
| Backend / standalone prep / frontend | 56 / 5 / 2 tests passed | [input review](code-review-input-v2.md) |
| Lint, API contract/types, TypeScript, native and Docker builds | Passed | [verification](verification.md) |
| Two real v2 Packages; independent validation and S1 | Passed; source files preserved, no double transform | [prep evidence](spikes/preprocessing-v2.json) |
| Deployed API input boundary and legacy Scene preservation | Inbox 404; v1 upload/S1 reload 400; two Scenes unchanged | [live API evidence](spikes/upload-v2-live.json) |
| Input code review | Standards 1 P3; Spec 2 P2; all fixed | [review details](code-review-input-v2.md) |

Earlier real GPU pipeline, offline installation, query evaluation and backup
checks are recorded under **Historical v1 implementation** in
[verification.md](verification.md). Remote CI was verified at `a582aea`; the
newer application delivery has local verification, not a recorded remote CI run.
The query evaluation compares detected Objects with hand-authored Programs and
is not a ScanRefer ground-truth benchmark. The latest browser screenshot capture
timed out; recorded UI state checks are described separately in the review.

For the shared-agent documentation setup, instruction/status link targets were
checked, guidance was compared with current source/contracts, and `git diff
--check` passed. Application suites were not rerun for this documentation change.

## Last recorded local deployment and user action

On 2026-10-09, the API image containing the input revision was deployed with normal
Compose at `http://127.0.0.1:8000`. The two existing processed Scenes remained ready;
their source Packages in application storage were still v1. Reprocessing those
sources from S1 requires a v2 upload; existing aligned artifacts remain readable.

Two prepared v2 files are available locally and ignored by Git:

- `dataset/preprocessing/scene0000_00.s3dpkg`
- `dataset/preprocessing/scene0000_01.s3dpkg`

The agent prepared and verified them without importing them into the running app.
The user's next step is manual upload with **Replace** for the existing IDs.
Confirm whether the user has since done this before changing the deployment.

Default checkout volume names were `3d-scene_s3d-data` and `3d-scene_s3d-models`;
these depend on the Compose project name. Production API mounts are `/data` and
`/models`. Raw scans, preprocessing outputs, models and backups are local-only
and absent from a fresh clone.

## Remaining work

No unimplemented criteria are recorded for tickets 01–25. Manual upload of the
prepared v2 files remains a user action. Publishing/pushing the latest delivery
has not been performed by the agent. Recheck Git and runtime for changes after
this snapshot before reporting either action as still pending or completed.

## Maintain this record

For each delivery that changes behavior, verification or remaining work, update
the date, application revision, affected summary, evidence links and outstanding
actions here. For unfinished work, record the next concrete step and any blocker.
Update the affected ticket/contract in the same change. Keep old measurements in
their evidence files and summarize only the latest applicable result here.
