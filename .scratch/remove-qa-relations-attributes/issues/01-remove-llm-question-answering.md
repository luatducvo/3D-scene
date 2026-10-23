# 01: Remove LLM question answering

**What to build:** A Scene can still be uploaded, processed, searched and inspected, but there is no way to ask it a question anywhere: no "Ask scene" control or chat panel in the explorer, and no queries endpoint in the API. Highlight comes only from Search. Building the API needs no LLM, and setup asks for no LLM endpoint or keys. See the parent spec, `.scratch/remove-qa-relations-attributes/spec.md`.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] The question-answering module (agent, scene tools, scripted and OpenAI-compatible LLM clients) is deleted.
- [ ] The queries endpoint and its request, answer and stream event models are gone from the API and from the regenerated OpenAPI contract.
- [ ] The API app factory takes no LLM argument, and every caller and test is updated.
- [ ] The error codes reachable only from question answering (ungrounded answer, step limit, unconfigured LLM, Scene not ready for questions, generic QA failure) are gone from the code and the failure docs.
- [ ] The LLM environment variables are gone from the example environment file and the configuration docs.
- [ ] The frontend has no chat panel, no "Ask scene" control, no client method for asking a question and no mock handler for it. Translation strings used only by them are removed.
- [ ] The viewer store knows only Search as a source of Highlighted results.
- [ ] The frontend's generated API types are synced from the new contract.
- [ ] The API, testing and extending docs no longer describe question answering, QA tools or the scripted LLM.
- [ ] QA tests in the API and HTTP-client suites are deleted. The remaining API tests (publish and rerun, Search, failed reprocess) still pass through the app factory and the Worker.
- [ ] Done check passes: `uv run main.py lint`, `uv run main.py test`, `uv run main.py openapi`, `npm run api:sync`, `npm run typecheck`, `npm test`, `npm run build`.
