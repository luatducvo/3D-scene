# 03: Search reranks candidates against their Object Descriptions

**What to build:** Search ranks Objects by how well their Object Description answers the query. The query embedding gives the top-K Objects by cosine similarity (K from configuration, default 20). Those Objects plus every label match are reranked on the Target. A Search Hit's score is the reranker relevance (0..1) plus 1 for a label match. The existing margin cut and hit limit apply to these scores, and nothing outside the candidates is returned. Run this end to end with `embed.fake`, which gives deterministic rerank scores. See `../spec.md`, "Target" and "Search".

**Blocked by:** 02

**Status:** ready-for-agent

- [x] The Target workspace offers `rerank(query, documents) -> list[float]` on both the in-process and the HTTP adapter, through scene-compute's invoke route, as `embed_text` does
- [x] A scripted rerank failure carries the Algorithm's own code on both adapters
- [x] `embed.fake` gives deterministic rerank scores
- [x] Search returns only reranked candidates, label matches rank first with the +1 bonus, and margin and limit apply to the reranked scores
- [x] An empty query returns no Search Hits; an unavailable Target is still `COMPUTE_UNAVAILABLE`
- [x] The top-K size is configurable, with a default of 20
- [x] The Search Hit model keeps its shape, and its raw score carries the reranker relevance
- [x] OpenAPI is regenerated; if it changed, `npm run api:sync` is run and the frontend checks pass
- [x] `uv run main.py lint` and `uv run main.py test` pass
