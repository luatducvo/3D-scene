# ADR-0009: Show Objects by their membership, not boxes

Status: accepted. Date: 2026-10-18. Amends [SPEC](../SPEC.md) user story 28 and the M1 and M5
acceptance lines: the viewer shows an Object by highlighting its own points and mesh vertices, and
draws no boxes.

## Context

Scene test1 has 172 Objects. Drawn as box outlines, they covered the room and hid the geometry, and
a highlighted box differed from the others only in colour. Many Objects are parts of other Objects,
such as handles on a wardrobe or outlets on a wall, so their boxes nest and point picking with
invisible boxes chose the outer box.

## Decision

- The graph Stage publishes Object Membership (`graph/membership.bin`, see
  [api.md](../architecture/api.md)). It lists every point of `points.ply` and every vertex of
  `mesh.glb` within `membership_radius_m` of an Object's lifted points. A point can belong to
  several Objects.
- The viewer removes the boxes layer. Hover, selection, search and chat highlight an Object's
  membership. A GPU pick pass finds the Object under the cursor; where Objects overlap, the
  smallest one wins.
- Objects keep their oriented boxes in the Scene Graph and the API. Relations, measurements, QA and
  camera framing still use them; only drawing changed.

## Alternatives considered

- **Keep boxes, hidden by default.** Cheap, but a box shows a volume, not the thing, and nested
  boxes still made picking pick the outer box.
- **Overlay each Object's lifted points.** This needs no index mapping, but the overlay sits up to
  one voxel off the displayed cloud and cannot cover the mesh.

## Consequences

- A Scene published before this change has `membership_url: null`. It shows geometry without
  highlighting until it is processed again.
- The membership file must match the published `points.ply` and `mesh.glb` index order. A count
  mismatch turns highlighting off in that layer.
- Mesh-view highlighting and pick cost on a dense room are verified live
  ([GPU-INTEGRATION](../GPU-INTEGRATION.md)).
