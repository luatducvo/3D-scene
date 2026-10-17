# 07: Versioned, immutable publication

**What to build:** Each Job publishes its results into a directory of its own,
`DATA_DIR/scenes/{scene}/{job}/`, finished before the database changes and never modified after.
`SceneStore.publish` records that version on the Scene (`scenes.publication`) in the same transaction
as Objects, Relations and `ready`; asset URLs carry the version. Older versions are removed after the
commit. Today `replace_results` commits first and renames after, so a crash in between pairs new
database rows with old files, and unchanged asset URLs let an open browser keep old geometry (audit R2).

**Blocked by:** 03, 06

**Status:** implemented

- [x] Migration 004 adds `scenes.publication`. ADR-0006 records the layout and ordering.
- [x] `TargetWorkspace.replace_results(scene_id, version, publish)`: download into staging, rename
      into the version directory, call `publish`; on failure remove that directory; after success
      remove the Scene's other versions and any pre-versioning result folders.
- [x] Files are served at `/scenes/{id}/publications/{version}/files/{path}`; `assets` and best-view
      URLs use the Scene's current version. Scenes published before this change (no version) keep
      working until they are reprocessed.
- [x] Tests: a publish that fails after the version directory exists leaves the earlier publication
      served and no orphan; two successive Jobs give different asset URLs; the old version is gone.
- [x] OpenAPI exported, frontend synced; docs (pipeline, api, compute, overview) updated.
