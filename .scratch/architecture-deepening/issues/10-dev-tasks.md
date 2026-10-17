# 10: Development tasks and lint configuration

**What to build:** `tasks.py` gains `lint`, `format` and `test-unit`; `test` reports a stopped Docker
clearly. Tests that need Postgres carry a `db` marker, so `test-unit` runs `-m "not db"` without
Docker. Ruff rules live in `pyproject.toml`. `.claude/launch.json` gains backend api and worker
entries (REFACTORING 4.2, 5.1).

**Blocked by:** 09

**Status:** implemented

- [x] `uv run tasks.py test-unit` passes with Docker stopped; `test` still runs everything.
- [x] `uv run tasks.py test` without Docker prints how to start it instead of a traceback.
- [x] `lint` runs `ruff check`, `format` runs `ruff format`; rules configured in `pyproject.toml`.
- [x] launch.json has `backend-api` and `backend-worker`.
- [x] Root AGENTS.md Commands section lists the new tasks.

## Comments

- 2026-10-17: The launch entries use the test database (`127.0.0.1:15432`, started by
  `tasks.py test`) and the fake pipeline on the `cpu` Target, because Compose does not publish
  Postgres to the host. `ruff check` reports 259 findings, 159 of them multiple statements per line,
  which ticket 11's formatting removes. RUF012 is ignored: Algorithms declare `reads`/`writes` lists
  as class attributes that are never mutated.
