# 10: Object list and detail panel

**What to build:** A side panel listing all Objects (with English and, when present, Vietnamese labels). Tapping an Object in the list or the viewer selects it, highlights it, and shows its label, size in meters, attributes and best-view evidence photos.

**Blocked by:** 08

**Status:** done

- [ ] The Objects tab lists every Object of a `ready` Scene.
- [ ] Selecting an Object (in the list or in 3D) highlights its box and opens a detail view with label, size (L × W × H in meters), attributes and evidence images.
- [ ] Selection state lives in the viewer store; layers read it, panels write it.
- [ ] Frontend tests cover list rendering and selection against the mock API.
