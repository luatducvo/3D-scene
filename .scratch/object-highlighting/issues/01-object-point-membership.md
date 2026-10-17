# 01: Object point membership

**What to build:** The graph Stage writes, for every Object, which points of `mesh/points.ply` and
which vertices of `mesh/mesh.glb` belong to it, and the Scene publishes that file to browsers so
the viewer can highlight an Object's own geometry instead of drawing its box. Today the per-Instance
points from lift (`instances/points/<id>.npy`, 2 cm voxels, aligned frame) never leave the Target
and are not public (`SceneResults.DIRECTORIES`, `SceneResults.PUBLIC` in
[results.py](../../../backend/packages/scene-core/src/scene_core/results.py)), so the frontend has
no way to know which point belongs to which Object.

Scene `test1` (f54146f6-4562-4c4f-9ed1-c2b69606b40e) has 172 Objects, 611,471 points and
360,450 faces; the format must stay small and fast to decode at that size.

**Blocked by:** None

**Status:** implemented — every check passes on fake and synthetic Scenes; test1 gets the file when it is reprocessed on the GPU Target

- [x] `graph.geometric` assigns a point or mesh vertex to every Object that has a lift point within
      `membership_radius_m` (default 0.02, the lift voxel size). A point may belong to several
      Objects (a door handle's points also belong to the wardrobe that contains it); points near
      no Object belong to none.
- [x] Membership uses final Object ids, so it is computed after every Instance becomes its Object.
- [x] One compact binary file per Scene, per Object a list of point indices and a list of mesh
      vertex indices (CSR-style offsets plus indices), in Object order with the ids recorded. It
      returns from the Target with the other results and is the only new public path; `instances/`
      stays private.
- [x] `SceneAssets` gains the file's URL, `null` when the Scene was published before this change.
      `uv run main.py openapi` and `npm run api:sync` run.
- [x] The fake graph Algorithm writes a valid membership file for the fake room; a REST test reads
      the asset URL and decodes it, and a published Scene without the file reports `null`.
- [x] A test on a small synthetic Scene shows a point inside two overlapping Objects listed under
      both, and a point beyond the radius under none.
- [x] docs/architecture/pipeline.md (graph Stage, Scene Results) and api.md (assets) updated.
