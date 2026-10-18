# 02: Search Objects with a relative similarity heatmap

**What to build:** An English free-text query finds Objects, frames them, and paints their geometry with an honest per-query heatmap from the API's raw cosine values.

**Blocked by:** 01: Explore Objects in Original and Instances appearances.

**Status:** done

- [x] Extend search hits end to end with raw_similarity while keeping the existing score and ranking/inclusion behavior. The ranking bonus never enters the heatmap normalization.
- [x] Update the API schema export, generated frontend contract, HTTP client consumption, and mock search responses together.
- [x] Normalize raw cosine over returned Objects per query, strongest hottest and weakest coolest; use one hot level for one result or equal scores and explain that case in the legend.
- [x] Paint each returned Object uniformly through membership. The legend explains relative similarity within this query, not a probability or confidence, and not comparable across queries.
- [x] Focus the camera on results. Distinguish empty responses from failures and unavailable compute; No results restores the selected base appearance.
- [x] Search replaces the active QA visualization. Clear and clearing search input remove its heatmap; background updates or stale responses cannot reclaim the viewer after a newer result, Clear, or a Scene change.
- [x] Preserve hover/selection feedback, both geometry views, and measurement over the heatmap, restoring its colors when feedback ends.
- [x] Verify raw versus bonus scores and ranking at the backend REST seam; verify UI normalization, equal/single/empty/error cases, result replacement, and stale responses through SceneApi/MSW. Visually verify the real heatmap and legend.
- [x] Update API/frontend documentation with score semantics, visualization behavior, and the compute Target requirement.

### Demo

Use a fixture whose highest label-boosted ranking score is not its highest raw similarity. Show the correct heatmap, compare another query, exercise equal and empty results, and Clear back to Instances.
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
