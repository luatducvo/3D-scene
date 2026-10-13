# 08: View the room in 3D

**What to build:** After processing, the Scene page shows the 3D viewer with the mesh and Object boxes. The worker publishes the Scene Graph and Object embeddings into Postgres after the last Stage (per ADR-0001); the API exposes Objects, a mesh URL in the Scene detail, and the whitelisted files endpoint; the frontend renders the mesh and box layers through the replaceable layer map.

**Blocked by:** 06

**Status:** done

- [ ] A `ready` Scene from the fake pipeline shows a box-room mesh and Object boxes I can orbit and zoom.
- [ ] Objects returned by the API carry boxes in meters (z-up, floor at z = 0) and absolute evidence URLs issued by the API.
- [ ] The files endpoint serves only whitelisted subfolders and rejects traversal attempts.
- [ ] Reprocessing replaces published Objects and Relations rather than duplicating them.
- [ ] API tests cover publish results, Objects listing and the files whitelist.
