# 05: Idle, Search and Selection are exclusive

**What to build:** The viewer is always in exactly one of three interaction states, and only that state paints.

- **Idle**: hover works as in ticket 04, and clicking an Object selects it.
- **Search** (the Search box holds non-blank text, whether the request is in flight, failed or returned nothing): the Object Heatmap, dimming, legend and camera flight work as today. Hover is off. Only a Search Hit can be clicked, and clicking it selects it, empties the Search box and drops the Highlight. Clicking empty space or a non-hit does nothing. Esc ends the Search.
- **Selection**: the selected Object is painted the way hover paints in Idle, and hover is off. Clicking another Object selects it. Clicking empty space or Esc returns to Idle without bringing back an earlier Search. Typing a Search drops the Selection. The camera no longer moves on Selection.

The cursor shows a pointer only over Objects that can be clicked in the current state. See the parent spec, `.scratch/unify-viewer-display/spec.md`.

**Blocked by:** 01 (Interactive explorer test harness), 04 (Hover paints the Object's Instance Color)

**Status:** ready-for-agent

- [ ] The viewer store holds the Search text; the explorer's Search box reads and writes it, and the debounced Search request still starts from the explorer.
- [ ] The interaction state is derived from the Selection and the Search text, never stored separately.
- [ ] The canvas reports intent (hover, click on an Object or on nothing, Esc) to the store instead of selecting and deselecting directly, and the store applies the per-state rules above.
- [ ] One pure "can this Object be clicked now" rule drives both clicks and the pointer cursor.
- [ ] Selecting drops the Search text, the Highlight and the similarities, and advances the result version so a late Search response is discarded.
- [ ] Selection no longer focuses the camera; Search still focuses its hits.
- [ ] The Painter paints one state at a time: the plain appearance, the emphasised Object (hovered or selected), or the Search heatmap. The orange Selection colour and the plain green Highlight colour are removed.
- [ ] GLOSSARY's relationship line reads that selecting an Object ends the Search and clears its Highlight, and that a new Search clears the Selection.
- [ ] Store tests walk every transition: hover ignored in Search and Selection; clicking a hit during Search; clicking a non-hit or nothing during Search; switching Selection; Esc in each state; typing a Search while selected; a stale Search response after a Selection; the clickable rule.
- [ ] Painter tests cover Selection painting in both appearances and the heatmap under both appearances.
- [ ] Component tests cover selecting a Search Hit emptying the Search box.
- [ ] Done check passes: `npm run typecheck`, `npm test`, `npm run build` in `frontend/`.
