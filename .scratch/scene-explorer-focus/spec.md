# Focused English Scene explorer

**Status:** ready-for-agent
**Date:** 2026-10-18

## Problem Statement

After processing a Scene, users need a focused way to understand the reconstructed room, identify individual Objects, locate Objects with English descriptions, ask grounded questions, and measure geometry. The current explorer highlights every search match with one color, does not offer distinct instance colors, restores persistent conversations, and supports two UI languages. It also provides little explanation of how the pipeline produced the Scene.

These behaviors distract from the intended core experience. A ranking score that includes a label-match bonus cannot honestly serve as a semantic heatmap value. Persistent conversations conflict with the decision that every question should stand alone. Users also need an Inspector that explains the pipeline without depending on large intermediate artifacts on a running compute Target.

## Solution

Concentrate the post-processing experience on five feature groups:

1. Direct Object interaction: hover, select, dimensions, and camera focus.
2. Original and Instances appearances, with stable distinct colors for individual Objects.
3. English open-vocabulary search with a per-query Object Heatmap, plus independent English question answering that highlights referenced Objects.
4. Manual two-point measurement in meters.
5. A Pipeline Inspector in a panel beside the viewer, explaining Stages and available execution facts.

Original is the default appearance. Search and QA temporarily override that appearance through one active result visualization; Clear restores the selected base appearance. The application uses English only. Chat displays only the latest exchange, does not retrieve history, and does not persist new exchanges. Existing stored conversations remain untouched.

The scope is a simplification of the post-processing experience. Existing capture, processing, Scene lifecycle controls, and basic 3D navigation remain available; this feature does not redesign them.

## User Stories

1. As a user, I want a processed Scene to open in a 3D explorer, so that I can examine the room immediately.
2. As a user, I want to orbit, zoom, and pan, so that I can inspect the Scene from useful viewpoints.
3. As a user, I want Home to frame the whole room, so that I can recover after navigating away.
4. As a user, I want the existing Point Cloud and Mesh views to remain usable when their assets exist, so that I can inspect either representation.
5. As a user, I want hovering an Object to show its name, so that I can identify what the system recognized.
6. As a user, I want hovering to provide visible feedback, so that I know which Object a click will select.
7. As a user, I want clicking an Object to select and highlight it, so that I can distinguish it from its surroundings.
8. As a user, I want selection to show the Object's dimensions in meters, so that I can understand its spatial extent.
9. As a user, I want selection and the focus action to frame the Object, so that I can inspect it closely.
10. As a user, I want Original to be the default appearance, so that I first see the reconstructed colors.
11. As a user, I want an Instances appearance, so that I can distinguish separate Objects visually.
12. As a user, I want separate Objects with the same label to have distinct colors, so that individual chairs or cabinets do not blend together.
13. As a user, I want each Object's instance color to stay stable when I revisit the same Scene, so that I can recognize it consistently.
14. As a user, I want a handle to retain its own color where it overlaps a cabinet, so that small Objects remain visible and selectable.
15. As a user, I want geometry without Object Membership to keep its original color, so that the rest of the room remains understandable.
16. As a user, I want to search using a free-text English description, so that I can find Objects without choosing from a fixed label menu.
17. As a user, I want the current search ranking behavior to remain useful, so that clear label matches remain easy to find.
18. As a user, I want search results colored by relative semantic similarity, so that I can see which returned Objects better match my query.
19. As a user, I want the strongest returned similarity to use the hottest color and the weakest the coolest, so that the heatmap is easy to interpret within one query.
20. As a user, I want the legend to explain per-query normalization, so that I do not mistake colors for absolute confidence or compare them across queries.
21. As a user, I want one-result and equal-score searches to show a single hot level with an explanation, so that the visualization remains meaningful without a score range.
22. As a user, I want an empty search to show No results and restore the base appearance, so that I do not mistake an old highlight for a new match.
23. As a user, I want the camera to frame matching Objects, so that I can locate them in the room.
24. As a user, I want search errors and unavailable compute to be visible, so that I understand why the system could not find a result.
25. As a user, I want to ask a standalone question in English, so that I can understand the Scene without navigating technical data.
26. As a user, I want to ask where an Object is and how many matching Objects exist, so that I can locate and count them.
27. As a user, I want to ask about Object sizes, distances, spatial Relations, and relative directions, so that I can understand the layout.
28. As a user, I want to ask about available floor area, ceiling height, and counts by label, so that I can understand the room as a whole.
29. As a user, I want numerical answers grounded in tools, so that the assistant does not invent measurements.
30. As a user, I want answers in English and visible tool/answer progress, so that I can follow the response.
31. As a user, I want referenced Objects highlighted and framed after an answer, so that I can check the answer against the Scene.
32. As a user, I want each question evaluated independently, so that an earlier exchange cannot silently change its meaning.
33. As a user, I want only the latest question and answer displayed, so that the panel remains focused.
34. As a user, I want the completed answer to remain visible without retrieving stored messages, so that removing history does not make answers disappear.
35. As a user, I want reopening a Scene to start with an empty question panel, so that there is no conversation review.
36. As a user, I want the latest search or QA result to replace the previous result visualization, so that I see only one result context at a time.
37. As a user, I want Clear to restore my chosen Original or Instances appearance, so that I can return to exploring the room.
38. As a user, I want hover and selection to remain distinguishable over search and QA colors, so that Object interaction remains usable.
39. As a user, I want to select two points on visible geometry and see their straight-line distance in meters, so that I can measure manually.
40. As a user, I want to measure again or exit measuring, so that I can inspect multiple distances without getting stuck in the tool.
41. As a user, I want an Inspector button beside the viewer, so that I can understand the processing pipeline without leaving the Scene.
42. As a user, I want an ordered list of Stages, so that I can understand how the result was produced.
43. As a user, I want each selected Stage to explain its purpose, Algorithm, and inputs and outputs, so that I understand what it contributes.
44. As a user, I want available status, timing, counts, and statistics for the Stage, so that I can distinguish explanation from actual execution facts.
45. As a user, I want missing execution data identified as unavailable, so that I do not mistake absent data for zero or a measured value.
46. As a user, I want the Inspector to work from published Scene metadata when the compute Target is off, so that I can still understand a completed Scene.
47. As a user, I want English-only navigation and controls with no language switch, so that the interface is consistent.
48. As a user, I want a clear statement that search and questions are supported in English, so that I know how to phrase requests.
49. As a user, I want older Scenes with missing or invalid membership to explain their visualization limitation, so that I understand why Object colors or picking are unavailable.

## Implementation Decisions

### Domain and architecture

- Preserve the existing Instance-to-Object identity: each Instance becomes one Object with the same ID. Do not invent a second identity for instance colors.
- Reuse Object Membership on the published geometry for instance colors, heatmaps, hover, selection, and QA highlights. Do not draw Object boxes or add detached point overlays.
- Reuse the existing viewer layer, camera command, SceneApi, and viewer state boundaries. Separate the selected base appearance from the active search/QA result so clearing results restores the intended appearance.
- Respect the existing pipeline and Publication architecture. All Stages remain on the configured Target; published geometry and membership keep their versioned asset URLs. Intermediate Frames and other visual artifacts remain private to the Target.
- Keep the attributes Stage disabled as currently configured. Do not promise color, material, state, or translated labels derived from a VLM.

### Instance appearance and interaction

- Offer Original and Instances independently of the existing Point Cloud/Mesh geometry choice. Apply the agreed appearance behavior to both representations when membership matches their geometry.
- Assign stable distinct colors within a Scene based on Object identity. Reloading the same publication or changing result overlays must not reshuffle colors.
- Resolve shared geometry using existing picking ownership: the Object with fewer membership elements wins. Keep coloring and picking consistent; use deterministic ownership when membership sizes tie.
- Retain original colors for unassigned geometry. Preserve original color data so changing modes and clearing results do not accumulate tints.
- Give hover and selection visible feedback distinct from result colors. Removing hover or selection restores the underlying active result or base appearance.
- Missing, failed, or mismatched membership must not produce fabricated Object colors or incorrect picking. Preserve geometry display and the existing reprocessing/error notice.

### Search score contract and heatmap

- Keep the existing search endpoint and result selection/ranking policy. Retain the existing score field for its ranking meaning.
- Extend each search hit with a finite numeric raw_similarity field containing the unbonused cosine similarity used for that Object. The OpenAPI contract and generated client must expose the distinction between ranking score and raw similarity.
- Label-match bonuses affect ranking and result inclusion only. Heatmap input is raw_similarity, never the boosted ranking score.
- Normalize over the returned results for the active query: subtract the minimum raw similarity and divide by the difference between the maximum and minimum. The lowest maps to the cool end and the highest to the hot end.
- A single returned result, or equal similarities across all returned results, uses the hot end for all results with a single-score-level legend. Avoid division by zero and non-finite colors.
- Label the legend as relative similarity for this query. Do not show probability percentages, recognition confidence, or imply comparability between different queries. A cool returned Object is still a match, not an absence of membership.
- Color Objects uniformly at Object level. This feature does not add semantic values per point or vertex.
- An empty result clears the previous result visualization, returns to the selected base appearance, and shows No results. Error responses remain errors, not empty matches.

### Active visualization and asynchronous behavior

- Allow one active result source: search or QA. A newer successful search result or completed QA answer replaces the previous result visualization; a QA answer with no referenced Objects removes the previous result overlay.
- Clear removes the active result visualization and restores the selected base appearance. Clearing search input must remove its heatmap.
- Search and chat results override instance colors while active. Hover and selection provide temporary feedback on top without destroying result data.
- Prevent stale asynchronous search or QA responses from repainting a newer result, restoring a cleared result, or affecting a different Scene. Existing automatic search updates must not reclaim the viewer merely because cached search data is present after a QA answer.
- Preserve camera focus for matching/referenced Objects and Home navigation. Do not use camera movement as a substitute for applying correct geometry colors.

### Independent English question answering

- Keep the existing question API and SSE protocol, tool names, camera input, numerical grounding, and current tool capabilities.
- Force the agent's response language to English, instead of following the question's language. Existing label and embedding storage do not need destructive conversion.
- Do not load or pass previous conversation messages to the LLM. The current question, current camera, and Scene tools remain available.
- Stop writing new question/answer exchanges to persistent storage. Do not delete, migrate away, or overwrite existing stored messages as part of this feature.
- The explorer must not request or render stored message history. Hold the latest submitted question, answer, and status in transient UI state and retain the completed answer directly.
- Submitting a new question replaces the previous displayed exchange. Reopening a Scene starts without an exchange; prior session content is not restored.
- Preserve existing request cancellation and error reporting while preventing cancelled or superseded responses from changing the current UI.
- QA final events highlight referenced Object IDs with no invented similarity values. Only actual search results have a similarity heatmap.

### English-only application

- Make English the only rendered UI language and default entry experience, including navigation, capture/processing screens, explorer controls, validation, and errors owned by the UI. Remove the language switch and active Vietnamese rendering.
- Existing locale URLs must resolve to an English experience or redirect to it; they must not expose a second rendered language or break existing navigation.
- State that search and question inputs are supported in English. Do not add automatic language detection, rejection, or translation of non-English input.
- Keep the existing multilingual embedding model; an English support policy does not require retraining or replacing it.

### Manual measurement

- Preserve two-point picking on visible geometry, the straight-line distance in meters, the segment/endpoints, measure-again, and exit controls.
- Measuring and Object selection must remain mutually usable through the existing tool-mode behavior. Do not interpret measurement clicks as unintended Object selections.

### Pipeline Inspector

- Add an Inspector entry point that opens a side panel while leaving the 3D viewer visible. Follow the existing panel interaction pattern rather than introducing a new page.
- List the nine existing Stages in pipeline order. Selecting a Stage shows its purpose, Algorithm, input/output roles, execution status, available timing, and meaningful available statistics.
- Read execution facts from existing Stage Runs and Manifests in Scene detail. A frontend catalog may supply stable explanations and input/output descriptions; clearly distinguish these descriptions from measured values.
- Derive elapsed timing only when the available start and completion/update timestamps support it; otherwise show unavailable. Do not label an update timestamp as a separately measured runtime or expose execution parameters that are not in the API.
- Present available summaries with units and labels instead of requiring users to understand raw JSON. Missing values are unavailable, not zero.
- Explain that disabled attributes performs no VLM enrichment. Do not fabricate statistics, artifacts, or preview links for it.
- Inspector metadata must remain usable with the Target off. Do not add Target calls or broaden the publication/file access contract to fetch intermediate previews.

### Contracts, data, and documentation

- No destructive data migration or deletion of old conversations is authorized. No new persistence is needed for appearances, active results, latest QA exchange, or Inspector selection.
- Export the backend OpenAPI contract and regenerate frontend API types after changing search models. Keep mock HTTP/SSE responses aligned with the real contract, including raw_similarity.
- Update the frontend and API architecture documentation with the final behavior, English-only policy, independent QA, and score semantics. Update the parent product spec where these decisions supersede multilingual UI and persistent chat stories; preserve unaffected scope and the accepted ADRs.
- Keep the existing domain definitions of Object Heatmap and Pipeline Inspector aligned with this spec. These reversible scope choices do not require a new ADR by themselves.

## Testing Decisions

The user confirmed the existing backend REST API + SSE seam and frontend SceneApi/MSW seam on 2026-10-18. Prefer observable behavior through those seams. Do not introduce a new service boundary or tests that mirror private helper implementations.

### Backend REST API and SSE

Use real store/publication behavior with fake Algorithms and ScriptedLLM; automated tests do not need a GPU or live LLM. Existing API tests for search ranking, grounded QA streams, lifecycle rules, unavailable compute, and published Scene data are the prior art.

- Verify every search hit exposes ranking score and raw_similarity with their separate meanings. Include a label-match bonus example where ranked order differs from raw similarity order.
- Preserve current result filtering/ranking and the distinction between search results and QA counting/search behavior.
- Verify independent consecutive questions: the second LLM request contains no prior exchange, including previously stored messages for the Scene.
- Verify new completed questions create no persisted messages, while pre-existing records remain unchanged.
- Preserve final Object IDs, tool and answer events, numerical grounding, English response instructions, request errors, and the not-ready/LLM-unconfigured rules.
- Verify Scene metadata still supplies the available Stage execution facts without fetching Target-private visual artifacts.

### Frontend behavior through SceneApi and MSW

Use the existing HTTP/SSE mock transport and published synthetic geometry/membership fixtures. Explorer interaction, API streaming, Object details, highlight/picking, and viewer-rule tests provide the prior art.

- Verify Original defaults, switching to Instances, stable colors, distinct same-label Objects, unassigned original colors, and consistency with overlap ownership.
- Verify ordered, equal-score, and single-result heatmaps; normalization uses raw similarity rather than the bonus score; show an honest legend and empty/error states.
- Verify Original/Instances restoration after Clear, single active search/QA visualization, hover/selection restoration, and protection against stale or cancelled results.
- Verify the latest completed answer stays visible without a history fetch; a new question replaces it; reopening starts empty; no history UI is rendered.
- Verify referenced Objects are highlighted, camera focus remains available, and QA without Object IDs leaves no stale result overlay.
- Verify English-only controls and entry navigation, the absence of a language switch, and no input-language rejection policy.
- Verify Inspector Stage order, explanations, real metadata, missing-data states, and operation when Target-dependent search is unavailable.
- Preserve manual measurement and existing Object details behavior.

Add focused pure tests only where numerical normalization, overlap ownership, or layered color restoration would be hard to validate reliably through the higher seam. Assertions should express visible outcomes rather than internal state layout.

### Visual verification and completion

- Run appropriate backend lint/tests and frontend typecheck/tests/build, plus contract regeneration checks for the API change. Document actual results separately from this design spec.
- Inspect both Point Cloud and Mesh at desktop width using deterministic mock Scenes. Check instance distinguishability, heatmap legend, picking, hover/selection, Clear, measurement, and the Inspector layout.
- Verify actual WebGL rendering and GPU picking in a browser: pure tests or a mocked canvas alone cannot establish visual correctness.
- Fake-pipeline/browser verification does not establish reconstruction quality or live compute correctness. Any required live checks are recorded separately in the existing GPU integration log.

### Acceptance checklist

- [ ] Object hover, click selection, dimensions, focus, Home, and basic navigation remain usable.
- [ ] Original/Instances works on available geometry; identity-based colors and overlapping ownership are consistent.
- [ ] Search exposes raw cosine separately, paints the agreed per-query heatmap, and handles equal/empty/error results honestly.
- [ ] Search, QA, selection, and hover obey the single-result visualization and restoration rules.
- [ ] QA is English, grounded, independent, latest-exchange-only, and does not read previous context or persist new messages.
- [ ] Existing stored messages are preserved and are not shown by the explorer.
- [ ] All rendered UI is English; the language switch is removed without breaking navigation.
- [ ] Manual two-point measurement remains functional.
- [ ] Inspector explains the nine Stages using real available metadata without needing intermediate artifact downloads.
- [ ] Missing/mismatched membership and unavailable metadata remain understandable and safe to view.
- [ ] API contracts, mocks, relevant architecture/product docs, automated checks, and desktop browser verification are complete.

## Out of Scope

- Object editing, relabeling, moving, deleting, merging, or splitting.
- Point-level semantic embeddings, within-Object heatmaps, confidence probabilities, and heatmap comparison across queries.
- Conversation review, persisted new exchanges, multi-turn context, or deletion of old stored messages.
- Vietnamese UI support, non-English input validation, automatic translation, or changing the embedding model solely for language policy.
- Inspector image/depth/mask/crop previews, fetching intermediate Target artifacts, interactive pipeline reconfiguration, or rerunning individual Stages.
- Re-enabling VLM attributes, evidence photo UI, suggested questions, a separate Object list, or drawn Object boxes.
- A separate Scene Graph visualization, export/download UI, sharing, authentication, mobile redesign, new providers, or pipeline Algorithm changes.
- Reworking existing capture, processing, Scene deletion, or whole-pipeline reprocessing beyond keeping them usable with English UI.

## Further Notes

- This specification synthesizes the user's fourteen answered design choices and their confirmed testing seams. Publishing it is a specification task, not authorization to claim application implementation is complete.
- This scope supersedes the parent spec's conflicting language/history interface requirements for this work. Existing accepted decisions about disabled VLM attributes, whole-pipeline Target execution, immutable versioned Publication, private Frame images, and membership-based rendering continue to apply.
- Viewing published geometry and Inspector metadata does not need a running GPU Target. Free-text search and QA tools that embed query text still need the Target; QA also needs a configured LLM.
- Query-normalized heatmaps can make a weak best result appear hot. The legend must communicate relative ranking and not imply that the best returned Object is a confident recognition.
- Keep the feature deliverable focused on the five agreed groups. Ordinary implementation details may be resolved within these acceptance criteria without reopening the design interview.
