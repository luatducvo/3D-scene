# 03: Ask independent English questions without conversation history

**What to build:** A user asks a standalone question, sees only the latest answer and its referenced Objects, and can ask another question without prior conversational context or new persisted messages.

**Blocked by:** 01: Explore Objects in Original and Instances appearances.

**Status:** done

- [x] Keep the current question API, SSE protocol, tools, current camera input, and numerical grounding; instruct the agent to answer in English.
- [x] Do not load/pass previous messages as LLM context or persist new exchanges. Preserve existing stored messages without destructive migrations.
- [x] Stop frontend history retrieval and rendering. Retain the completed latest question/answer directly in transient state; a new question replaces it, and reopening the Scene starts empty.
- [x] Retain visible tool/answer progress, cancellation and errors without allowing a cancelled or superseded response to change the current Scene or answer.
- [x] Highlight and focus referenced Object IDs through the single-active-result behavior; do not invent QA heatmap scores. A completed answer without referenced Objects clears the previous result overlay.
- [x] A new QA answer replaces the active search visualization; a later search can replace it. Clear restores Original/Instances without a cached search silently repainting.
- [x] Verify independent consecutive requests and preservation of old records at the REST/SSE seam with ScriptedLLM; retain grounding, tools and lifecycle error coverage. Verify latest-answer retention, no history fetch, reopen behavior, cancellation and result replacement through SceneApi/MSW.
- [x] Update API/frontend and parent product documentation where persistent history, multilingual answers, or multi-turn context conflict with this behavior.

### Demo

Seed old messages, ask two questions, show only the second exchange and its Object highlights, reopen the Scene, and verify that old data is unchanged and no new messages were stored.
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
