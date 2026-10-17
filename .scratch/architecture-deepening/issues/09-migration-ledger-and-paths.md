# 09: Migration ledger and explicit resource paths

**What to build:** `SceneStore.migrate` applies each SQL file once, recorded in `schema_migrations`,
under a Postgres advisory lock so the api and worker can start together. The migrations and config
folders come from `MIGRATIONS_DIR` and `CONFIG_DIR` when set, else from the source layout, and a
missing folder fails with a clear message instead of silently finding nothing (audit R10,
REFACTORING 2.3).

**Blocked by:** 07

**Status:** implemented

- [x] Ledger table, one application per file, advisory lock; an existing database applies every file
      once more (all are idempotent) and then never again.
- [x] `parents[4]` lookups in scene-store and scene-target replaced by one resolver each with an
      environment override and a clear error; `.env.example` documents the variables.
- [x] Tests: migrating twice runs nothing the second time; a missing folder raises a clear error.
- [x] backend/AGENTS.md and api.md describe how migrations really run.
