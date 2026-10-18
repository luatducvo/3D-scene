# Search and QA review — conversation handoff (2026-10-18)

Context saved to continue this work on another machine. Nothing in the code was changed in this
conversation; everything below is findings, proposals and open decisions.

## How we got here

1. Question: for open-vocabulary queries, use Search (`GET /scenes/{id}/search`) or QA
   (`POST /scenes/{id}/queries`)? Answer: both embed the query on the Target and compare with Object
   embeddings (MetaCLIP 2, 1024-d). Search is for locating/highlighting; QA is for questions that
   need reasoning on top (count, distance, relations, direction). They rank differently:
   `rank_search_hits` (margin 0.05 from best, max 10, label matches first) vs `rank_tool_hits`
   (every Object scoring above `TOOL_MIN_SCORE = 0.15`, uncut). See
   [api.md#search](../architecture/api.md#search).
2. Started a grilling + domain-modeling session on that split (round 1 below, unanswered).
3. Tested both features against Scene **test3** and wrote redesign proposals.

## Test setup

- The built-in browser is not available in the VS Code extension, so testing went through the same
  API the frontend uses: `http://localhost:8000/api/v1`.
- Scene test3: id `2c3e8d08-c3dc-40fc-a5aa-b817658b9837`, status ready, 176 Frames, 131 Objects,
  54 distinct labels, 8603 Relations. Algorithms: `recon.da3`, `align.geocalib_ransac`,
  `segment.sam3` (Vocabulary 353), `lift.maskclustering`, `embed.metaclip2`, `attributes.none`,
  `graph.geometric`.
- Every Object has `label_vi = null` and `attributes = {}` (because `attributes.none`).
  `ceiling_height` is null.

## Findings — Search (0.6–1.4 s per query)

| Query | Result |
|---|---|
| `chair`, `book`, `fan`, `light switch`, `headphones` | Correct on top (label match), followed by unrelated hits |
| `door` | 29 hits: substring match pulls in `door handle`, `door frame`; label matches bypass the 10-hit cap |
| `ghế` | office chair, recliner, then headphones, cabinet; `chair` missing |
| `máy tính` | Top hit `window` |
| `something to sit on`, `place to sleep`, `where can I store clothes` | Right Object at rank 4–9 among noise |
| `red object`, `đồ màu đỏ` | Random (no attributes) |
| `refrigerator`, `tủ lạnh`, `toilet` (absent) | Still 10 hits; no "not found" state |

Text-to-image cosines for every query sit in **0.16–0.29**, so raw similarity barely separates
right from wrong.

## Findings — QA (6–19 s per question)

| Question | Answer | Objects highlighted |
|---|---|---|
| Is there a refrigerator? | "No" (correct) | **101** |
| How many doors? | "7" | **116** |
| Có bao nhiêu cái ghế? | 2, or 3 with the recliner (good) | 2 |
| Cái gì ở bên trái cái tủ quần áo? | Correct, but 23 tool calls, 19 s | 3 |
| How far is the office chair from the desk? | 0.43 m center-to-center | 2 |
| How big is the room? | "No data" | 0 |
| What color is the backpack? | "No color data" | 3 |

## Root causes

1. **Highlight fallback bug** —
   [qa.py:359-361](../../backend/services/scene-api/src/scene_api/qa.py#L359-L361): when the LLM's
   `final_answer` has empty `object_ids`, the agent falls back to every Object any tool touched.
2. **`count_objects` is meaningless** — `TOOL_MIN_SCORE = 0.15`
   ([main.py:40](../../backend/services/scene-api/src/scene_api/main.py#L40)) is below the cosine
   floor, so it counts ~120 Objects for any query. The LLM works around it with `get_room_info`.
3. **No `label_vi`, no attributes** — Vietnamese relies only on weak embeddings; color questions
   are impossible.
4. **`floor_area` is never computed** by the real pipeline (only `fake.py` sets it); the
   `get_room_info` tool description still promises it.
5. **Two rankings** for one concept, so Search says 29 "door" while QA says 7.

## Proposals

P0 — bug fixes:

- **D1** Empty `object_ids` means highlight nothing; drop the `tools.mentioned` fallback; accept only
  ids the tools actually returned.
- **D2** Compute floor area (and ceiling height) in the graph Stage, or omit them from the tool
  output/description when null.

P1 — one Search core shared by Search and QA:

- **D3** Two-tier ranking: (a) label tier — embed every distinct label (or the Vocabulary) with the
  multilingual text encoder and match the query text-to-text (`ghế` → chair, office chair,
  recliner); (b) image tier — use Object image embeddings only to re-rank within chosen labels and
  for descriptions no label matches. Enables a real "not found". Likely deserves an ADR.
- **D4** Replace substring label matching with head-noun matching (`door` matches `closet door`, not
  `door handle`).
- **D5** Return hits grouped by label (`{label, count, objects}`); `count_objects` counts groups
  instead of thresholding at 0.15.
- **D6** Static Vietnamese translation of the Vocabulary (353 lines, generated once, committed) to
  fill `label_vi` without enabling the attributes Stage.
- **D7** Server-side LRU cache of query embeddings.

P2 — QA:

- **D8** Slimmer `get_relations`: filter by predicate, sort by distance, cap ~10, include labels;
  maybe an `objects_around(object_id, direction)` tool. Unverified hypothesis: `near` dominates the
  8603 Relations.
- **D9** SSE `tool` events carry a summary ("Search 'ghế' → 3 Objects").
- **D10** Stream real tokens, or drop the single-chunk `delta` event.

P3 — UX:

- **D11** Search shows a grouped, clickable result list and an explicit "not found"; question-like
  input in the search box offers "Ask this".

## Open decisions (recommendation in brackets)

- **C1** Keep two inputs (Search and chat) or merge into one with two modes? [Keep two, add D11]
- **C2** Adopt D3's two-tier ranking? [Yes, with an ADR]
- **C3** Enable the attributes Stage (VLM cost, against ADR-0004) or state "no color support"?
  [Not now; do D6 first, then re-measure]
- **C4** Order: D1–D2, then D3–D7, then QA and UX, each group as issues under `.scratch/`? [Yes]

Earlier grilling round, also unanswered:

- **Q1** Scope: terms only, terms + behavior, or something else? [Terms + behavior]
- **Q2** "Open vocabulary" vs the glossary's **Vocabulary**: keep **Vocabulary** as the set of
  concepts for naming Objects; add a separate term for free-text querying.
- **Q3** Canonical term for finding Objects from a free-text description: **Search** (_Avoid_:
  find, lookup, query).
- **Q4** Term for one ask in chat: **Question**, answered by an **Answer** grounded in Objects
  (_Avoid_: query, prompt, message). A Question may use Search as a step.

None of these terms is in [CONTEXT.md](../../CONTEXT.md) yet.

## Next step

Answer C1–C4 (and Q1–Q4), then write issues under `.scratch/search-qa-redesign/issues/` and update
CONTEXT.md with the resolved terms.
