# Ticket breakdown proposal: Focused English Scene explorer

Status: Approved by the user and published as five ready-for-agent issues on 2026-10-18. All five issues are implemented and verified; see the shared completion report.
Source: the Focused English Scene explorer specification.

## Approved dependency graph

- 01: No blockers.
- 02: Blocked by 01.
- 03: Blocked by 01.
- 04: No blockers.
- 05: No blockers.

01, 04, and 05 can start immediately. 02 and 03 are independent of each other once 01 is complete. Shared files may require coordination but are not blocking dependencies.

## 01: Explore Objects in Original and Instances appearances

**What it delivers:** A user can switch a processed Scene between reconstructed colors and stable colors for individual Objects, then hover, select, inspect dimensions, focus, navigate, and measure without losing the chosen appearance.

**Blocked by:** None (can start immediately).

### Acceptance scope

- Default to Original; provide Instances independently of Point Cloud/Mesh, with stable distinct colors for Object IDs, including Objects sharing a label.
- Render through published Object Membership on both geometry representations. For overlapping geometry use the existing smaller-membership ownership and deterministic ties; unassigned geometry retains its original color.
- Preserve hover labels, click selection, distinct hover/selection feedback, dimensions, camera focus, Home, orbit, zoom, and pan.
- Removing transient feedback restores the underlying appearance without accumulating color changes.
- Include the necessary prefactoring inside this user-visible slice: separate base appearance, selection/hover, and one active search/QA visualization. Provide Clear, retaining existing search/QA highlights while restoring the selected base appearance on clearing.
- Preserve two-point straight-line measurement, its meters display, measure-again and exit; measurement clicks do not select Objects accidentally.
- Missing, failed, or mismatched membership keeps the geometry visible with an honest notice and no fabricated Object colors or picking.
- Verify through existing SceneApi/MSW behavior and focused ownership/color-rule tests where necessary; visually inspect Point Cloud and Mesh in a desktop browser.
- Update relevant viewer architecture explanations with the delivered behavior. No API or persistence change is required for this slice.

### Demo

Open the synthetic Scene, switch between Original and Instances, select an overlapping small Object, use an existing result highlight, Clear, and measure a segment. The chosen base colors return correctly throughout.

## 02: Search Objects with a relative similarity heatmap

**What it delivers:** An English free-text query finds Objects, frames them, and paints their geometry with an honest per-query heatmap from the API's raw cosine values.

**Blocked by:** 01: Explore Objects in Original and Instances appearances.

### Acceptance scope

- Extend search hits end to end with raw_similarity while keeping the existing score and ranking/inclusion behavior. The ranking bonus never enters the heatmap normalization.
- Update the API schema export, generated frontend contract, HTTP client consumption, and mock search responses together.
- Normalize raw cosine over returned Objects per query, strongest hottest and weakest coolest; use one hot level for one result or equal scores and explain that case in the legend.
- Paint each returned Object uniformly through membership. The legend explains relative similarity within this query, not a probability or confidence, and not comparable across queries.
- Focus the camera on results. Distinguish empty responses from failures and unavailable compute; No results restores the selected base appearance.
- Search replaces the active QA visualization. Clear and clearing search input remove its heatmap; background updates or stale responses cannot reclaim the viewer after a newer result, Clear, or a Scene change.
- Preserve hover/selection feedback, both geometry views, and measurement over the heatmap, restoring its colors when feedback ends.
- Verify raw versus bonus scores and ranking at the backend REST seam; verify UI normalization, equal/single/empty/error cases, result replacement, and stale responses through SceneApi/MSW. Visually verify the real heatmap and legend.
- Update API/frontend documentation with score semantics, visualization behavior, and the compute Target requirement.

### Demo

Use a fixture whose highest label-boosted ranking score is not its highest raw similarity. Show the correct heatmap, compare another query, exercise equal and empty results, and Clear back to Instances.

## 03: Ask independent English questions without conversation history

**What it delivers:** A user asks a standalone question, sees only the latest answer and its referenced Objects, and can ask another question without prior conversational context or new persisted messages.

**Blocked by:** 01: Explore Objects in Original and Instances appearances.

### Acceptance scope

- Keep the current question API, SSE protocol, tools, current camera input, and numerical grounding; instruct the agent to answer in English.
- Do not load/pass previous messages as LLM context or persist new exchanges. Preserve existing stored messages without destructive migrations.
- Stop frontend history retrieval and rendering. Retain the completed latest question/answer directly in transient state; a new question replaces it, and reopening the Scene starts empty.
- Retain visible tool/answer progress, cancellation and errors without allowing a cancelled or superseded response to change the current Scene or answer.
- Highlight and focus referenced Object IDs through the single-active-result behavior; do not invent QA heatmap scores. A completed answer without referenced Objects clears the previous result overlay.
- A new QA answer replaces the active search visualization; a later search can replace it. Clear restores Original/Instances without a cached search silently repainting.
- Verify independent consecutive requests and preservation of old records at the REST/SSE seam with ScriptedLLM; retain grounding, tools and lifecycle error coverage. Verify latest-answer retention, no history fetch, reopen behavior, cancellation and result replacement through SceneApi/MSW.
- Update API/frontend and parent product documentation where persistent history, multilingual answers, or multi-turn context conflict with this behavior.

### Demo

Seed old messages, ask two questions, show only the second exchange and its Object highlights, reopen the Scene, and verify that old data is unchanged and no new messages were stored.

## 04: Use English throughout the application

**What it delivers:** Users enter, navigate, capture, process, and explore Scenes using one consistent English interface without a language switch or a non-English input blocker.

**Blocked by:** None (can start immediately).

### Acceptance scope

- English is the default and only rendered UI language for the library, capture/review, processing, Scene options, explorer, UI-owned validation/errors, and navigation.
- Remove the language switch and active Vietnamese rendering. Existing locale URLs resolve to English or redirect without breaking Scene navigation.
- State that Object search and question inputs are supported in English. Do not introduce detection, rejection or translation of other-language input.
- Preserve existing multilingual embeddings and stored labels; no destructive data conversion, training, or Algorithm replacement.
- Keep existing Scene creation, uploads, progress, deletion and whole-pipeline reprocessing usable; this is a language simplification rather than a redesign of those workflows.
- Verify default and existing locale entry behavior, rendered controls, absent language switch, and absence of language rejection through current frontend seams and desktop browser navigation. Update affected mocks and copy consistently.
- Update frontend/product documentation for the English-only policy. QA answer language is implemented and tested in 03, not a duplicate dependency of this ticket.

### Demo

Enter through the root and a previously Vietnamese URL, navigate library to capture and explorer, open options, and confirm English copy throughout with no language switch.

## 05: Inspect how the pipeline produced the Scene

**What it delivers:** A user opens an Inspector beside the viewer, selects a Stage, and understands its purpose and real available execution facts without running the compute Target.

**Blocked by:** None (can start immediately).

### Acceptance scope

- Add an Inspector entry point and side panel using the existing panel pattern, leaving the viewer visible.
- List the nine Stages in order and show the selected Stage's purpose, Algorithm, input/output roles, status, available timing, and meaningful available statistics with units.
- Combine static explanations with existing Scene detail Stage Runs and Manifests; distinguish descriptions from observed execution facts.
- Handle absent fields as unavailable rather than zero; derive durations only from timestamps that support them. Do not expose nonexistent execution parameters or label a mere update as independently measured runtime.
- Explain that the disabled attributes Stage performs no VLM enrichment. Do not fabricate statistics or attributes.
- Use published metadata with no new Target calls, intermediate RGB/depth/mask previews, file access expansion, or reprocessing controls.
- Verify ordered Stage selection, populated/missing metadata, timing honesty, and Target-off behavior through SceneApi/MSW; confirm the panel remains usable next to the viewer in a desktop browser.
- Keep Object selection, camera controls and manual measurement usable when opening/closing the panel. Use English labels and update the frontend architecture explanation and domain terminology if needed.

### Demo

Disable Target-dependent search, open a completed Scene, and inspect reconstruction, attributes and graph Stages. Show useful counts/timing where available and explicit unavailable values otherwise.

## Shared completion criteria

- Each published ticket is one separately numbered Markdown issue with ready-for-agent status and explicit blockers, using the tracker template.
- Each ticket owns its relevant tests, documentation, and browser verification; do not defer correctness to an unspecified final integration ticket.
- Use the agreed backend REST/SSE and frontend SceneApi/MSW seams; fake Algorithms and ScriptedLLM keep automated tests independent of GPU and live LLM services.
- Run checks appropriate to changed behavior; regenerate contracts for schema changes. Report actual local results separately from any live GPU checks.
- Preserve accepted ADRs about disabled VLM attributes, whole-pipeline Target execution, versioned Publication, private Frame images, and membership-based rendering.
- 01 contains the necessary color/result-state prefactoring alongside a demoable improvement. No standalone horizontal refactor or test-only ticket is needed.
- The user approved the ticket sizes and blocking edges. The five issues are published; the parent specification remains unchanged and all five issues are implemented and verified.

## Published issues

- [01: Explore Objects in Original and Instances appearances](issues/01-object-interaction-and-instance-colors.md)
- [02: Search Objects with a relative similarity heatmap](issues/02-open-vocabulary-search-heatmap.md)
- [03: Ask independent English questions without conversation history](issues/03-independent-english-questions.md)
- [04: Use English throughout the application](issues/04-english-only-application.md)
- [05: Inspect how the pipeline produced the Scene](issues/05-pipeline-inspector.md)

Completion: [validation report](validation.md), 2026-10-19.
