# 02: Docs alignment — glossary, ADR-0001, architecture doc

**What to build:** Bring the written design in line with the agreed spec so later agents read one consistent story. Create the domain glossary, record the one surprising decision as an ADR, and edit the architecture doc where the spec deviates from it.

**Blocked by:** None (can start immediately)

**Status:** done — glossary lives in GLOSSARY.md

- [ ] A root glossary defines Scene, Keyframe, Frame, Stage, Algorithm, Target, Workspace, Manifest, Vocabulary, Job, Stage Run, Compute Run, Instance, Object, Relation, Scene Graph, with no implementation details.
- [ ] ADR-0001 records "the worker publishes the Scene Graph into Postgres; Algorithms never touch the database", with the alternative considered.
- [ ] The architecture doc reflects: Executor in scene-core, entry-point-only registry, worker publish step, graph Stage writes only its folder, `/queries` path, upload/busy 409 rules, `min_keyframes`, Modal building from the Dockerfile, task runner replacing the Makefile, in-house MaskClustering re-implementation.
- [ ] A short agent guide points to the spec, architecture doc, glossary and task commands.
