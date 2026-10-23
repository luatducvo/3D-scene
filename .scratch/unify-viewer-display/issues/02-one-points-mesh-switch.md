# 02: One Points/Mesh switch

**What to build:** The user changes the room's geometry in one place: a two-way Points/Mesh switch that always shows exactly one of the point cloud or the mesh. The viewer opens on Points when the Scene has a point cloud, else on Mesh, and an option with no geometry behind it is disabled. The point-size slider sits beside the switch and appears only in Points mode. The "Display layers" panel, both buttons that open it, and the topbar "Clear" button are gone; the Search box's own clear remains the way to clear a Search. See the parent spec, `.scratch/unify-viewer-display/spec.md`.

**Blocked by:** 01 (Interactive explorer test harness)

**Status:** ready-for-agent

- [ ] The topbar has one Points/Mesh switch; the viewer can never show both layers or neither.
- [ ] The default mode is Points when the Scene has a point cloud, else Mesh; each option is disabled when its geometry is missing.
- [ ] The point-size slider is beside the switch and only present in Points mode.
- [ ] The Display layers panel, its topbar and spatial-tools buttons, and the per-layer toggle in the viewer store are removed; layers change only through the geometry mode.
- [ ] The topbar "Clear" button is removed.
- [ ] Translation strings used only by the removed controls are deleted from `messages/en.json`.
- [ ] The frontend architecture page no longer lists a layers side panel.
- [ ] View-rule tests cover the default mode and that switching shows exactly one layer.
- [ ] Component tests cover the single switch, the slider only in Points mode, and the absence of the Display layers panel and the Clear button.
- [ ] Done check passes: `npm run typecheck`, `npm test`, `npm run build` in `frontend/`.
