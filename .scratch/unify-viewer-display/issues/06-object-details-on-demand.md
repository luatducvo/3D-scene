# 06: Object Details on demand

**What to build:** Selecting an Object no longer opens the Object Details panel. The user opens it with a new Object Details button among the spatial tools, which is always visible and disabled while nothing is selected. While open, the panel shows whichever Object is selected and follows the Selection when it changes. Dropping the Selection closes the panel. See the parent spec, `.scratch/unify-viewer-display/spec.md`.

**Blocked by:** 01 (Interactive explorer test harness)

**Status:** ready-for-agent

- [ ] Selecting an Object leaves the side panel as it was; nothing opens on its own.
- [ ] The spatial tools have an Object Details button with a label in `messages/en.json`, disabled without a Selection.
- [ ] Pressing the button opens the panel for the selected Object; pressing it again closes it.
- [ ] Selecting another Object while the panel is open shows that Object.
- [ ] Dropping the Selection (empty-space click or Esc) closes the panel.
- [ ] Opening Measurement or Scene info still replaces the panel as today.
- [ ] Component tests cover the disabled button, opening only on press, following the Selection and closing on deselect.
- [ ] Done check passes: `npm run typecheck`, `npm test`, `npm run build` in `frontend/`.
