# 03: Instance Colors switch

**What to build:** The user turns Instance Colors on and off with one switch, in either geometry mode, and every Object is painted in its own stable colour; geometry that belongs to no Object keeps its captured colour. It only colours: no boxes or labels are added. When Object Membership is missing or does not fit the shown geometry, the switch is disabled and the existing "Object highlighting could not be loaded." notice stays. See the parent spec, `.scratch/unify-viewer-display/spec.md`.

**Blocked by:** 01 (Interactive explorer test harness)

**Status:** ready-for-agent

- [ ] One Instance Colors switch replaces the `original | instances` button pair, with a label in `messages/en.json`; strings used only by the pair are removed.
- [ ] The switch keeps its state across Points/Mesh changes and works in both modes.
- [ ] The switch is disabled whenever the existing highlight-availability rule reports a failure, and the notice is still shown.
- [ ] Painter tests keep covering stable, distinguishable Instance Colors and shared points owned by the smallest Object.
- [ ] Component tests cover toggling the switch and its disabled state without membership.
- [ ] Done check passes: `npm run typecheck`, `npm test`, `npm run build` in `frontend/`.
