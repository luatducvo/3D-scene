# Frontend

An independent Next.js app in [frontend/](../../frontend/). It knows the backend only through
`NEXT_PUBLIC_API_URL` (browser), `API_INTERNAL_URL` (server-side, over the `scene-net` Docker
network) and the committed OpenAPI file. Commands and validation steps are in
[Development and validation](#development-and-validation); scripts are in
[package.json](../../frontend/package.json).

## UI scope

The UI follows the approved Figma design, and the user's later UI decisions override SPEC's
interface stories: desktop web only, no Object list, no evidence photos, no suggested questions.
English is the only rendered language. The language switch is removed; old Vietnamese locale URLs redirect to English while preserving the Scene path and query. Existing translation data is not selected by the application. Search and questions are supported in English without language detection or rejection.

Input photo previews and quality badges remain part of capture review. API responses still carry
Object identities and evidence fields; the UI does not render evidence.

## Stack

Next.js App Router with TypeScript and React 19, Tailwind CSS 4, TanStack Query for server state,
Zustand for viewer state, React Three Fiber + drei for the viewer, next-intl for English
strings, `openapi-typescript` + `openapi-fetch` for the typed client, MSW for the mock backend,
Vitest for tests.

## Source map

| Path | Role |
|---|---|
| `src/app/[locale]/page.tsx` | Scene list and "New scene" (the root URL opens `/en`) |
| `src/app/[locale]/scenes/new/page.tsx` | Capture tips and upload |
| `src/app/[locale]/scenes/[sceneId]/page.tsx` | Progress, then the explorer |
| `src/components/SceneExplorer.tsx` | Full-viewport explorer: canvas, search, 360 px task panel |
| `src/components/StageStepper.tsx` | Renders per-Stage progress |
| `src/lib/sceneProgress.ts` | `useSceneProgress`: Stage Runs plus replayed and live SSE events, folded per Stage |
| `src/components/UploadDropzone.tsx`, `src/lib/quality/` | Drop files; sharpness/exposure scoring in a Web Worker |
| `src/lib/upload/shrink.ts` | Shrinks photos to ingest's `long_side` as metadata-free JPEG before upload |
| `src/components/ObjectDetails.tsx`, `ChatPanel.tsx`, `IngestReport.tsx` | Selected Object properties, latest independent answer, rejected files |
| `src/components/viewer/SceneCanvas.tsx`, `viewer/layers/index.tsx` | Three.js canvas, pointer picking, hover label and replaceable layers |
| `src/components/viewer/view.ts`, `viewer/camera.ts` | Viewer rules without WebGL (default layers, framing bounds, home pose, focus box, highlight availability) and camera commands |
| `src/components/viewer/highlight.ts`, `viewer/picking.ts` | Object highlight and hover painting, pick ownership; the GPU pick pass |
| `src/components/HeatmapLegend.tsx`, `PipelineInspector.tsx` | Relative search similarity legend and metadata-only Stage explanations |
| `src/components/SearchStatus.tsx` | Search result count or localized search error |
| `src/lib/api/http.ts`, `sse.ts`, `errors.ts`, `membership.ts` | `sceneApi`, the only way to the backend; one SSE reader, one error decoder, the membership decoder |
| `src/lib/api/types.ts` | Schema aliases, `STAGES` (type-checked against the backend's Stage enum), event builders |
| `src/lib/api/mock/` | MSW handlers, a deterministic colored PLY and GLB room with matching Object membership, and a `legacy` Scene without membership |
| `src/lib/api/schema.d.ts` | Generated from OpenAPI, never edited by hand |
| `src/lib/store/viewerStore.ts` | Viewer state: selection, highlights, hovered Object, measuring, layer visibility, loaded layer bounds, membership fit |
| `messages/en.json`, `messages/vi.json` | The only localized text |

## `sceneApi`

Screens use `sceneApi` from [src/lib/api](../../frontend/src/lib/api/index.ts), never `fetch`. JSON
requests go through `typedClient` (openapi-fetch), so `schema.d.ts` checks every path, parameter and
body. `uploadFiles` first shrinks every JPEG, PNG or WebP photo larger than `UPLOAD_LONG_SIDE` to a
JPEG of that long side at quality 0.95, `SHRINK_CONCURRENCY` (8) photos at once because each JPEG
encode takes about a second off the main thread, EXIF orientation applied and metadata dropped by
the canvas. Each full-resolution decode is released before its encode. Ingest keeps such a JPEG byte for byte, so a photo is compressed once, and the
tunnel to a remote Target carries roughly a sixth of the bytes. `UPLOAD_LONG_SIDE` must equal
ingest's `long_side` in `pipeline.yaml`: smaller, the pipeline gets less detail than configured;
larger, ingest re-encodes every photo. Videos, HEIC, smaller photos and files the browser cannot
decode go as they are. Shrinking is the first half of the progress bar. Uploads use
`XMLHttpRequest` for upload progress; questions and Scene progress are streamed
with `fetch` and read by one SSE reader ([sse.ts](../../frontend/src/lib/api/sse.ts)). Every error body
becomes an `ApiError` through `toApiError` ([errors.ts](../../frontend/src/lib/api/errors.ts)).
`subscribeProgress` reconnects a dropped progress stream and stops at a terminal status.

There is one implementation. Mock mode (`NEXT_PUBLIC_API_MODE=mock`) starts MSW in the browser,
which serves the same HTTP and SSE paths, so UI work needs no backend or GPU; it does not test
reconstruction quality or live GPU services. Schema type names must match the backend's pydantic
model names.

## Scene progress

`useSceneProgress(sceneId, scene)` ([sceneProgress.ts](../../frontend/src/lib/sceneProgress.ts))
starts from the Scene's Stage Runs and, while it processes, follows the progress stream. Replay and
live events have the same shapes ([api.md](api.md#sse-events)): a `stage` event replaces a Stage's
state (a Stage that starts again clears its progress), a `progress` event updates its counts, and a
terminal `status` refetches the Scene. Its tests drive `watchSceneProgress`, the part behind the
hook, with MSW streaming replayed, live and reconnecting streams.

## Viewer layers

`sceneLayers` in [layers/index.tsx](../../frontend/src/components/viewer/layers/index.tsx) maps a
name to a component receiving `{sceneId, assets, objects, membership}`: `points` (dense point cloud
from `points.ply`) and `mesh` (TSDF mesh). Objects are not drawn as boxes; they are shown on the
room's own geometry ([below](#object-highlighting)). The rules live in
[view.ts](../../frontend/src/components/viewer/view.ts) and are tested without WebGL: a Scene shows
its point cloud when it has one, else its mesh (`defaultLayers`); the view mode shows exactly one of
the two; the room is framed by the visible layer's bounds once loaded (`visibleBounds`), whichever
layer loaded first. The store holds state only.

Camera moves go through [camera.ts](../../frontend/src/components/viewer/camera.ts): `goHome()`
clears selection/results and shows the whole room; `focus(ids)` fits Object bounds without changing
their colors. Result visualization and selection are separate viewer state. Search, chat, Object details and a click on an Object call these; the canvas's controls attach
on mount and apply a focus given earlier. The room layers listen for raycast clicks only while
measuring.

### Object highlighting

`SceneExplorer` loads Object membership with `sceneApi.getMembership(assets.membership_url)`, which
decodes `graph/membership.bin` ([api.md](api.md#object-membership)) in
[membership.ts](../../frontend/src/lib/api/membership.ts), and passes it to the layers. A layer uses
it only when its counts match the loaded geometry: `pointCount` against the PLY's vertices (PLYLoader
keeps file order), `vertexCount` against the glTF's POSITION entries, taken per primitive in glTF
mesh and primitive order through `parser.associations` (GLTFLoader neither merges nor reorders
vertices). A mismatch sets `membershipMismatch` in the store and logs a warning.

- **Painting** ([highlight.ts](../../frontend/src/components/viewer/highlight.ts), tested without
  WebGL): `Painter` rewrites the layer's per-element colour array from the real colours it keeps
  aside. Highlighted and selected Objects draw in the highlight green (`#9ee8c4`) and every other
  element dims to `DIM` of its colour; with no highlight, real colours return. The hovered Object
  moves `HOVER_MIX` towards white, and a hover change repaints only the two Objects involved. The
  mesh's vertex colours are painted the same way, multiplied by its lighting.
- **Picking** ([picking.ts](../../frontend/src/components/viewer/picking.ts)): each layer adds a pick
  twin that shares its position (and index) buffers and carries one colour per element, the 24-bit
  index of its owning Object (`owners`, `pickColors`). Where Objects overlap, the Object with the
  fewest members owns the element, so a door handle wins over the wardrobe. Ids are never blended:
  the point twin draws each point as one vertex, and the mesh twin uses a GLSL3 pick shader whose id
  varying is `flat`, so a triangle whose vertices have different owners takes its last vertex's id
  rather than an interpolated colour that would decode to another Object. Both layers set this up
  through `useObjectHighlighting` in [layers/index.tsx](../../frontend/src/components/viewer/layers/index.tsx),
  which also checks the counts and runs the painting. `pickAt` draws the twins
  into a render target the size of the drawing buffer with a 1 × 1 scissor under the cursor and reads
  that pixel back: the same projection keeps points their on-screen size (a narrowed view would clip
  points whose centres fall outside it), while only one pixel is filled and read. No CPU raycast
  runs over the points.
- **Pointer** (`Picker` in [SceneCanvas.tsx](../../frontend/src/components/viewer/SceneCanvas.tsx)):
  a pointer move only records the position; the next frame picks once and sets `hovered`, which tints
  the Object and shows its label next to the cursor (`HoverLabel`). Nothing picks while a button is
  held (orbit or pan) or while measuring. A press that moves less than 4 px is a click: on an Object it
  selects it and calls `focus`; on empty space it deselects, which also drops the highlight when it was
  only the selection.
- **Without membership** (`highlightState` in view.ts): a Scene whose `membership_url` is `null`
  (published before membership existed), or whose membership does not fit the shown layer, still
  shows its geometry; hover and highlight are off and the viewer asks for the Scene to be processed
  again. A membership file that fails to load shows its own notice.

Search errors are shown by error code from `searchErrors` in `messages/*.json`
([SearchStatus.tsx](../../frontend/src/components/SearchStatus.tsx)); `COMPUTE_UNAVAILABLE` says
semantic search needs the GPU machine running. Search does not retry, because the API answers 503
only after its own wait for the Target.

While a layer loads, the canvas's Suspense fallback only reports it, and
[SceneCanvas.tsx](../../frontend/src/components/viewer/SceneCanvas.tsx) shows the loading label as
plain DOM over the canvas. drei's `Html` is never a Suspense fallback: unmounting it during the
canvas's commit makes React 19 log "synchronously unmount a root" and a `removeChild` error.

## User flow

1. **New scene:** capture tips, then a dropzone for photos or one video with a quality badge per image.
2. **Upload:** progress bar; "Process" starts the Job.
3. **Processing:** `StageStepper` shows plain-language Stage names, an overall bar (each Stage is 1/9
   plus the running one's reported share), elapsed time, and a time estimate for long Stages.
4. **Explorer:** full-viewport 3D canvas; Original or Instances appearance; hover labels and selection with dimensions/focus; English search paints a relative Object Heatmap. Independent QA, measurement, display controls and Pipeline Inspector use the task panel.

## Development and validation

The frontend Docker build uses the repository root as context, with
[Dockerfile.frontend](../../Dockerfile.frontend) and the shared root `.dockerignore`.
It copies only `frontend/` into the image. Local dependencies, Next.js output, generated TypeScript
metadata, test reports and environment files are excluded (`.env.example` remains available).
The image installs dependencies from `frontend/package-lock.json` and rebuilds the application
from source; public build configuration comes from the Dockerfile build arguments.

In `frontend/`, run `npm ci`, then `npm run dev` against the backend configured in
`NEXT_PUBLIC_API_URL`. Set `NEXT_PUBLIC_API_MODE=mock` to work without a backend or GPU. Open `/en`; old `/vi` deep links redirect to the matching English URL.

A change is validated by `npm run typecheck`, `npm test` and `npm run build`. Visible changes also
get a browser check at desktop width (1440 × 960); mock mode covers creation, quality scoring,
upload, progress, selection, search, measuring, independent QA, English navigation, Inspector and deletion.

Design SVGs and the Inter font are served locally from `public/design`, with the Inter license
alongside; the app loads no Figma asset URLs at runtime.


## Appearances and active results

Original is the default. Instances assigns stable, distinct Object ID colors on either Point Cloud
or Mesh; shared geometry uses the same smaller-membership ownership as picking. Unassigned geometry
keeps its original color. Hover and selection are temporary feedback, separate from the base
appearance and active result. Restoring feedback never accumulates tints.

Search consumes both ranking `score` and unbonused `raw_similarity`. Only raw similarity is normalized
within the returned Objects for the query: minimum is cool and maximum hot. One result or tied
similarities are all hot with a single-level explanation. The legend states that this is relative
similarity, not confidence; colors cannot be compared across queries. No results restores the base
appearance and shows a distinct empty message; failures keep their error states.

Only one search or QA visualization is active. Search colors override instance colors; QA highlights
referenced Object IDs without inventing relevance scores. Clear restores the chosen base appearance.
A monotonically increasing result version rejects delayed results after a newer request, Clear,
Home, or a Scene change. Debounced search does not automatically repaint cached results after QA;
a superseded response can settle its search status without taking control of the viewer.

## Independent QA

The question panel holds only the latest question and answer in transient state and retains a
completed answer directly. It never fetches message history. Each request carries the current
question and camera; the API supplies no earlier exchanges and saves no new messages. Existing
stored messages are preserved. Closing or switching panels preserves the latest exchange for this Scene; reopening a Scene starts with an empty panel. Answers are instructed
to be English; tool progress, cancellation, numerical grounding and error reporting remain.

## Pipeline Inspector

The Inspector is a side panel beside the viewer, listing all nine Stages. Selecting a Stage shows
its purpose and input/output roles from an English explanatory catalog, and its Algorithm, status,
available elapsed timing and meaningful statistics from Scene detail Stage Runs and Manifests.
Elapsed time is derived only from valid recorded timestamps of a terminal Stage Run and is labeled
accordingly. Missing values are Not available, never zero. The disabled attributes Algorithm is
explicitly explained as producing no VLM enrichment.

The Inspector reads published metadata, so it works with the Target off. It does not fetch or expose
intermediate Frame/depth/mask previews, execution parameters, or new file endpoints. Fake fixtures
include both geometry representations and completed Stage metadata for desktop browser checks.
