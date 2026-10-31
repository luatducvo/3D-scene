# MG3D-Doc: Object Descriptions for embedding and reranked Search

Status: ready-for-agent

See ADR 0001 (`docs/adr/0001-object-descriptions-replace-image-embeddings.md`) for why.

## Problem Statement

A user who searches a Scene with a natural query, especially one about where something is or what it is for ("the lamp on the desk", "something to sit on near the window", or a Vietnamese query such as "cái ghế cạnh giường"), often gets poor Search Hits. Today an Object's embedding is a MetaCLIP 2 image embedding of its Best View crops, and the query is embedded by MetaCLIP's text tower. That pairing matches short appearance phrases, but it knows nothing about an Object's use or its physical place in the Scene. Its text side also cuts input off at 77 tokens and was trained on short alt-text. Spatial and functional queries therefore rank the wrong Objects.

## Solution

Each Object gets an **Object Description**: three English sentences covering its visual appearance, its use, and its physical place in the Scene relative to gravity (size, height above the floor, what it rests on, its nearest neighbours, and whether it stands by a wall, in a corner or in the open). A VLM writes the Description from the Object's Best View crops, its label and geometric facts computed from the final boxes. A multilingual sentence model embeds the Description. When the user searches, the query is embedded with the same model, and the most similar Objects (plus every label match) are re-judged by a multilingual cross-encoder against their Descriptions. The user sees better-ranked Search Hits, Vietnamese queries work against English Descriptions, and spatial and functional queries find the right Objects.

## User Stories

1. As a user, I want to search for an Object by where it is ("the lamp on the desk"), so that I can find it without knowing its exact label.
2. As a user, I want to search for an Object by what it is used for ("somewhere to put my coffee"), so that I can find Objects that serve a purpose.
3. As a user, I want to search by appearance ("the white round thing"), so that visual details still find Objects.
4. As a Vietnamese-speaking user, I want to type my query in Vietnamese, so that I get the same Search Hits as an equivalent English query.
5. As a user, I want a label match to stay at or near the top of the Search Hits, so that searching "chair" still shows every chair first.
6. As a user, I want Search to return only Objects that were re-judged against my query, so that the Highlight and Object Heatmap show comparable scores.
7. As a user, I want an empty query to return no Search Hits, as it does today.
8. As a user, I want a query that matches nothing well to return few or no Search Hits, so that the Highlight is not filled with noise.
9. As a user, I want Search to report that compute is unavailable when the Target is down, as it does today, so that I know to retry later.
10. As a user, I want a Scene processed with this change to keep its Selection, Highlight, Object Heatmap and Measurement behaviour unchanged, so that only ranking quality differs.
11. As a user, I want a failed Job to keep the Scene's previous Publication, so that I can still search the old results.
12. As an operator, I want the embed Stage to run after the objects Stage, so that each Description uses the same boxes the viewer shows.
13. As an operator, I want the Stage Run list for a Job to show the Stages in the new order (ingest, recon, align, mesh, segment, lift, objects, embed).
14. As an operator, I want the embed Algorithm to be named `embed.mg3d_doc`, so that its name says which method it performs.
15. As an operator, I want the VLM, sentence model and reranker model ids and the geometric thresholds to be Algorithm params in the pipeline config, so that I can tune them without code changes.
16. As an operator, I want the top-K size for reranking to be configurable, with 20 as the default, so that I can trade latency for recall.
17. As an operator, I want a VLM answer that is not exactly the three expected sentences to be regenerated up to two times, and then fail the Stage with `INVALID_MODEL_OUTPUT`, so that malformed Descriptions never reach a Publication.
18. As an operator, I want every Object in a Scene to have exactly one Object Description, and the Stage to fail if any Object lacks one, so that no Object is silently unsearchable.
19. As an operator, I want the embed Stage's Manifest to name the models it used and the embedding dimension, so that I can tell which models made a Publication.
20. As an operator, I want the embed Stage to report progress as it describes and embeds Objects, so that I can watch a long Stage advance.
21. As an operator, I want the reranker to run on the Target like query embedding does, so that scene-api never loads a model.
22. As an operator, I want a rerank failure on the Target to surface with the Algorithm's own code on both the in-process and the HTTP Target, so that failures read the same everywhere.
23. As an operator, I want the Object Descriptions published with the Objects and stored per Object, so that Search can read them without the Target Workspace.
24. As an operator, I want a Publication that lacks Object Descriptions to be rejected as `RESULTS_INVALID`, so that results written by older code are never half-served.
25. As an operator, I want the embedding dimension to stay 1024, so that the `objects.embedding` column does not change.
26. As a developer, I want `embed.fake` to write deterministic Object Descriptions and give deterministic rerank scores, so that the whole Pipeline and Search are testable without a GPU.
27. As a developer, I want `embed.fake` to keep its `fail`, `fail_code`, `delay` and `progress_steps` params, so that failures and progress stay scriptable.
28. As a developer, I want the placement facts (support, neighbours, wall/corner, size and height) computed by plain code from boxes, so that I can test them on synthetic boxes.
29. As a developer, I want the VLM to be injectable into the Algorithm's Description step, so that I can test the JSON validation and retry rule without model weights.
30. As a developer, I want the OpenAPI contract regenerated, and the frontend types synced if it changes, so that both sides agree.
31. As a reader of the code, I want GLOSSARY terms (Object Description, Search, Search Hit) used consistently, so that the vocabulary matches the domain model.

## Implementation Decisions

**Pipeline**
- The Stage order becomes `ingest, recon, align, mesh, segment, lift, objects, embed`. The shared Stage list, each Stage's declared reads, and the three pipeline configs (real, fake, fake-gpu) change together.
- The objects Stage must not depend on the embed Stage's output. The embed Stage reads the objects Stage's output (boxes and labels), the instances output (Best View crops) and the mesh output (for the floor-plan footprint).

**Algorithm `embed.mg3d_doc`** (it replaces `embed.metaclip2`, which is deleted, and runs on the Target like every Stage)
- *Placement facts*, deterministic and computed from the Objects' boxes in the gravity-aligned frame (floor at z = 0). Every threshold is a param:
  - Size in metres, and height of the box bottom above the floor.
  - Support: Object A rests on Object B when A's bottom is within 5 cm of B's top and their horizontal footprints overlap by at least 50% of A's footprint. Otherwise A rests on the floor when its bottom is within 5 cm of z = 0. Otherwise A is mounted or hanging. When several Objects qualify, the one with the largest overlap wins.
  - Nearest neighbours: the 2 Objects whose boxes are closest.
  - Room position: by a wall when the box lies within 30 cm of the boundary of the mesh's horizontal footprint, in a corner when it lies near two boundary edges, otherwise in the open.
- *Description writing*: one Qwen3-VL-8B-Instruct call per Object, batched across Objects. Each call receives up to 3 Best View crops, the label and the placement facts, and answers JSON `{appearance, use, placement}`, each field one English sentence. An answer that is not valid JSON, misses a field, or has a field that is not a single non-empty sentence is regenerated up to 2 times. After that the Stage raises `INVALID_MODEL_OUTPUT` naming the Object. There is no template fallback.
- *Embedding*: the three sentences joined in the order appearance, use, placement are embedded with BAAI/bge-m3 (dense output only, L2-normalised, 1024 dimensions). The Algorithm checks the model's dimension against the database dimension, as today.
- *Outputs*: the embeddings file keeps its layout (`ids`, `vectors`). A Descriptions file beside it maps each Object id to its three sentences. Both are published. The Manifest records the VLM, embedder and reranker model ids, the dimension and both file names.
- *Optional capabilities* on the Algorithm, reached through the Target like the existing query embedding: `embed_text(texts)` returns bge-m3 vectors, and `rerank(query, documents)` returns one BAAI/bge-reranker-v2-m3 relevance score per document, passed through a sigmoid into 0..1.

**Target**
- The Target workspace interface gains `rerank(query, documents) -> list[float]` next to `embed_text`, on both the in-process and the HTTP adapter. scene-compute exposes it through the same invoke route it uses for `embed_text`, and a failure carries the Algorithm's own code.

**Publication and storage**
- Reading results requires the Descriptions file and checks that its ids match the Objects and the embeddings exactly. Any mismatch or missing file raises `RESULTS_INVALID`.
- Schema: `objects` gains a non-null text column `description` holding the joined three sentences. It is written at publish time together with the embedding.

**Search**
- Candidates: the top-K Objects by cosine similarity of the bge-m3 query embedding (K from configuration, default 20), plus every Object whose label matches the query.
- Every candidate is reranked on the Target with its Description. A Search Hit's score is the reranker relevance plus 1 for a label match. The existing margin cut and hit limit apply to the reranked scores, and nothing outside the candidates is returned.
- The Search Hit API model keeps its shape: its raw score field carries the reranker relevance instead of cosine similarity. The Object API model does not expose the Description (internal only), so the frontend contract changes only if regeneration shows a difference.

**Glossary and ADR**
- GLOSSARY already defines Object Description, the new Stage order and the new meaning of Search and Search Hit. ADR 0001 records the decision.

## Testing Decisions

- A good test checks behaviour you can observe at a seam (Stage Runs, published rows, Search Hits, raised error codes), not how it is done internally. Tests never need a GPU, model weights or a network service.
- **Seam 1: `create_app(..., target=...)` with the fake pipeline** (prior art: the publish-and-rerun test and the search tests in the API tests). Cover:
  - A Job's Stage Runs appear in the new order.
  - Every published Object has a non-empty description row.
  - Search returns only reranked candidates, label matches rank first with the +1 bonus, the margin and limit cut apply to reranked scores, Vietnamese and empty queries behave as specified, and an unavailable Target is still `COMPUTE_UNAVAILABLE`.
  - A failed reprocess keeps the previous Publication, Descriptions included.
- **Seam 2: `open_target_workspace(...)` over in-process and HTTP clients** (prior art: the target tests' query-embedding and failure-code tests). Cover: rerank returns one score per document, scores come from the configured embed Algorithm, and a scripted failure carries its code on both adapters.
- **Seam 3: Algorithm level, on small synthetic inputs** (prior art: the objects Stage tests). Cover:
  - Placement facts from hand-built boxes: an Object on a desk, on the floor and mounted; overlap below 50%; nearest neighbours; by a wall, in a corner and in the open against a synthetic footprint.
  - The Description step with an injected fake VLM: valid JSON is accepted; malformed JSON, a missing field or a multi-sentence field is retried, and a third failure raises `INVALID_MODEL_OUTPUT`.
- Publication reading (prior art: the results tests): a missing Descriptions file or mismatched ids raises `RESULTS_INVALID`.
- Done check: `uv run main.py lint`, `uv run main.py test`, regenerate OpenAPI and, if it changed, run `npm run api:sync` and the frontend checks.

## Out of Scope

- Showing the Object Description in the frontend or returning it from the Object API.
- Query expansion or rewriting, and parsing spatial queries into target/landmark filters.
- Keeping MetaCLIP 2 image embeddings in any form, or fusing image and text scores.
- Vietnamese or bilingual Object Descriptions.
- Mesh-contact or Object Membership based support detection (boxes only).
- Migrating existing Publications: Scenes processed by older code must be reprocessed, following the strict-read rule in the failures doc.
- Checks against real models or GPUs in the automated suite.

## Further Notes

- Including every label match among the rerank candidates keeps today's guarantee that a label match is always a Search Hit. This detail was not discussed explicitly; it follows from keeping the label bonus.
- Search now makes two Target calls (embed the query, then rerank) where it made one, so Search latency depends on the Target being warm.
- The GPU host image must provide Qwen3-VL-8B-Instruct, bge-m3 and bge-reranker-v2-m3 weights. Weight download follows the existing `download_weights` convention.
