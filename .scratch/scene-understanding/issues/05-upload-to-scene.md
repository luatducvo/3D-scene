# 05: Upload photos or a video to a Scene

**What to build:** Uploading images or a single video into a Scene, streamed to its raw folder, from a basic dropzone on the new-Scene page. Status moves from `created` to `uploaded`; multiple batches are allowed before processing.

**Blocked by:** 04

**Status:** done

- [ ] From the browser I can drop several images (or one video) into a Scene and see them accepted; the Scene becomes `uploaded`.
- [ ] A second batch to the same `uploaded` Scene is accepted and added.
- [ ] Large files are streamed to disk, not held in memory.
- [ ] Non-image/video files are rejected with a clear error code.
- [ ] API tests cover the status transition and multi-batch upload; a committed synthetic fixture set (tiny generated images) is introduced and used.
