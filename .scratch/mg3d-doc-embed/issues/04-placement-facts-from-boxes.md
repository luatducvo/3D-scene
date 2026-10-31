# 04: Placement facts from the Objects' boxes

**What to build:** Plain, deterministic code for `embed.mg3d_doc` that computes each Object's placement facts from the objects Stage's boxes, in the gravity-aligned frame (floor at z = 0), and the mesh's horizontal footprint. Every threshold is an Algorithm param. The facts are:

- Size in metres, and height of the box bottom above the floor.
- Support: A rests on B when A's bottom is within 5 cm of B's top and their footprints overlap by at least 50% of A's footprint (the largest overlap wins). Otherwise A rests on the floor when its bottom is within 5 cm of z = 0. Otherwise A is mounted or hanging.
- The 2 nearest Objects.
- Room position: by a wall within 30 cm of the footprint boundary, in a corner when near two boundary edges, otherwise in the open.

See `../spec.md`, "Algorithm embed.mg3d_doc".

**Blocked by:** 01

**Status:** ready-for-agent

- [x] Tests on hand-built boxes cover: resting on a desk, on the floor, and mounted; overlap just below 50%; the largest overlap winning
- [x] Tests cover the two nearest neighbours
- [x] Tests cover by a wall, in a corner and in the open against a synthetic footprint
- [x] Thresholds come from params, and a non-positive threshold raises `INVALID_PARAMETERS`
- [x] No GPU or model weights are needed
- [x] `uv run main.py lint` and `uv run main.py test` pass
