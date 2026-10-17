# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- **`CONTEXT.md`** at the repo root: the domain language.
- **`docs/adr/`**: read ADRs that touch the area you're about to work in.
- **`docs/architecture/overview.md`**: the system map; it links the page for each area.

If any of these files don't exist, **proceed silently**. Don't flag their absence; don't suggest creating them upfront. The `/domain-modeling` skill (reached via `/grill-with-docs` and `/improve-codebase-architecture`) creates them lazily when terms or decisions actually get resolved.

## File structure

Single-context repo:

```
/
├── CONTEXT.md
├── docs/
│   ├── SPEC.md
│   ├── architecture/
│   │   ├── overview.md
│   │   └── pipeline.md, compute.md, api.md, frontend.md, extending.md
│   └── adr/
│       ├── 0001-worker-publishes-scene-graph.md
│       └── 0002-...
├── backend/
└── frontend/
```

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in `CONTEXT.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, that's a signal: either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/domain-modeling`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-0005 (whole pipeline on the GPU host), but worth reopening because…_
