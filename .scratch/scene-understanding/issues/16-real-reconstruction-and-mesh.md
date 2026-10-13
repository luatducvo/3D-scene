# 16: Real reconstruction and mesh

**What to build:** MapAnything reconstruction on Modal and TSDF meshing on CPU replace their fakes, so my own room appears as a real metric mesh in the viewer. Alignment stays fake but passes poses through unchanged. Each GPU Algorithm can pre-download its weights.

**Blocked by:** 14, 08, 12

**Status:** needs-live-check — adapter, extras and CPU mesh test done; MapAnything on Modal and the room capture not run

- [ ] Processing my room capture produces a recognizable mesh in the viewer.
- [ ] Reconstruction outputs follow the contract (model-resolution RGB, per-Frame depth in meters, confidence, camera-to-world pose, intrinsics) and the Manifest records metric scale.
- [ ] A known dimension (e.g. a door's height) measures plausibly in meters.
- [ ] MapAnything inference arguments and output keys are checked against the installed version; torch pins across GPU dependency groups are resolved.
- [ ] A mesh Stage contract test runs on synthetic reconstruction fixtures on CPU.
