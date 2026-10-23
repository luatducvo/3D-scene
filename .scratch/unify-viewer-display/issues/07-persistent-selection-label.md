# 07: Persistent Selection label in 3D

**What to build:** While an Object is selected, its name is shown in the 3D view, anchored at the top centre of its box, and it follows the camera as the user orbits, zooms or pans. The label stays until the Selection is dropped or moves to another Object. The cursor-following hover label is unchanged. See the parent spec, `.scratch/unify-viewer-display/spec.md`.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] The selected Object's label is rendered in the canvas above the top centre of its box, using the Object's label text.
- [ ] The label moves with the camera and disappears when the Selection is dropped.
- [ ] Selecting another Object moves the label to it.
- [ ] Nothing is shown for a selected id that is not among the Scene's Objects.
- [ ] Where the anchor point is computed from the box, a pure view-rule test covers it, including a rotated box.
- [ ] Done check passes: `npm run typecheck`, `npm test`, `npm run build` in `frontend/`.
