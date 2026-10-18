---
name: done-check
description: Run this repo's done check on the current changes — backend lint and tests, API contract sync, frontend typecheck/test/build, and the live-docs rule — and report pass/fail per step. Use when the user types /done-check, asks whether a change is done or ready to commit, or after finishing a ticket.
---

# Done check

Checks the working-tree changes against the done rules in [AGENTS.md](../../../AGENTS.md),
[backend/AGENTS.md](../../../backend/AGENTS.md) and [frontend/AGENTS.md](../../../frontend/AGENTS.md).
Run every command from the repository root. Do not fix anything while checking; report first, then
offer fixes.

## 1. Scope the change

Run `git status --short` and `git diff --stat HEAD`. Decide which areas changed:

- **backend**: anything under `backend/`, `main.py` or `pyproject.toml`
- **api contract**: route or pydantic model changes under `backend/services/` or `backend/packages/`
  that reach the HTTP API
- **frontend**: anything under `frontend/`

Skip the steps for an area that did not change and say so in the report.

## 2. Backend

1. `uv run main.py lint`
2. `uv run main.py test-unit`
3. `uv run main.py test` — needs Docker. If Docker is not running, mark it **skipped (no Docker)**,
   never passed.

## 3. API contract

When the api contract changed: run `uv run main.py openapi`, then `npm --prefix frontend run api:sync`,
then check `git status` for changes to `backend/openapi/openapi.json` and
`frontend/src/lib/api/schema.d.ts`. Those files changing means the contract was stale before this
check; report it.

## 4. Frontend

1. `npm --prefix frontend run typecheck`
2. `npm --prefix frontend test`
3. `npm --prefix frontend run build`
4. A visible change also needs a browser check at desktop width in mock mode (the `frontend-mock`
   entry in `.claude/launch.json`). If you cannot do it, list it as **manual check needed**.
5. Every new user-visible string is a key in both `frontend/messages/en.json` and `vi.json`.

## 5. Docs and decisions

- A behavior change updates the architecture page under `docs/architecture/` that describes it.
- A new screen or flow updates `docs/architecture/frontend.md`.
- A hard-to-reverse trade-off has a new ADR in `docs/adr/`.
- New domain words match [CONTEXT.md](../../../CONTEXT.md) and avoid its _Avoid_ words.

## Report

End with one table, one row per step: step, result (pass / fail / skipped + reason), and for a
failure the first relevant error lines. Then a one-line verdict: **done**, or **not done** with the
blocking steps listed.
