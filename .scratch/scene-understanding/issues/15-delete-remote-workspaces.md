# 15: Deleting a Scene removes remote Workspaces

**What to build:** Deleting a Scene also deletes its Workspace on every non-shared remote Target, so no copies are left on provider disks.

**Blocked by:** 13

**Status:** done

- [ ] After processing on a non-shared Target and deleting the Scene, the Target lists no files for that Scene.
- [ ] An unreachable Target does not block local deletion; the failure is logged.
- [ ] Covered by a test at the compute-contract seam.
