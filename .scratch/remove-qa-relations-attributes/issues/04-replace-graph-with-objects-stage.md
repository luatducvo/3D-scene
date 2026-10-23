# 04: Replace the graph Stage with the objects Stage

**What to build:** A Job runs ingest, recon, align, mesh, segment, lift, embed, objects, and the progress view and pipeline inspector show the objects Stage last, with its Manifest giving the number of Objects. The objects Stage is performed by `objects.geometric` (Fake Algorithm `objects.fake`). It reads Instances and the mesh and writes the Objects file and the Object Membership file into its own `objects` folder. A Publication holds `objects/`, `embeddings/` and `mesh/`, and the viewer loads membership from its new URL with no change in behaviour. The term Scene Graph disappears from code and docs. See the parent spec, `.scratch/remove-qa-relations-attributes/spec.md`.

**Blocked by:** 02 (Remove the attributes Stage and Object attributes), 03 (Remove Relations, the room and wall planes)

**Status:** ready-for-agent

- [ ] The Stage list ends with `objects` instead of `graph`, and its output folder is `objects`. The objects Manifest reports only the number of Objects.
- [ ] `objects.geometric` and `objects.fake` replace `graph.geometric` and `graph.fake` in entry points and in the real, fake and fake-GPU pipeline files. The fake keeps the shared fail, fail_code, delay and progress_steps params.
- [ ] The Objects file sits at `objects/objects.json` and the membership file at `objects/membership.bin`. The membership binary format and version are unchanged.
- [ ] The Scene Graph model is replaced by a list of Objects throughout the domain, results loading, publishing and the API.
- [ ] Results loading reads the new paths. The public files are the mesh files and the objects folder's membership file, and the published asset URLs point there.
- [ ] The compute server, the Colab cells and any other deployment config run the new Stage list.
- [ ] The frontend's Stage labels, stage stepper, pipeline inspector and mock API use the objects Stage and the new membership path.
- [ ] The architecture docs, extending guide, testing guide and diagrams name the objects Stage. No code or doc says "Scene Graph" or uses "graph" for this concept.
- [ ] The graph Stage tests become objects Stage tests on the same synthetic workspaces. They check that each Object keeps its Instance id, that the Stage writes only its own folder, membership within the radius (and against a brute-force search), invalid radius and unreadable assets.
- [ ] The results tests use the new paths. The end-to-end Job test asserts the eight-Stage order ending with objects and the Publication's three folders.
- [ ] Done check passes: `uv run main.py lint`, `uv run main.py test`, `uv run main.py openapi`, `npm run api:sync`, `npm run typecheck`, `npm test`, `npm run build`.
