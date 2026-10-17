# ADR-0006: Each Job publishes an immutable, versioned result folder

Status: accepted. Date: 2026-10-17. Amends [ADR-0005](0005-whole-pipeline-on-gpu-host.md) on how
results replace the Scene's local copy.

## Context

After the last Stage the worker downloaded the results, committed Objects, Relations and `ready`,
and then renamed the downloaded folders over the Scene's published copy in `DATA_DIR/scenes/{id}`.
A database transaction cannot roll back file renames: a crash or I/O error between the commit and
the renames left new Objects next to old or missing files, with the Scene already `ready`. Every
Job also reused the same asset URLs, which the viewer uses as cache keys, so an open browser could
keep showing the previous Job's mesh or point cloud.

## Decision

- A Job's results become a folder of their own, `DATA_DIR/scenes/{scene}/{job id}/`. The worker
  downloads into staging, renames the complete folder into place, validates it, and only then
  commits. The folder is never modified afterwards.
- `scenes.publication` holds the Job id the Scene serves. `SceneStore.publish` sets it in the same
  transaction as Objects, Relations, the room info, the finished Job and `ready`.
- If validation or the commit fails, the new folder is removed and the previous publication stays
  served. After a successful commit, every other folder of the Scene is removed; a crash before
  that leaves an unreferenced folder that the next publication removes.
- Files are served at `/scenes/{id}/publications/{version}/files/{path}`. Asset and best-view URLs
  name the current version, so a new publication never shares a URL with an old one. Scenes
  published before this change have no version; they are served from the Scene folder under the
  version `legacy` until they are processed again.

## Alternatives considered

- Commit first, then swap folders (the previous design): leaves a window where the database points
  at files that do not exist yet.
- Swap folders first, then commit: a failed commit leaves new files with old Objects.
- Content-hash cache busting on the old URLs: fixes the browser cache but not the crash window.

## Consequences

- Disk briefly holds two publications of a Scene, until the new one commits.
- An old URL returns 404 once its publication is removed; the viewer gets the new URLs from the API.
- Migration 004 adds `scenes.publication`.
