# 04: Use English throughout the application

**What to build:** Users enter, navigate, capture, process, and explore Scenes using one consistent English interface without a language switch or a non-English input blocker.

**Blocked by:** None (can start immediately).

**Status:** done

- [x] English is the default and only rendered UI language for the library, capture/review, processing, Scene options, explorer, UI-owned validation/errors, and navigation.
- [x] Remove the language switch and active Vietnamese rendering. Existing locale URLs resolve to English or redirect without breaking Scene navigation.
- [x] State that Object search and question inputs are supported in English. Do not introduce detection, rejection or translation of other-language input.
- [x] Preserve existing multilingual embeddings and stored labels; no destructive data conversion, training, or Algorithm replacement.
- [x] Keep existing Scene creation, uploads, progress, deletion and whole-pipeline reprocessing usable; this is a language simplification rather than a redesign of those workflows.
- [x] Verify default and existing locale entry behavior, rendered controls, absent language switch, and absence of language rejection through current frontend seams and desktop browser navigation. Update affected mocks and copy consistently.
- [x] Update frontend/product documentation for the English-only policy. QA answer language is implemented and tested in 03, not a duplicate dependency of this ticket.

### Demo

Enter through the root and a previously Vietnamese URL, navigate library to capture and explorer, open options, and confirm English copy throughout with no language switch.
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
