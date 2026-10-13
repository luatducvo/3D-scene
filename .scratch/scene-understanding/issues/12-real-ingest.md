# 12: Real ingest and ingest report

**What to build:** The real CPU ingest Algorithm replaces the fake: apply EXIF orientation, strip metadata including GPS, resize, extract frames from video, reject blurry, badly exposed and duplicate frames, sample down to the keyframe cap, and fail with `NOT_ENOUGH_KEYFRAMES` below `min_keyframes`. The Scene page shows the ingest report.

**Blocked by:** 07

**Status:** done — video input path has no automated test

- [ ] Uploading a mix of good, blurred, dark and duplicate fixture images produces Keyframes only from the good ones; the report lists rejected files by reason.
- [ ] A short video is split into Frames and ingested like photos.
- [ ] Keyframes are upright and carry no EXIF/GPS metadata.
- [ ] Too few usable Frames fails the Scene with `NOT_ENOUGH_KEYFRAMES` and per-reason counts; the UI suggests creating a new Scene and recapturing.
- [ ] Stage Algorithm contract tests (seam 3) cover each rejection reason, video input and `min_keyframes`.
