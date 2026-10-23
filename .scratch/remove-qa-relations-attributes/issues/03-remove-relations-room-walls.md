# 03: Remove Relations, the room and wall planes

**What to build:** A processed Scene has no Relations and no room summary (floor, ceiling, area). The graph Stage only turns Instances into Objects with oriented boxes and writes Object Membership, so selection, Highlight, Object Heatmap and Instance Colors behave exactly as before. The align Stage still gravity-aligns the Frames and reports floor height and ceiling height in its Manifest, but no longer writes wall planes. See the parent spec, `.scratch/remove-qa-relations-attributes/spec.md`.

**Blocked by:** 01 (Remove LLM question answering), whose tools are the only readers of Relations and the room.

**Status:** ready-for-agent

- [ ] The Relation rules (`on`, `under`, `above`, `inside`, `next_to`, `near`, `against_wall`), the Relation rule port and the `scene_relations` entry point group are removed. The registry test checks that no Relation group remains.
- [ ] The Relation domain model and the Scene Graph's relations and room fields are removed. The graph Stage's params have no list of Relations, and its Manifest has no Relation count.
- [ ] The graph Stage no longer reads align output.
- [ ] The align Stage no longer writes wall planes, in the real and the fake Algorithm. Its Manifest keeps floor height and ceiling height.
- [ ] The init migration drops the relations table and the Scenes' room column. Publishing writes neither, and the Scene response has no room.
- [ ] Geometry helpers that nothing uses any more are removed.
- [ ] The pipeline inspector drops the Relation count.
- [ ] The OpenAPI contract is regenerated and the frontend's types are synced.
- [ ] The extending guide's Relation section goes. The pipeline, API and overview docs and the diagrams describe no Relations, room or wall planes.
- [ ] The Relation-rule and missing-walls tests are deleted. The graph Stage's membership, radius and unreadable-asset tests still pass, as do the end-to-end Job and store tests.
- [ ] Done check passes: `uv run main.py lint`, `uv run main.py test`, `uv run main.py openapi`, `npm run api:sync`, `npm run typecheck`, `npm test`, `npm run build`. Developers reset the database with `uv run main.py reset`.
