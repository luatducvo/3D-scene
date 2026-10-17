# Frontend

An independent Next.js app in [frontend/](../../frontend/). It knows the backend only through
`NEXT_PUBLIC_API_URL` (browser), `API_INTERNAL_URL` (server-side, over the `scene-net` Docker
network) and the committed OpenAPI file. Commands and validation steps are in
[Development and validation](#development-and-validation); scripts are in
[package.json](../../frontend/package.json).

## UI scope

The UI follows the approved Figma design, and the user's later UI decisions override SPEC's
interface stories: desktop web only, no Object list, no evidence photos, no suggested questions.
Input photo previews and quality badges remain part of capture review. API responses still carry
Object identities and evidence fields; the UI does not render evidence.

## Stack

Next.js App Router with TypeScript and React 19, Tailwind CSS 4, TanStack Query for server state,
Zustand for viewer state, React Three Fiber + drei for the viewer, next-intl for `en` / `vi`
strings, `openapi-typescript` + `openapi-fetch` for the typed client, MSW for the mock backend,
Vitest for tests.

## Source map

| Path | Role |
|---|---|
| `src/app/[locale]/page.tsx` | Scene list and "New scene" (the root URL opens `/vi`) |
| `src/app/[locale]/scenes/new/page.tsx` | Capture tips and upload |
| `src/app/[locale]/scenes/[sceneId]/page.tsx` | Progress, then the explorer |
| `src/components/SceneExplorer.tsx` | Full-viewport explorer: canvas, search, 360 px task panel |
| `src/components/StageStepper.tsx` | Renders per-Stage progress |
| `src/lib/sceneProgress.ts` | `useSceneProgress`: Stage Runs plus replayed and live SSE events, folded per Stage |
| `src/components/UploadDropzone.tsx`, `src/lib/quality/` | Drop files; sharpness/exposure scoring in a Web Worker |
| `src/components/ObjectDetails.tsx`, `ChatPanel.tsx`, `IngestReport.tsx` | Selected Object properties, streamed answers, rejected files |
| `src/components/viewer/SceneCanvas.tsx`, `viewer/layers/index.tsx` | Three.js canvas and replaceable layers |
| `src/components/viewer/view.ts`, `viewer/camera.ts` | Viewer rules without WebGL (default layers, framing bounds, home pose, focus box) and camera commands |
| `src/lib/api/http.ts`, `sse.ts`, `errors.ts` | `sceneApi`, the only way to the backend; one SSE reader and one error decoder |
| `src/lib/api/types.ts` | Schema aliases, `STAGES` (type-checked against the backend's Stage enum), event builders |
| `src/lib/api/mock/` | MSW handlers and a small deterministic colored PLY room |
| `src/lib/api/schema.d.ts` | Generated from OpenAPI, never edited by hand |
| `src/lib/store/viewerStore.ts` | Viewer state: selection, highlights, measuring, layer visibility, loaded layer bounds |
| `messages/en.json`, `messages/vi.json` | The only localized text |

## `sceneApi`

Screens use `sceneApi` from [src/lib/api](../../frontend/src/lib/api/index.ts), never `fetch`. JSON
requests go through `typedClient` (openapi-fetch), so `schema.d.ts` checks every path, parameter and
body. Uploads use `XMLHttpRequest` for upload progress; questions and Scene progress are streamed
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
name to a component receiving `{sceneId, assets, objects}`: `points` (dense point cloud from
`points.ply`), `mesh` (TSDF mesh) and `boxes` (Object boxes). The rules live in
[view.ts](../../frontend/src/components/viewer/view.ts) and are tested without WebGL: a Scene shows
its point cloud when it has one, else its mesh, and boxes always (`defaultLayers`); the view mode
shows exactly one of the two; the room is framed by the visible layer's bounds once loaded
(`visibleBounds`), whichever layer loaded first. The store holds state only.

Camera moves go through [camera.ts](../../frontend/src/components/viewer/camera.ts): `goHome()`
clears the selection and shows the whole room, `focus(ids)` highlights Objects and fits them in view.
Search, chat, Object details and box clicks call these; the canvas's controls attach on mount and
apply a focus given earlier. The room layers listen for clicks only while measuring.

While a layer loads, the canvas's Suspense fallback only reports it, and
[SceneCanvas.tsx](../../frontend/src/components/viewer/SceneCanvas.tsx) shows the loading label as
plain DOM over the canvas. drei's `Html` is never a Suspense fallback: unmounting it during the
canvas's commit makes React 19 log "synchronously unmount a root" and a `removeChild` error.

## User flow

1. **New scene:** capture tips, then a dropzone for photos or one video with a quality badge per image.
2. **Upload:** progress bar; "Process" starts the Job.
3. **Processing:** `StageStepper` shows plain-language Stage names, an overall bar (each Stage is 1/9
   plus the running one's reported share), elapsed time, and a time estimate for long Stages.
4. **Explorer:** full-viewport 3D canvas; search highlights matching geometry; selecting an Object
   opens its properties; chat, measuring and display controls open in the task panel.

## Development and validation

In `frontend/`, run `npm ci`, then `npm run dev` against the backend configured in
`NEXT_PUBLIC_API_URL`. Set `NEXT_PUBLIC_API_MODE=mock` to work without a backend or GPU. Open `/vi`
or `/en`; the root URL opens `/vi`.

A change is validated by `npm run typecheck`, `npm test` and `npm run build`. Visible changes also
get a browser check at desktop width (1440 × 960); mock mode covers creation, quality scoring,
upload, progress, selection, search, measuring, streamed chat, language switching and deletion.

Design SVGs and the Inter font are served locally from `public/design`, with the Inter license
alongside; the app loads no Figma asset URLs at runtime.
