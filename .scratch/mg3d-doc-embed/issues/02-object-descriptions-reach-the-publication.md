# 02: Object Descriptions reach the Publication

**What to build:** A processed Scene stores one Object Description per Object. `embed.fake` writes a deterministic Descriptions file next to the embeddings, mapping each Object id to its three sentences (appearance, use, placement). Reading results requires that file and checks that its ids match the Objects and the embeddings exactly. Publishing writes the joined sentences into a new non-null `objects.description` column. The Object API does not expose it. See `../spec.md`, "Publication and storage".

**Blocked by:** 01

**Status:** ready-for-agent

- [x] A migration adds a non-null text column `description` to `objects`
- [x] `embed.fake` writes deterministic Descriptions for every Object; its `fail`, `fail_code`, `delay` and `progress_steps` params still work
- [x] A missing Descriptions file, or ids that differ from the Objects or the embeddings, raises `RESULTS_INVALID`
- [x] After a fake Job, every published Object row has a non-empty description
- [x] A failed reprocess keeps the previous Publication, Descriptions included
- [x] The Object API model is unchanged
- [x] `uv run main.py lint` and `uv run main.py test` pass
