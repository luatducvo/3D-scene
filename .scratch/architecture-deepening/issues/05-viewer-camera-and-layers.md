# 05: Viewer camera and layer module

**What to build:** Replace the `homeRevision`/`focusRevision` counters in `viewerStore` with a
camera module exposing `goHome()` and `focus(box)`. `Controls` registers it on mount, and the home
pose formula and camera write-back live in one place. Move the visible-layer rule (points if
available, else mesh, written three times in SceneExplorer) and the bounds (today set by whichever
layer loads first) into one viewer module. Speculative: no known bug. See
[spec](../spec.md#viewer-ticket-05-speculative-last).

**Blocked by:** 04

**Status:** implemented — done last, as the user chose on 2026-10-17

- [x] Store holds state only. No revision counters.
- [x] `goHome()` / `focus(box)` work from SceneExplorer, ObjectDetails and chat. Camera write-back
      happens once.
- [x] Visible-layer rule and bounds come from one module, and bounds follow the visible layer.
- [x] vitest covers the layer rule and bounds without WebGL.
- [x] docs/architecture/frontend.md updated. The frontend done check passes.

## Comments

- 2026-10-17: Box clicks now call `focus([id])` explicitly; before, any change of `highlightedIds`
  flew the camera. Mesh clicks, like point-cloud clicks, are only listened to while measuring. The
  browser check saw the home pose computed from the point cloud's bounds (sent with a question); the
  hidden browser pane paused rendering, so the focus flight was not watched. The dev overlay's
  "synchronously unmount a root" error from drei `Html` predates this ticket.
