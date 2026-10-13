# 17: Gravity alignment

**What to build:** The real alignment Algorithm: GeoCalib gravity estimate, floor plane by RANSAC, rotation so up is +z with the floor at z = 0, Manhattan yaw so walls follow the axes, and ceiling height from the highest large horizontal plane. Plane fitting and Manhattan helpers are pure-numpy geometry in scene-core.

**Blocked by:** 16

**Status:** needs-live-check — adapter and geometry tests done; GeoCalib on Modal not run

- [ ] My room's mesh sits with the floor at z ≈ 0 and walls parallel to the viewer's axes.
- [ ] The Scene reports floor and ceiling height when the ceiling is visible.
- [ ] Unit tests on synthetic point clouds cover plane fitting, floor selection and dominant-yaw estimation.
