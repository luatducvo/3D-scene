# 05: embed.mg3d_doc writes and embeds Object Descriptions

**What to build:** The real `embed.mg3d_doc` Algorithm, running on the Target, performs the embed Stage.

- For each Object it gives Qwen3-VL-8B-Instruct up to 3 Best View crops, the label and the placement facts (ticket 04), batched across Objects. The model answers JSON `{appearance, use, placement}`, one English sentence each.
- An invalid answer (bad JSON, a missing field, or a field that is not one non-empty sentence) is regenerated up to 2 times. After that the Stage raises `INVALID_MODEL_OUTPUT` naming the Object. There is no fallback.
- The joined sentences are embedded with BAAI/bge-m3 (dense, L2-normalised, 1024 dimensions, checked against the database dimension).
- It writes the same embeddings and Descriptions files that `embed.fake` writes, with a Manifest naming the models, the dimension and the files, plus progress reporting and `download_weights`.

See `../spec.md`.

**Blocked by:** 02, 04

**Status:** ready-for-agent

- [x] The VLM is injectable into the Description step, and tests with a fake VLM cover a valid answer, retried malformed answers, and `INVALID_MODEL_OUTPUT` on the third failure
- [x] Every Object gets exactly one Description, and the Stage fails if any Object lacks one
- [x] The VLM and embedder model ids and the batch sizes are params in the real pipeline config
- [x] The output files pass results reading from ticket 02
- [x] No automated test needs a GPU or model weights
- [x] `uv run main.py lint` and `uv run main.py test` pass
