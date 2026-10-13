# 03: Create, list and delete Scenes (backend tracer)

**What to build:** The first thin path through the backend: Postgres (with the full initial schema), scene-api with its composition root, the local file store, and the Scenes endpoints (create, list, get, delete). Runs under Docker Compose. The OpenAPI contract is exported and committed. This establishes the primary test seam (REST API against real Postgres).

**Blocked by:** 01

**Status:** done

- [ ] `uv run tasks.py up` starts Postgres and scene-api; the API docs page loads on localhost.
- [ ] Creating a Scene returns its id; it appears in the list with status `created`; getting an unknown id returns 404 with code `SCENE_NOT_FOUND` in the standard error body.
- [ ] Deleting a Scene removes its rows and its folder in the scene-data volume.
- [ ] `uv run tasks.py openapi` writes the contract file; it is committed.
- [ ] API tests exercise these behaviours over HTTP against a real Postgres started by the task runner.
- [ ] `uv run tasks.py reset` returns the system to empty while leaving the model cache alone.
