# Working in this repository

Read [docs/SPEC.md](docs/SPEC.md) before implementing a ticket; it defines scope and acceptance.
For module boundaries, file contracts or compute changes, read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
Use [GLOSSARY.md](GLOSSARY.md) for domain names. For publication and database ownership, read
[ADR-0001](docs/ADR-0001-worker-publishes-scene-graph.md).

Run `uv run tasks.py --help` from the repository root for task commands. The frontend scripts live in
`frontend/package.json`. Use the agreed test seams in the spec and fake Algorithms for automated tests.
Record live GPU checks separately from local tests. The user commits changes; agents edit files only.
