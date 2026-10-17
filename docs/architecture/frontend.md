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
| `src/components/StageStepper.tsx` | Live progress from the SSE stream |
| `src/components/UploadDropzone.tsx`, `src/lib/quality/` | Drop files; sharpness/exposure scoring in a Web Worker |
| `src/components/ObjectDetails.tsx`, `ChatPanel.tsx`, `IngestReport.tsx` | Selected Object properties, streamed answers, rejected files |
| `src/components/viewer/SceneCanvas.tsx`, `viewer/layers/index.tsx` | Three.js canvas and replaceable layers |
| `src/lib/api/port.ts` | The `SceneApi` interface every screen uses |
| `src/lib/api/http.ts`, `sse.ts` | Real backend implementation |
| `src/lib/api/mock/` | MSW handlers and a small deterministic colored PLY room |
| `src/lib/api/schema.d.ts` | Generated from OpenAPI, never edited by hand |
| `src/lib/store/viewerStore.ts` | Selection, highlights, measuring, layer visibility |
| `messages/en.json`, `messages/vi.json` | The only localized text |

## The `SceneApi` port

Screens depend on `SceneApi` ([port.ts](../../frontend/src/lib/api/port.ts)), never on `fetch`.
[index.ts](../../frontend/src/lib/api/index.ts) picks the HTTP implementation or the mock one from
`NEXT_PUBLIC_API_MODE` (`http` | `mock`). Mock mode exercises the same HTTP and SSE paths through MSW,
so UI work needs no backend or GPU; it does not test reconstruction quality or live GPU services.
Schema type names must match the backend's pydantic model names.

## Viewer layers

`sceneLayers` in [layers/index.tsx](../../frontend/src/components/viewer/layers/index.tsx) maps a
name to a component receiving `{sceneId, assets, objects}`: `points` (dense point cloud from
`points.ply`, on by default), `mesh` (TSDF mesh, off) and `boxes` (Object boxes, on). The store keeps
per-layer visibility. Search and chat only write `highlightedIds` to the store; the boxes layer
draws highlights and flies the camera. The point cloud listens for clicks only while measuring.

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
