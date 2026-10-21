# Remove stored questions and answers

Status: ready-for-agent

Each question is independent and answers are no longer stored: nothing calls `SceneStore.save_exchange`, so the `messages` table never gains rows and `GET /api/v1/scenes/{scene_id}/messages` only returns exchanges stored by older code. The frontend never calls it. Remove the whole path; under `docs/agents/failures.md`, reading data written by older code is not kept alive.

## Scope

Backend:

- `SceneStore.save_exchange` in `backend/packages/scene-store/src/scene_store/__init__.py`, and "chat state" in the module docstring.
- The `list_messages` route and the `Message` import in `scene_api/main.py`; the `Message` model in `scene_api/models.py`.
- The next numbered migration in `backend/migrations/` (`002_drop_messages.sql` unless another issue took 002): `DROP TABLE IF EXISTS messages;`.
- Tests:
  - delete `test_an_answered_question_is_stored_as_one_exchange` in `test_store.py`;
  - in `test_api.py`, rewrite `test_grounded_qa_is_independent_and_preserves_only_old_messages` without `save_exchange` and `/messages`: ask two questions in turn and assert the LLM's messages for the second contain nothing from the first, and that the system prompt asks for English. Rename it to `test_grounded_qa_answers_each_question_independently`.
- Regenerate the contract: `uv run main.py openapi`, then `npm run api:sync` in `frontend/`.

Frontend:

- `sceneApi.getMessages` in `src/lib/api/http.ts`.
- The `messages` map and the `GET /:id/messages` handler in `src/lib/api/mock/handlers.ts`.

Docs:

- `docs/architecture/api.md`: the `/messages` endpoint row, the "Answers are not stored" bullet, and the `messages` row of the Database table.

## Done when

- `git grep -n -E "save_exchange|getMessages|/messages|\bMessage\b"` finds nothing in `backend/` or `frontend/src/` apart from LLM chat payloads in `qa.py` and `attributes.py`.
- The done check in `docs/agents/testing.md` passes for backend and frontend.
