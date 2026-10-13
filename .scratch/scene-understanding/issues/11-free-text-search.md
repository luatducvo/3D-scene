# 11: Free-text search with highlight

**What to build:** A search bar over the viewer. The API embeds the query text through the configured query-embedding Target (via the compute backend's synchronous invoke), ranks Objects by vector similarity combined with label matching, and returns hits; the frontend highlights hits in 3D. Uses the fake embedder until real embeddings land.

**Blocked by:** 08

**Status:** done

- [ ] Typing an Object's label returns that Object first and highlights it in the viewer.
- [ ] The query-embedding Target comes from compute configuration; the API depends only on the `TextEmbedder` port.
- [ ] An empty or no-match query returns an empty list, not an error.
- [ ] API tests cover ranking with label match and vector similarity on fake data.
