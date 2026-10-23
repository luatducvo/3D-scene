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

`src/components/SceneExplorer.tsx` holds the 3D canvas, a topbar (the Points/Mesh switch with point size in Points mode, Instance Colors, the Search box) and a side panel that shows one of: `object` (`ObjectDetails` for the Selection), `measure` or `info`. Each panel opens from its spatial-tools button; the `object` one only while there is a Selection, which it follows, and it closes when the Selection is dropped.

- The viewer is in one interaction at a time (`interaction` in the viewer store): idle (hover paints the Object under the pointer), Search (while the Search text is not blank) or Selection. The canvas reports hovers and clicks to the store, which applies that interaction's rules; `clickable` says which Objects a click reaches, and drives the cursor.
- A Search Highlights its hits and colours them as an Object Heatmap (`HeatmapLegend`). `showResult` drops a Search response whose version is stale, so a slow Search cannot overwrite a newer one or a Selection made meanwhile.
- The camera moves only through `goHome` (whole room, clears Search, Selection and Highlight) and `focus(ids)` in `viewer/camera.ts`. A Search focuses its hits; a Selection does not move the camera, and is labelled with its Object's name on top of its box.

## Viewer

`src/components/viewer/`:

| File | Holds |
| --- | --- |
| `SceneCanvas.tsx` | the react-three-fiber canvas, controls, picking, the cursor, hover and Selection labels; renders every entry of `sceneLayers` |
| `layers/index.tsx` | `sceneLayers`: `points` (`PointCloudLayer`, `points.ply`) and `mesh` (`MeshLayer`, `mesh.glb`); repaints vertex colours for Highlight, hover and Instance Colors |
| `view.ts` | which layer shows, room bounds, home and focus poses, where a Selection's label sits, whether highlighting is available |
| `highlight.ts` | which Object owns each point (the smallest one), heatmap and dim colours, Instance Colors for hover and Selection, heatmap normalisation |
| `picking.ts` | a hidden twin of each layer coloured by Object id, read back to pick the Object under the pointer |
| `camera.ts` | `goHome`, `focus` and the driver the canvas attaches |

`src/lib/store/viewerStore.ts` holds viewer state: the Search text, Selection, Highlight, similarities, hover, Measurement points, layers, appearance, loaded bounds.

Object Membership (`src/lib/api/membership.ts`) maps each Object to its points and vertices; the viewer refuses to highlight when the membership is absent or its counts do not match the loaded geometry.

## Mock mode

With `NEXT_PUBLIC_API_MODE=mock`, `src/app/providers.tsx` starts MSW (`public/mockServiceWorker.js`) before rendering. `src/lib/api/mock/handlers.ts` serves every API path, including the SSE progress stream, with a demo Scene built in `mock/room.ts` and its membership in `mock/membership.ts`.
