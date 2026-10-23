# 01: Interactive explorer test harness

**What to build:** The Scene explorer can be tested the way a user drives it: rendered in a DOM against the mock API, with buttons pressed and switches flipped, while the WebGL canvas is replaced by a stub. Canvas clicks and hovers are simulated through the viewer store. Nothing the user sees changes; the harness is proven by one test of today's behaviour. See the parent spec, `.scratch/unify-viewer-display/spec.md`.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] A DOM test environment (jsdom with React Testing Library) is added as dev dependencies and applies only to the interactive component tests; the existing static-markup and pure-module tests keep running as before.
- [ ] The explorer renders in a test with the translation and query providers, the mock API served through the existing MSW handlers, and the viewer store reset between tests.
- [ ] The 3D canvas is replaced by a stub in these tests, so no WebGL is needed.
- [ ] One test presses today's Points and Mesh buttons and asserts which geometry mode is shown, proving the harness end to end.
- [ ] Done check passes: `npm run typecheck`, `npm test`, `npm run build` in `frontend/`.
