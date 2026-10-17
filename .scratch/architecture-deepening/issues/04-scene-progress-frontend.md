# 04: Scene progress hook and one api client

**What to build:** A `useSceneProgress(sceneId)` hook that owns folding Stage Run replay and live
SSE events into per-Stage state, and invalidates the Scene query when a terminal status arrives.
Today this logic is written inline in `app/[locale]/scenes/[sceneId]/page.tsx:45-77` and is not
tested. In the same change, remove the fake `SceneApi` port and make `sceneApi` use `typedClient`
with one error decoder. See [spec](../spec.md#scene-progress-in-the-frontend-ticket-04).

**Blocked by:** 02

**Status:** implemented

- [x] `useSceneProgress` returns per-Stage state; page.tsx contains no event folding. (The Scene
      status comes from the Scene query, which the hook refetches on a terminal status.)
- [ ] Hook tests use renderHook and MSW streaming a replay followed by live events, including
      progress before a Stage's first live `stage` event and a terminal `status`. — Partly: the
      MSW cases run against `watchSceneProgress`, not renderHook; see Comments.
- [x] `mockSceneApi`, `NEXT_PUBLIC_API_MODE` and the port indirection are removed. MSW remains the
      mock.
- [x] `sceneApi` requests go through `typedClient`. One error decoder replaces the three parsers and
      their three fallback codes. The XHR upload uses it too.
- [x] Backend `stage` fields are a `Literal` built from scene-core `STAGES`. The frontend `STAGES`
      constant is shared by StageStepper and the mock handlers and fails type-checking if it differs
      from the schema enum.
- [x] `uv run tasks.py openapi`, `npm run api:sync`, then the frontend done check passes.
      docs/architecture/frontend.md updated.

## Comments

- 2026-10-17: The hook's tests drive `watchSceneProgress`, the module behind `useSceneProgress`,
  with MSW streams in node; renderHook would need jsdom and testing-library, which the project does
  not install, and jsdom has no EventSource. `subscribeProgress` therefore reads the stream with
  `fetch` and the shared SSE reader, reconnecting after 1 s while the Scene processes.
  `port.ts` became `types.ts`; `NEXT_PUBLIC_API_MODE` now only decides whether MSW starts.
