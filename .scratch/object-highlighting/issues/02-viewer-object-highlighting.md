# 02: Highlight Objects on the point cloud and mesh

**What to build:** Replace Object boxes in the viewer with highlighting of each Object's own points
and mesh vertices, add hover, and make search highlighting usable. On Scene `test1` today:

- All 172 boxes draw at once (`layers.boxes: true` in
  [viewerStore.ts](../../../frontend/src/lib/store/viewerStore.ts)), so the room is unreadable.
- Hovering an Object does nothing; [layers/index.tsx](../../../frontend/src/components/viewer/layers/index.tsx)
  only handles clicks.
- Every search returns 503 `COMPUTE_UNAVAILABLE` because query text is embedded on the Target
  (ADR-0005) and the Target is off. The panel shows the API's English message.
- Search keeps every Object scoring above 0.15
  ([main.py](../../../backend/services/scene-api/src/scene_api/main.py) `search`). With MetaCLIP
  text-image cosines this likely keeps most of the room, so a highlight would mark everything.
- A highlighted box only changes colour from `#496a60` to `#9ee8c4`, so it is hard to see.

**Blocked by:** 01

**Status:** implemented — passes on the mock room and the fake backend; mesh-view highlighting and picking cost on test1 (611k points) wait for a browser check on the reprocessed Scene

- [x] The boxes layer is removed: no box drawing, no boxes entry in Display layers, no invisible
      boxes for picking.
- [x] GPU picking: the visible layer (points or mesh) is rendered by Object index to a 1×1 target
      under the cursor (a drawing-buffer-sized target with a 1×1 scissor, so points whose centre
      lies just outside the pixel are not clipped away; one pixel is filled and read). Where Objects overlap, the smallest Object (fewest members) wins, so
      pointing at a door handle picks the handle and not the wardrobe. Picking cost does not grow
      with the point count per pointer move.
- [x] Hover tints the hovered Object's points or vertices lightly and shows a tooltip with its
      label next to the cursor. It does not move the camera. It is off while measuring.
- [x] Click selects the picked Object as today (Object details, `focus`). Clicking empty space
      deselects.
- [x] When there is a selection or highlight (search, chat, Object details), those Objects draw in
      the app's highlight green and the rest of the room dims. Clearing returns real colours.
- [x] The same hover, selection and highlight work in mesh view through vertex membership.
- [x] A Scene whose membership asset is `null` still shows points and mesh; hover and highlight
      are off and the viewer says the Scene must be reprocessed to enable them.
- [x] Search: a 503 `COMPUTE_UNAVAILABLE` shows a localized message chosen by error code
      (`messages/*.json`), saying semantic search needs the GPU machine running. The API keeps
      returning 503.
- [x] API search keeps hits within a configurable margin of the best score, at most 10, and always
      keeps label matches. A REST test with fake embeddings shows the cut.
- [x] Frontend tests against the mock `SceneApi`: search highlights its hits, a 503 shows the
      localized message, and a Scene without membership shows the reprocess hint.
- [x] docs/architecture/frontend.md (viewer layers, highlight) and api.md (search) updated;
      `npm` done check in frontend/AGENTS.md passes.
