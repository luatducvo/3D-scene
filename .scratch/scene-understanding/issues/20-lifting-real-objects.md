# 20: 2D → 3D lifting — real Objects

**What to build:** The in-house re-implementation of MaskClustering's view-consensus lifting: masks to 3D points via aligned depth and poses, a mask graph weighted by cross-view consensus, iterative clustering, score × area label voting, dropping Instances seen in too few views, best-view selection and padded crops. Combined with the real Scene Graph, my room's furniture appears as real Object boxes.

**Blocked by:** 19, 17, 18

**Status:** needs-live-check — algorithm and synthetic test done; real-room smoke not run

- [ ] Processing my room shows boxes around real furniture with sensible labels.
- [ ] Each Instance becomes exactly one Object with the same id through to the UI.
- [ ] Each Object has best-view crops visible as evidence in its detail view.
- [ ] A Stage Algorithm contract test on synthetic masks and depth (two Frames seeing one box) yields one Instance with the correct label and view count.
