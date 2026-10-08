# Ticket acceptance evidence

Date: 2026-10-08. Windows, Docker Desktop, RTX 3050 6 GiB.
All 24 tickets are implemented. Tests use synthetic contracts at module seams;
GPU and installation gates below use the licensed local scans and actual models.

| Tickets | Evidence |
| --- | --- |
| 01, 05 | Native static web and health endpoint, Windows/Linux frozen lock, loopback Compose, generated OpenAPI/TS checks, successful native and Docker web builds. GitHub Actions passed at `a582aea`: `spikes/github-ci.json`. Later application revisions passed local tests/builds. |
| 02 | Actual CUDA-enabled MinkowskiEngine; both raw scans at 2/3 cm, VRAM/timing/proposals in `spikes/mask3d.json`, decision in ADR 0008. Image saved in `.backups/s3d-mask3d.tar`. |
| 03 | Pinned router, 4k/q8 presets, two-image vision, unloading and 30-case schema smoke: ADR 0007 and `spikes/llm-b11459.json`. |
| 04 | Both real Packages packed/verified by independent PEP 723 script; parallel batch skips valid files; independent unaligned copy packed with identity matrix; 2 synthetic prep tests pass. |
| 06 | Both native and clean Compose `s3d models pull` downloaded and verified all 7 assets. Clean runtime worked with outbound TCP blocked. |
| 07, 08 | Synthetic import contracts, corruption checks, no-op/Replace and durable fake-stage/restart tests; both real Packages imported. |
| 09–13 | Both scans completed GPU geometry, Mask3D, YOLOE and MobileCLIP2. Packed mesh preserves vertex order; decoder tests pass. Viewer inspected bed/bbox, labels, colors and evidence. Stage/config/memory evidence: `spikes/stage-runs.json`, `spikes/unaligned-pipeline.json`, `spikes/scene0000_01-stage-runs.json`. |
| 14–17 | Lookup runs on CPU; semantic gap/solver/graph/visibility/predicate tests pass. Viewpoint reversal, degenerate fallback, Structures, counts, NOT and relaxed constraints covered. Real 10 handwritten Programs passed: `spikes/query-eval.json`. |
| 18 | Production schema, retry and cloud-client tests; 30 scene questions: 29 valid Programs, 26/28 target-set agreements. Original spike prompts also replayed against the production schema: 25/25 text, 1/5 synthetic vision valid (`spikes/program-spike-replay.json`). Production vision uses numeric Tiebreak/captions, not image-to-Program generation. Invalid Programs produce Clarify. |
| 19, 20 | Verified number/ID guard regression tests; SSE parser, related highlighting, sessions/Clarify and query journal. Fresh multi-turn bed → it → color succeeds: `spikes/clean-rebuild.json`. |
| 21, 22 | Real two-keyframe Tiebreak and lazy caption cache: `spikes/vision-validation.json`. Fresh installation repeated the same cached bed description. Top-N precaption generated successfully with N=1 in 3.49s; router resident list empty afterward, 4,527 MiB free. |
| 23 | Reprocess from stages, active-job rejection, Package-preserving deletion/Replace contracts and UI controls. Both real replacements/reprocessing completed. |
| 24 | Fresh clone built Mask3D and API, pulled 7 models into empty volumes, processed a real scan and answered six turns. Final application image at `232dc87` also passed with an internal Docker network and outbound TCP error 101: `spikes/clean-rebuild.json`. Configuration-only compatible endpoint returned a verified count of 4. Backup restored to a disposable volume: `spikes/backup-restore.json`. |

## Checks

- Backend: **54 pytest tests passed**, including actual CUDA visibility equivalence.
- Standalone prep: **2 unittest tests passed** outside backend imports.
- Frontend: **2 Vitest tests passed**, TypeScript and static export passed.
- Ruff and OpenAPI freshness checks passed; npm audit reported no vulnerabilities.
- Both review axes completed and findings fixed: [review](code-review.md).

## Limits

The semantic evaluation compares Programs on detected Objects; it is not ScanRefer
ground truth or a claim that every detected label is correct. The final browser
screenshot API timed out; Structure Lookup and UI/console checks succeeded. Earlier
mesh, bbox and Keyframe visual inspection succeeded. CI evidence names its exact
remote commit; newer local commits have not been pushed by the agent.

Raw data, Packages, model files, compiled image backups and temporary clean-clone
files are ignored by Git. Default Compose serves at `http://127.0.0.1:8000`.
