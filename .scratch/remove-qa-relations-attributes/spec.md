# Remove question answering, Relations and the attributes Stage

Status: ready-for-agent

## Problem Statement

The product promises that a Scene's Objects can be searched, inspected and asked about in plain English. In practice the "asked about" half costs more than it gives:

- Question answering needs an external LLM endpoint and its keys. It fails in ways the rest of the product does not (ungrounded answers, step limits, an unconfigured LLM), and its tests rely on scripted LLM replies.
- The attributes Stage is configured to produce nothing. The vision-LLM Algorithm exists but is never used, so every Object carries an empty attributes field and the viewer shows no attribute tags.
- The graph Stage computes Relations (on, under, next to, against a wall…) and a room summary (floor, ceiling, area) that only question answering reads. Its real work for the viewer is the Objects' oriented boxes and Object Membership, which is buried among Relation rules.

Every Job pays for two Stages and every developer maintains a whole LLM agent that the core experience (capture → process → search → inspect in 3D) does not need.

## Solution

Narrow the product to "searched and inspected":

- Question answering with an LLM disappears from the backend and the frontend. Highlight becomes purely the answer to a Search.
- The attributes Stage disappears, and Objects no longer have attributes.
- Relations disappear as a concept.
- The room summary (floor, ceiling, area) disappears. The align Stage keeps gravity alignment and still reports floor height and ceiling height in its own Manifest, but no longer writes wall planes.
- The graph Stage is replaced by a thin final Stage named **objects**, performed by the Algorithm `objects.geometric` (Fake Algorithm `objects.fake`). It only turns Instances into Objects with oriented boxes and writes Object Membership.
- The Pipeline becomes eight Stages: ingest, recon, align, mesh, segment, lift, embed, objects.
- The term Scene Graph is retired. A Publication serves the Scene's Objects, their embeddings and its mesh.

From the user's point of view, uploading, processing, Search, Highlight, Selection, Object Heatmap, Instance Colors, Measurement and object details all work as before. The "Ask scene" entry point and the chat panel are gone, and the pipeline view shows eight Stages.

## User Stories

1. As a user, I want to process a Scene without configuring any LLM endpoint, so that the product works with nothing but its own compute Target.
2. As a user, I want the processing progress view to list exactly eight Stages ending with "objects", so that what I see matches what runs.
3. As a user, I want no "Ask scene" button or chat panel in the explorer, so that the interface offers only what the product supports.
4. As a user, I want Search to remain the one way to Highlight Objects, so that a Highlight always means "matches my query".
5. As a user, I want to click a point or vertex and select the smallest Object it belongs to, exactly as before, so that inspection is unchanged.
6. As a user, I want the camera to fly to a selected or highlighted Object, so that I can find it in the room.
7. As a user, I want the object details panel to show the Object's label, size and Best Views without an empty attributes area, so that the panel shows only real information.
8. As a user, I want Object Heatmap and Instance Colors to keep painting Objects correctly, so that the viewer layers are unaffected.
9. As a user, I want Measurement to keep working between any two picked points, so that I can still measure the room myself.
10. As a user, I want a Job to take less time because two Stages' work is gone, so that I get results sooner.
11. As a user re-processing a Scene, I want a failed Job to leave the current Publication untouched, as before, so that removing Stages does not weaken that guarantee.
12. As a user, I want the pipeline inspector to show the objects Stage's Manifest (the number of Objects), so that I can check the final result.
13. As a user, I want the align Stage's Manifest to still show floor height and ceiling height, so that I can judge the alignment.
14. As a developer, I want the pipeline files (real, fake and fake-GPU) to name only the eight Stages and their Algorithms, so that configuration matches the code.
15. As a developer, I want the Algorithm registry to have no Relation entry point group and no attributes or graph Algorithms, so that nothing dead is installed.
16. As a developer, I want the objects Stage to read only Instances and the mesh, so that its inputs are as small as its job.
17. As a developer, I want `objects.geometric` to keep the Instance id for each Object, so that "each Instance becomes exactly one Object with the same id" still holds.
18. As a developer, I want `objects.geometric` to reject a non-positive membership radius as invalid parameters, as the graph Stage did, so that configuration mistakes still fail loudly.
19. As a developer, I want `objects.geometric` to report an unreadable mesh or point cloud as an unreadable asset, as before, so that error handling is unchanged.
20. As a developer, I want Object Membership to list a point under every Object within the radius, as before, so that nested Objects (a handle in a wardrobe) still both own it.
21. As a developer, I want the membership binary format to be unchanged apart from where it is stored, so that the frontend decoder keeps working.
22. As a developer, I want `SceneResults` to load a Publication from its objects, embeddings and mesh folders and to reject mismatched ids, embeddings or membership, as before, so that publishing stays safe.
23. As a developer, I want the public files of a Publication to be the mesh files and the membership file only, so that the Objects list is still served only through the Objects endpoints.
24. As a developer, I want the database schema to have no relations table, no attributes column on Objects and no room column on Scenes, so that the schema holds only what is served.
25. As a developer, I want the API app factory to take no LLM argument, so that building the API in tests needs no question-answering stand-in.
26. As a developer, I want the OpenAPI contract and the frontend's generated types to drop the queries endpoint, the question and answer models, the attributes field and the room, so that both sides agree.
27. As a developer, I want the error codes only question answering raised (ungrounded answer, step limit, unconfigured LLM, Scene not ready for questions) to be gone from the code and the failure docs, so that the error catalogue lists only reachable errors.
28. As a developer, I want the LLM environment variables gone from the example environment file and the configuration docs, so that setup asks for nothing unused.
29. As a developer, I want geometry helpers that only question answering used to be removed, so that no dead code remains.
30. As a developer, I want the mock API used by the frontend's mock mode to serve the new shapes (no attributes, no queries), so that running the UI without a backend still works.
31. As a developer, I want the viewer store to know only Search as a source of results, so that its state has no unreachable branch.
32. As a developer, I want the Colab and other compute deployment files to run the eight-Stage Pipeline, so that GPU Targets keep working.
33. As a developer, I want the architecture docs, extending guide and diagrams to describe eight Stages and no Relations, attributes or question answering, so that the docs match the code.
34. As a developer, I want GLOSSARY.md to define the objects Stage, no Relation and no Scene Graph, so that the domain language matches the product (already done).
35. As a maintainer, I want the change to reset the database rather than migrate it, following the repo's schema convention, so that there is no migration code to keep.

## Implementation Decisions

- **Pipeline contract.** The Stage list becomes ingest, recon, align, mesh, segment, lift, embed, objects. The attributes and graph Stages, their output folders and Manifest models are removed. A new objects Manifest reports the number of Objects. The align Manifest keeps floor height and ceiling height.
- **objects Stage.** It reads the lift Stage's Instances and the mesh Stage's point cloud and mesh. It writes an Objects file (each Object's id, label, oriented box and Best Views) and the membership file in an `objects` folder. It no longer reads align output or attributes. Its params are the membership radius (and device, if the graph Stage had one), with no list of Relations. It is mostly the graph Stage with the Relation evaluation and the room assembly taken out.
- **Fake Algorithm.** `objects.fake` replaces the graph and attributes fakes and keeps the shared fail, fail_code, delay and progress_steps params.
- **align Stage.** It stops writing wall planes; nothing else reads them.
- **Domain models.** Relation, the Scene Graph model and its context model are removed, along with the attributes field on an Object. What a Publication carries is a list of Objects. The Relation rule port and the `scene_relations` entry point group are removed.
- **Publication layout.** A Publication holds `objects/`, `embeddings/` and `mesh/`. The public files are the mesh files and the objects folder's membership file. The membership binary format (magic, version 1, sections) is unchanged, so its version stays 1.
- **Publishing.** Publishing replaces the Scene's Objects, sets the Publication and marks the Job done and the Scene ready. It no longer writes Relations or a room.
- **Database.** The single init migration drops the relations table, the attributes column on Objects and the room column on Scenes. The database is reset (`uv run main.py reset`); existing Scenes are lost by design.
- **API.** The queries endpoint, its request, answer and stream event models, and the LLM argument of the app factory are removed. The Objects endpoints return Objects without attributes. The Scene response has no room. Error codes reachable only from question answering are removed. The OpenAPI contract is regenerated and synced to the frontend.
- **Question answering module.** The module holding the agent, the scene tools and both LLM clients is deleted, along with the LLM environment variables.
- **Frontend.** The chat panel, the "Ask scene" control, the client method that asks a question and its mock handler are removed. The viewer store's result source can only be Search. Object details drop the attribute tags. The pipeline inspector lists the objects Stage's Manifest field and drops the attributes and graph entries. Translation strings used only by these parts are removed.
- **Deployment.** Pipeline files, the compute server, Colab cells and any other deployment config that names Stages are updated to the eight-Stage list.
- **Docs.** The architecture docs (overview, pipeline, API, frontend, compute), the extending guide (the Relation and QA-tool sections go), the failure docs, the testing guide (no scripted LLM) and the diagrams are updated. GLOSSARY.md is already updated.
- **No ADR.** The user decided the commit message is enough record.

## Testing Decisions

- A good test drives the system through its public seams and asserts what a user or caller observes: Stage order, Publication contents, endpoint responses, error codes, rendered behaviour. It never asserts private helpers or call order.
- **Seam 1, primary: a whole Job end to end** through the API app factory and the Worker, on the fake pipeline. It checks that a Job runs the eight Stages in order ending with objects, that the Publication holds only the objects, embeddings and mesh folders, that the Objects endpoints return Objects with boxes and Best Views and no attributes, that the Scene has no room, that Search still Highlights the right Objects, and that the queries endpoint no longer exists. Prior art: the publish-and-rerun, search and failed-reprocess tests in the API suite, and the store tests for every Stage and publishing.
- **Seam 2: the `objects.geometric` Algorithm** run on a small synthetic workspace. It checks that an Object keeps its Instance id, that the objects Stage writes only its own folder, that membership lists a point under every Object within the radius (and agrees with a brute-force search), that a non-positive radius is invalid parameters, and that unreadable mesh files are unreadable assets. Prior art: the current graph Stage tests, minus the Relation and walls cases.
- **Seam 3: loading a Publication** with `SceneResults`. It covers one embedding per Object, rejecting mismatched embeddings or membership, reporting missing results, and the mesh files and membership being the only public files, all on the new paths. Prior art: the current results tests.
- **Registry:** every configured Algorithm is installed and no Relation group remains. Prior art: the current registry test.
- **Frontend:** behaviour tests for the scene explorer (Search paints and dims, no ask control), object details (geometry without attributes), the stage stepper (eight Stages) and the HTTP client (no question method). Prior art: the existing tests beside each module.
- **Removed tests:** the attributes Stage tests, the QA tests in the API suite, the Relation-rule tests and the client's question tests are deleted along with what they test.
- **Done check:** `uv run main.py lint`, `uv run main.py test`, `uv run main.py openapi`, then `npm run api:sync`, `npm run typecheck`, `npm test` and `npm run build`.

## Out of Scope

- Any replacement for question answering, such as rule-based or templated answers.
- New uses for the removed room data or wall planes.
- Changes to Search ranking, the embed Stage or the membership binary format.
- Migrating existing Scenes or Publications; the database is reset.
- Changes to the ingest, recon, mesh, segment, lift or embed Algorithms beyond what the new Stage list needs.

## Further Notes

- The objects Stage still turns Instances into Objects, so the glossary keeps Instance and Object separate.
- `uv run main.py reset` must run after this change lands on any machine with an existing database, or the API and worker will fail against the old schema.
- Any doc wording that relies on "graph" or "Scene Graph" should say "Objects" instead; the glossary flags both terms as retired.
