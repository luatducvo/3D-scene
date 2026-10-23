# 02: Remove the attributes Stage and Object attributes

**What to build:** A Job runs eight Stages (ingest, recon, align, mesh, segment, lift, embed, graph) with no attributes Stage, and the progress view and pipeline inspector show exactly those eight. Objects no longer have attributes anywhere: not in the stored Objects, not in the Objects endpoints, not in the mock API. The object details panel shows label, size and Best Views with no empty attributes area. See the parent spec, `.scratch/remove-qa-relations-attributes/spec.md`.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] The attributes Stage is gone from the Stage list and outputs, along with its Manifest model, both its Algorithms (`attributes.none`, `attributes.vlm_api`), its Fake Algorithm and their entry points.
- [ ] The graph Stage no longer reads attributes output.
- [ ] The real, fake and fake-GPU pipeline files, the compute server and the Colab cells name no attributes Stage.
- [ ] Objects carry no attributes field in the domain model, the database schema (the column is dropped in the init migration), the Objects endpoints, the regenerated OpenAPI contract or the frontend's synced types.
- [ ] The object details panel renders no attribute tags. The pipeline inspector has no attributes entry and no `attributes.none` notice.
- [ ] The mock API serves Objects without attributes.
- [ ] If question answering still exists when this ticket lands, its tools stop reading attributes.
- [ ] The pipeline, API, frontend and compute docs, the extending guide and the diagrams describe the Pipeline without attributes.
- [ ] The attributes Stage tests are deleted. The end-to-end Job test asserts the Stage order without attributes and Objects without attributes. The object details and stage stepper tests are updated.
- [ ] Done check passes: `uv run main.py lint`, `uv run main.py test`, `uv run main.py openapi`, `npm run api:sync`, `npm run typecheck`, `npm test`, `npm run build`. Developers reset the database with `uv run main.py reset`.
