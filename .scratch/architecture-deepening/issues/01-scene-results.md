# 01: Scene Results module

**What to build:** A `SceneResults` module in scene-core, next to `SceneWorkspace`, that is the only
code that knows the published result files of a Scene. Today the runner hard-codes
`graph/scene_graph.json` and `embeddings/objects.npz` (runner.py:89-93). The api hard-codes
`mesh/mesh.glb`, `mesh/points.ply` and `recon/rgb/<frame>.png` and keeps its own public allowlist
(main.py:49, 64, 112). The dimension 1024 appears in four places. See
[spec](../spec.md#scene-results-ticket-01).

**Blocked by:** None

**Status:** implemented

- [x] `SceneResults` reads the Scene Graph and Object embeddings from a Workspace root and validates
      them (same Object ids, `EMBEDDING_DIM`, finite values) before any transaction opens; the
      runner's `publish` uses it.
- [x] It returns the asset paths (mesh, points, best-view images) that `get_scene` and
      `public_objects` turn into URLs; no other module builds these paths.
- [x] Public file serving allows only `mesh/` and `recon/rgb/`; `keyframes` and `instances` return 404.
- [x] One `EMBEDDING_DIM` constant; runner, api search and fakes use it; a Postgres test compares it
      with the `objects.embedding` column type.
- [x] Tests exercise the module through its interface with a fake-pipeline Workspace.
- [x] docs/architecture/pipeline.md and api.md describe the module and the public file rule.
