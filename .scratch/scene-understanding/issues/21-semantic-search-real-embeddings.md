# 21: Multilingual semantic search with real embeddings

**What to build:** Meta CLIP 2 replaces the fake embedder for both Object embeddings (score-weighted mean of crop embeddings) and query-time text embedding via the compute backend, so search works by meaning in English or Vietnamese.

**Blocked by:** 20, 11

**Status:** needs-live-check — adapter done; MetaCLIP 2 on Modal and dimension check against real weights not run; switch query_embedding in compute.yaml

- [ ] Searching "something to sit on" or "cái ghế" ranks chairs/sofas in my room near the top.
- [ ] The embedding dimension matches the database vector column (migration adjusted if not).
- [ ] Query embedding uses the configured Target and stays within the contract's synchronous time limit.
