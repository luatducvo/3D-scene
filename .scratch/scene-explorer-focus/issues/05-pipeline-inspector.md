# 05: Inspect how the pipeline produced the Scene

**What to build:** A user opens an Inspector beside the viewer, selects a Stage, and understands its purpose and real available execution facts without running the compute Target.

**Blocked by:** None (can start immediately).

**Status:** done

- [x] Add an Inspector entry point and side panel using the existing panel pattern, leaving the viewer visible.
- [x] List the nine Stages in order and show the selected Stage's purpose, Algorithm, input/output roles, status, available timing, and meaningful available statistics with units.
- [x] Combine static explanations with existing Scene detail Stage Runs and Manifests; distinguish descriptions from observed execution facts.
- [x] Handle absent fields as unavailable rather than zero; derive durations only from timestamps that support them. Do not expose nonexistent execution parameters or label a mere update as independently measured runtime.
- [x] Explain that the disabled attributes Stage performs no VLM enrichment. Do not fabricate statistics or attributes.
- [x] Use published metadata with no new Target calls, intermediate RGB/depth/mask previews, file access expansion, or reprocessing controls.
- [x] Verify ordered Stage selection, populated/missing metadata, timing honesty, and Target-off behavior through SceneApi/MSW; confirm the panel remains usable next to the viewer in a desktop browser.
- [x] Keep Object selection, camera controls and manual measurement usable when opening/closing the panel. Use English labels and update the frontend architecture explanation and domain terminology if needed.

### Demo

Disable Target-dependent search, open a completed Scene, and inspect reconstruction, attributes and graph Stages. Show useful counts/timing where available and explicit unavailable values otherwise.
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
