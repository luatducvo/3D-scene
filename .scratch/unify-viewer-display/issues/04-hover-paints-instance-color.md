# 04: Hover paints the Object's Instance Color

**What to build:** When nothing is selected and no Search is active, hovering an Object paints exactly its points or vertices in its own Instance Color, so the user sees which geometry belongs to it; its label still follows the cursor. With Instance Colors on, the hovered Object keeps its colour and every other Object dims instead. Moving off the Object or the canvas returns the plain appearance. The white hover tint is gone. See the parent spec, `.scratch/unify-viewer-display/spec.md`.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] The Painter knows every Object's Instance Color whatever the appearance, using the same stable palette as Instance Colors.
- [ ] In original appearance, a hovered Object's owned elements take its Instance Color and every other element keeps its captured colour.
- [ ] Under Instance Colors, a hovered Object keeps its colour and every other element is dimmed by the existing dim factor.
- [ ] Ownership follows the smallest-Object rule shared with picking.
- [ ] Ending the hover restores the plain appearance exactly.
- [ ] The white hover tint is removed.
- [ ] Painter tests assert per-point colours for hover in both appearances and the restore on hover end.
- [ ] Done check passes: `npm run typecheck`, `npm test`, `npm run build` in `frontend/`.
