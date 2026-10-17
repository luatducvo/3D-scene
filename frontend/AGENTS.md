# Working in frontend/

The root [AGENTS.md](../AGENTS.md) applies here too. Run npm scripts from this directory.
[frontend.md](../docs/architecture/frontend.md) is the source map: which file holds each screen,
the `SceneApi` port, viewer layers and the user flow.

## Rules

- The UI follows the Figma design and the user's later decisions, which override SPEC's interface
  stories: desktop web only, no Object list, no evidence photos, no suggested questions. Keep
  evidence fields in the data and out of the rendered UI.
- Screens talk to the backend through `SceneApi` from `src/lib/api`. Mock mode
  (`NEXT_PUBLIC_API_MODE=mock`) runs the same HTTP and SSE paths through MSW, so UI work and
  browser checks need no backend or GPU.
- Every user-visible string is a key in both `messages/en.json` and `messages/vi.json`.
- `src/lib/api/schema.d.ts` and `openapi/openapi.json` come from `npm run api:sync`, which copies
  the backend's committed contract. Schema type names follow the backend's pydantic model names.
- 3D rendering changes go through a layer in `sceneLayers`
  ([layers/index.tsx](src/components/viewer/layers/index.tsx)); search and chat only write
  `highlightedIds` to the viewer store.

## Done

A change is done when `npm run typecheck`, `npm test` and `npm run build` pass, and a visible change
has been checked in the browser at desktop width (mock mode is enough). A new screen or flow
updates [frontend.md](../docs/architecture/frontend.md).
