# 01: Workspace & task runner

**What to build:** Replace the `uv init` scaffold with the uv workspace described in the spec: a non-package workspace root, empty member packages for scene-core, scene-stages, scene-api, scene-worker and scene-compute, a shared dev toolchain (pytest, pytest-asyncio, httpx, ruff), and a stdlib-only Python task runner invoked through `uv` that replaces the Makefile on Windows. Prefactor ticket: makes every later ticket easy to start.

**Blocked by:** None (can start immediately)

**Status:** done

- [ ] The old `backend` scaffold package is gone; the workspace root declares all five members and `uv sync` succeeds on Windows.
- [ ] Each member package is importable from the workspace environment.
- [ ] The task runner exposes `test`, `up`, `down`, `reset`, `openapi`, `init-storage`, `disk-usage` (later tickets add more) and runs from both PowerShell and Git Bash.
- [ ] `uv run tasks.py test` runs pytest across the workspace and exits 0 with no tests yet.
- [ ] `.gitignore` covers the model cache, the git-ignored room-capture samples folder and Next.js build output.
