# Testing and the done check

## Done check

Run the checks for what the change touches, from the directory shown, before calling it done:

| Change touches | Run |
| --- | --- |
| `backend/`, `main.py`, `pyproject.toml` | `uv run main.py lint`, then `uv run main.py test` (repository root) |
| `frontend/` | `npm run typecheck`, `npm test`, `npm run build` (`frontend/`) |
| an API route or model | both rows above, after regenerating the contract ([api-contract.md](api-contract.md)) |

Without Docker, run `uv run main.py test-unit` instead of `test`, and say in the report that the database tests did not run. Report failures with their output.

## Backend tests

- Tests live in `backend/tests/`, one file per module or Stage (`test_<area>.py`).
- Automated tests never need a GPU, model weights, or a network service. They select Fake Algorithms through `backend/config/pipeline.fake.yaml`.
- A test that needs Postgres sets `pytestmark = pytest.mark.db` and reads `TEST_DATABASE_URL`. `main.py test` recreates the `scene-test-db` container on port 15432 from `backend/migrations/001_init.sql` and sets that variable; `test-unit` skips the `db` marker.
- Build systems under test through their constructor seams rather than patching:
  - `scene_api.main.create_app(database_url, data_dir, pipeline, compute, target)`
  - `scene_worker.runner.Worker(database_url, data_dir, pipeline, compute, target)`
  - `scene_target.open_target_workspace(data_dir, pipeline, compute, client=...)`, where `client` is an HTTP client for an in-memory `scene_compute.server.create_app(...)`, to test the HTTP Target without a network (see `test_target.py`).
- A Fake Algorithm takes `fail`, `fail_code`, `delay` and `progress_steps` params to script failures and progress.
- Test real Algorithms on small synthetic arrays and files; checks on real models and GPUs are manual and stay out of the suite.

## Frontend tests

- Vitest, with each test beside its module as `*.test.ts(x)`.
- Keep rules testable without WebGL: viewer logic lives in plain modules (`view.ts`, `highlight.ts`, `picking.ts`) with unit tests; components get tests for behaviour, not markup.
- To see the UI without a backend, run `NEXT_PUBLIC_API_MODE=mock npm run dev`: MSW serves the API's paths, including SSE, from `src/lib/api/mock/`.
