# Focused Scene explorer scope

Date: 2026-10-18
Status: Design decisions synthesized into the local issue tracker specification. Testing seams confirmed on 2026-10-18. All five implementation tickets are complete; verification is recorded in the feature completion report.

## Goal

Focus the post-processing experience on Object interaction, distinct instance colors, English open-vocabulary search and independent question answering, manual measurement, and a pipeline Inspector.

## 1. Object interaction and instance colors

- Hover an Object to show its label and hover feedback.
- Click an Object to select it, highlight it, show its dimensions in meters, and focus the camera.
- Provide Original and Instances appearance modes, with Original as the default.
- Instances assigns a stable distinct color to each Object ID, including different Objects with the same label.
- An Instance becomes exactly one Object with the same identity; appearance, picking, search, and answers use that identity.
- For overlapping Object Membership, prefer the smaller Object, consistent with current picking ownership. Geometry without an Object retains its original color.
- Hover and selection use distinct feedback colors over the active appearance.

## 2. English open-vocabulary search and heatmap

- Accept free-text English Object queries.
- Keep label-match bonuses for search ranking, but expose raw cosine similarity separately for heatmap rendering.
- Normalize raw cosine similarity across the returned Objects for each query: t = (similarity - min) / (max - min).
- The strongest result is hottest and the weakest result coolest. The legend explains that this is relative similarity within this query, not recognition confidence or a probability. Colors are not comparable across queries.
- A single result or equal scores use the same hot color, with a legend indicating a single score level.
- An empty result restores the selected base appearance and displays No results.
- The heatmap colors each returned Object uniformly through Object Membership; it does not imply different semantic scores within an Object.

## 3. Independent question answering

- Answer in English and highlight the Object IDs referenced in the answer, with camera focus.
- Retain existing grounded QA tools for finding and counting Objects, Object size, distances, spatial Relations, relative directions, and available room information.
- Each question is independent: never pass previous questions or answers as LLM context.
- Display only the latest question and answer. Do not fetch old conversations or persist new exchanges.
- Leave existing stored conversations untouched; removing conversation review does not authorize deleting old data.
- Chat highlights referenced Objects without assigning invented relevance scores to them.

## 4. Shared result visualization

- Only one result visualization is active: a new search result or new chat answer replaces the previous visualization.
- Search heatmaps and chat highlights temporarily override Original/Instances colors.
- Provide Clear to remove the active visualization and restore the selected base appearance.

## 5. Manual measurement

- Keep picking two points on displayed geometry and showing their straight-line distance in meters.
- Keep measure-again and exit-measure controls.

## 6. Pipeline Inspector

- An Inspector button opens a panel beside the viewer.
- List the pipeline Stages; selecting a Stage shows its purpose, Algorithm, inputs and outputs, status, timing, and available statistics.
- Use existing Stage Run and Manifest data. Describe input/output roles even when their files are not published.
- Do not present missing statistics or unavailable timing as measured values.
- Intermediate RGB/depth/mask previews are outside this version; their artifacts remain on the compute Target.

## Language policy

- UI, Object search support, and QA answers are English only; remove the language switch.
- Clearly state that queries are supported in English.
- Do not introduce language detection or rejection for other-language input.
- English-only does not require replacing the multilingual embedding model.

## Existing implementation constraints

- Current search ranking scores include a label-match bonus and cannot directly represent raw semantic similarity.
- QA final events contain Object IDs without similarity scores.
- Current chat display depends on persisted messages, and the API currently loads history as LLM context. Both paths need changing for independent questions and latest-exchange-only display.
- Stage Runs already expose Algorithm, status, Manifest, progress, errors, and timestamps; execution parameters are not exposed there.
- Intermediate visual artifacts are not publicly served. The lightweight Inspector must work with published metadata.

## Documentation and delivery

- Canonical domain terms live in CONTEXT.md. Record the agreed meaning of Object Heatmap and Pipeline Inspector there.
- No ADR is needed for these reversible UI scope choices at this point.
- This document records the design, not completed implementation or runtime verification.

## Published specification

The implementation specification is [Focused English Scene explorer](../../.scratch/scene-explorer-focus/spec.md), with status ready-for-agent. It includes the fourteen selected design decisions and the confirmed testing seams.
