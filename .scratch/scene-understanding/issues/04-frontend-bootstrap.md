# 04: Frontend bootstrap — Scene list, create and delete

**What to build:** The Next.js app wired to the backend contract: typed client generated from the committed OpenAPI file, the `SceneApi` port with HTTP and mock (MSW) implementations, i18n scaffolding (`en`, `vi`), Tailwind/shadcn, TanStack Query, and pages to list, create and delete Scenes. Runs in its own Compose project on the shared network.

**Blocked by:** 03

**Status:** done — verified in the browser against the real backend; frontend Docker image build not re-run

- [ ] With the backend up, I can create a named Scene, see it listed with its status, and delete it from the browser.
- [ ] Mock mode (`NEXT_PUBLIC_API_MODE=mock npm run dev`) shows the same pages with mock data and no backend.
- [ ] `npm run api:sync` regenerates types from the backend contract; there are no hand-written API types.
- [ ] UI strings come from message files; switching locale between `en` and `vi` works (Vietnamese strings may be partial).
- [ ] vitest + MSW tests cover listing and creating a Scene through the `SceneApi` port.
- [ ] The frontend Docker image builds and serves on localhost:3000.
