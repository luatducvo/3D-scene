# Working in this repository

Photos of a room become a metric 3D Scene with Objects, a Scene Graph and grounded question
answering. The backend is one uv workspace: `pyproject.toml`, `uv.lock` and `tasks.py` sit at the
repository root, code under `backend/`. The frontend is a Next.js app in `frontend/`.

## Read before you work

- **Any ticket:** [docs/SPEC.md](docs/SPEC.md) for scope and acceptance. ADRs in
  [docs/adr/](docs/adr/) amend it where their status line says so (0004, 0005).
- **Unfamiliar code or a cross-module change:** [docs/architecture/overview.md](docs/architecture/overview.md),
  then the page for the area:
  [pipeline](docs/architecture/pipeline.md) (Stages, Workspace, Job runner, Publication),
  [compute](docs/architecture/compute.md) (Targets, compute contract, GPU image, providers),
  [api](docs/architecture/api.md) (endpoints, SSE, lifecycle rules, schema, QA agent),
  [frontend](docs/architecture/frontend.md),
  [extending](docs/architecture/extending.md) (new Algorithm, Relation, QA tool, layer, provider).
- **Naming a domain concept:** [CONTEXT.md](CONTEXT.md); use its terms, never its _Avoid_ words.
- **GPU adapters or a live run:** [docs/GPU-INTEGRATION.md](docs/GPU-INTEGRATION.md).

## Commands

`uv run tasks.py --help` from the repository root lists every task. `uv run tasks.py test` runs
pytest against a disposable Postgres container, so Docker must be running; extra arguments go to
pytest. Frontend scripts are in `frontend/package.json`; its validation sequence is in
[frontend/README.md](frontend/README.md).

## Rules

- Test through the agreed seams in SPEC with fake Algorithms (`*.fake`) and `ScriptedLLM`; automated
  tests never need a GPU. Record live GPU checks in the GPU-INTEGRATION live check log, separately
  from local test results.
- After changing API routes or models, run `uv run tasks.py openapi`, then `npm run api:sync` in
  `frontend/`. `frontend/src/lib/api/schema.d.ts` is generated.
- Repository text is English (code, comments, logs, API messages, docs); only
  `frontend/messages/*.json` is localized.
- Keep docs live: a behavior change updates the architecture page that describes it in the same
  change. A hard-to-reverse, surprising trade-off gets the next ADR number in `docs/adr/`.
- The user commits changes; agents edit files only.

## Agent skills

### Issue tracker

Issues live as local markdown files under `.scratch/<feature>/issues/`. See `docs/agents/issue-tracker.md`.

### Triage labels

Default five triage roles plus this repo's delivery states, recorded on the `**Status:**` line. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` plus ADRs in `docs/adr/`. See `docs/agents/domain.md`.
