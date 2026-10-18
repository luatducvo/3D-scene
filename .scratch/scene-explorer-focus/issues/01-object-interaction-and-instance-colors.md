# 01: Explore Objects in Original and Instances appearances

**What to build:** A user can switch a processed Scene between reconstructed colors and stable colors for individual Objects, then hover, select, inspect dimensions, focus, navigate, and measure without losing the chosen appearance.

**Blocked by:** None (can start immediately).

**Status:** done

- [x] Default to Original; provide Instances independently of Point Cloud/Mesh, with stable distinct colors for Object IDs, including Objects sharing a label.
- [x] Render through published Object Membership on both geometry representations. For overlapping geometry use the existing smaller-membership ownership and deterministic ties; unassigned geometry retains its original color.
- [x] Preserve hover labels, click selection, distinct hover/selection feedback, dimensions, camera focus, Home, orbit, zoom, and pan.
- [x] Removing transient feedback restores the underlying appearance without accumulating color changes.
- [x] Include the necessary prefactoring inside this user-visible slice: separate base appearance, selection/hover, and one active search/QA visualization. Provide Clear, retaining existing search/QA highlights while restoring the selected base appearance on clearing.
- [x] Preserve two-point straight-line measurement, its meters display, measure-again and exit; measurement clicks do not select Objects accidentally.
- [x] Missing, failed, or mismatched membership keeps the geometry visible with an honest notice and no fabricated Object colors or picking.
- [x] Verify through existing SceneApi/MSW behavior and focused ownership/color-rule tests where necessary; visually inspect Point Cloud and Mesh in a desktop browser.
- [x] Update relevant viewer architecture explanations with the delivered behavior. No API or persistence change is required for this slice.

### Demo

Open the synthetic Scene, switch between Original and Instances, select an overlapping small Object, use an existing result highlight, Clear, and measure a segment. The chosen base colors return correctly throughout.
## Completion requirements

- [x] Use the existing backend REST API/SSE and frontend SceneApi/MSW test seams as applicable, with fake Algorithms and ScriptedLLM instead of live GPU/LLM services. Add focused pure tests only for necessary numerical or color/ownership behavior.
- [x] Run checks appropriate to the changes, including API export/client regeneration when contracts change and frontend typecheck/tests/build for UI changes. Record actual outcomes.
- [x] Check the delivered desktop UI in a browser; do not treat a mocked canvas as proof of actual WebGL coloring or picking correctness. Record any live GPU verification separately from local checks.
- [x] Update relevant architecture and product documentation in the same change, preserving accepted decisions on disabled VLM attributes, Target execution, versioned Publication, private Frame images, and membership rendering.

## Scope reference

Follow the Focused English Scene explorer specification for shared behavior and exclusions. This ticket does not authorize unrelated features or deletion of existing stored conversations.

## Comments

Implemented and verified on 2026-10-19. See the [shared completion report](../validation.md)
for automated results, desktop browser evidence, independent review findings and their fixes,
and the explicit limit that these are mock-data UI checks rather than live reconstruction checks.
