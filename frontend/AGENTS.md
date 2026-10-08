# Frontend guidance

Read [root AGENTS.md](../AGENTS.md) and [current status](../docs/project-status.md)
first. Paths below are relative to `frontend/`.

## Code map

- `src/app/page.tsx`: upload, Replace and Scene list.
- `src/app/scene/page.tsx`: Scene loading, processing status and viewer/chat state.
- `src/components/SceneCanvas.tsx`: mesh, Instance/Structure highlights, bboxes,
  selection and viewer camera.
- `src/components/ChatPanel.tsx`: Session questions, streamed responses, Clarify
  and Keyframe Evidence.
- `src/lib/mesh.ts`, `sse.ts`, `highlights.ts`, `api.ts`: binary decoding, SSE
  parsing, highlighting and API URL construction.
- `src/generated/api.ts`: generated backend contract; refresh through `types:api`.

## UI and protocol rules

- Keep the Next static export deployable through FastAPI. Use browser-side API
  calls through the existing URL helper; production uses relative URLs and native
  development supplies `NEXT_PUBLIC_API_BASE_URL`.
- Upload receives prepared `.s3dpkg` files only. File selection and the full drop
  zone share upload validation and busy state. Explain v2/prep errors clearly and
  keep the user's explicit Replace choice.
- Keep UI text and questions in English (ADR 0006).
- Decode the exact [mesh.bin contract](../docs/mesh-bin.md). Packed RGB can leave
  following sections unaligned; retain safe reads/copies and original vertex order.
  Vertex Instance IDs and server Object IDs drive selection/highlighting.
- Send the current viewer camera as Viewpoint with questions (ADR 0005). Preserve
  clicked Object/Session references and backend Clarify choices across turns.
- Treat SSE as a streamed protocol: chunks can split events. Preserve handling of
  error, reset and final events so displayed wording agrees with verified results.
  Use actual server Keyframes for Evidence.

## Verification

From `frontend/`, choose relevant checks from the existing package scripts:

```powershell
npm run typecheck
npm test
npm run build
```

`build` includes the API freshness gate. An API/source change requires backend
schema export followed by `npm run types:api`; commit both generated files with
the source change. Check upload/drop, processing, camera selection or chat in the
browser when that interaction changes. Record visual checks separately from unit
tests; a screenshot failure is not evidence that visual inspection passed.
