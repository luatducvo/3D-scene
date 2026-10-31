# 06: Real query embedding and reranking; MetaCLIP removed

**What to build:** Search on a real Target uses `embed.mg3d_doc` end to end. Its `embed_text` embeds queries with BAAI/bge-m3, and its `rerank` scores (query, Object Description) pairs with BAAI/bge-reranker-v2-m3, returning sigmoid relevance in 0..1. The real pipeline config selects `embed.mg3d_doc` with its model ids as params, and `embed.metaclip2` is deleted. See `../spec.md` and ADR 0001.

**Blocked by:** 03, 05

**Status:** ready-for-agent

- [x] `embed.mg3d_doc` offers `embed_text` (bge-m3, 1024 dimensions) and `rerank` (bge-reranker-v2-m3, sigmoid 0..1)
- [x] The real pipeline config uses `embed.mg3d_doc`, and nothing refers to `embed.metaclip2` or MetaCLIP any more
- [x] `download_weights` fetches the VLM, embedder and reranker weights
- [ ] `uv run main.py lint` and `uv run main.py test` pass; checking real models on a GPU host is a manual step, and its result is reported
