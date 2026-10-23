# frontend/

React SPA with Vite, React Router, TanStack Query, Zustand, react-three-fiber and use-intl. Run npm scripts from this folder.

## Rules

- Screens reach the backend only through `sceneApi` from `src/lib/api`; no other module calls `fetch` on the API.
- API types come from `src/lib/api/types.ts`. `src/lib/api/schema.d.ts` and `openapi/openapi.json` are generated: [docs/agents/api-contract.md](../docs/agents/api-contract.md).
- Mock mode (`VITE_API_MODE=mock`) serves the same HTTP and SSE paths through MSW from `src/lib/api/mock/`; keep its handlers in step with the API.
- The UI is English only. Every user-visible string is a key in `messages/en.json`, read with `useTranslations`.
- 3D rendering goes through a layer registered in `sceneLayers` (`src/components/viewer/layers/index.tsx`). Camera moves go through `goHome` and `focus` in `src/components/viewer/camera.ts`. Viewer rules that need no WebGL live in `view.ts`, `highlight.ts` and `picking.ts`, with unit tests. Viewer state lives in `src/lib/store/viewerStore.ts`.
- Errors and fallbacks: [docs/agents/failures.md](../docs/agents/failures.md). Tests and the done check: [docs/agents/testing.md](../docs/agents/testing.md).

## Read before changing

- Routes, screens, data flow and the viewer: [docs/architecture/frontend.md](../docs/architecture/frontend.md)
