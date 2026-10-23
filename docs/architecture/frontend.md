# Frontend

`frontend/`: Next.js App Router (standalone output), React, TanStack Query for server state, Zustand for viewer state, react-three-fiber for 3D, next-intl for strings. English is the only locale.

## Routes

| Route | File | Shows |
| --- | --- | --- |
| `/` | `src/app/page.tsx` | redirects to `/en` |
| `/en` | `src/app/[locale]/page.tsx` | the Scene library |
| `/en/scenes/new` | `src/app/[locale]/scenes/new/page.tsx` | name a Scene, add files, upload |
| `/en/scenes/{id}` | `src/app/[locale]/scenes/[sceneId]/page.tsx` | depends on the Scene's status (below) |

The Scene page shows:

- `created` or `uploaded`: `UploadDropzone` (more files) and, once uploaded, a button to process;
- `processing` or `failed`: `StageStepper` with live progress, and on failure the failure and a link to start a new Scene;
- before `ready`, once ingest has run: the `IngestReport` of kept and rejected Frames;
- `ready`: `SceneExplorer`.

## Data flow

- `sceneApi` (`src/lib/api/http.ts`) is the only way to the backend: typed `openapi-fetch` calls, plus hand-written upload (XMLHttpRequest, for upload progress) and SSE readers (`sse.ts`).
- Uploading first shrinks photos to `UPLOAD_LONG_SIDE` in the browser (`src/lib/upload/shrink.ts`); `UploadDropzone` scores each photo's sharpness and exposure in a worker (`src/lib/quality/`) to warn before upload.
- `useSceneProgress` (`src/lib/sceneProgress.ts`) seeds per-Stage state from the Scene's Stage Runs, follows `GET /events` while the Scene processes, reconnects on a dropped stream, and refetches the Scene on a terminal status.
- Query keys: `["scenes"]`, `["scene", id]`, `["objects", id]`, plus the membership file.

## Scene Explorer

`src/components/SceneExplorer.tsx` holds the 3D canvas, the Search box and a side panel that shows one of: `object` (`ObjectDetails` for the Selection), `measure`, `layers` (point cloud or mesh, point size, Instance Colors) or `info`.

- A Search Highlights its hits and colours them as an Object Heatmap (`HeatmapLegend`). `showResult` drops a result whose version is stale, so a slow Search cannot overwrite a newer one.
- The camera moves only through `goHome` (whole room, clears Selection and Highlight) and `focus(ids)` in `viewer/camera.ts`.

## Viewer

`src/components/viewer/`:

| File | Holds |
| --- | --- |
| `SceneCanvas.tsx` | the react-three-fiber canvas, controls, picking and hover; renders every entry of `sceneLayers` |
| `layers/index.tsx` | `sceneLayers`: `points` (`PointCloudLayer`, `points.ply`) and `mesh` (`MeshLayer`, `mesh.glb`); repaints vertex colours for Highlight, hover and Instance Colors |
| `view.ts` | which layer shows, room bounds, home and focus poses, whether highlighting is available |
| `highlight.ts` | which Object owns each point (the smallest one), highlight, dim and hover colours, heatmap normalisation |
| `picking.ts` | a hidden twin of each layer coloured by Object id, read back to pick the Object under the pointer |
| `camera.ts` | `goHome`, `focus` and the driver the canvas attaches |

`src/lib/store/viewerStore.ts` holds viewer state: Selection, Highlight and its source, similarities, hover, Measurement points, layers, appearance, camera pose, loaded bounds.

Object Membership (`src/lib/api/membership.ts`) maps each Object to its points and vertices; the viewer refuses to highlight when the membership is absent or its counts do not match the loaded geometry.

## Mock mode

With `NEXT_PUBLIC_API_MODE=mock`, `src/app/providers.tsx` starts MSW (`public/mockServiceWorker.js`) before rendering. `src/lib/api/mock/handlers.ts` serves every API path, including the SSE progress stream, with a demo Scene built in `mock/room.ts` and its membership in `mock/membership.ts`.
