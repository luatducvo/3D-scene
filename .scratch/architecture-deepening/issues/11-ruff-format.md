# 11: Format the Python code with Ruff

**What to build:** Run `uv run tasks.py format` and the safe `ruff check --fix` rules over the
backend as one mechanical change, committed on its own so earlier diffs stay readable (REFACTORING
3.1, 3.2). No behavior change.

**Blocked by:** 10, and tickets 01–10 committed first

**Status:** ready-for-agent

- [ ] Only formatting and safe autofixes; `uv run tasks.py test` passes unchanged.
- [ ] Remaining `ruff check` findings listed in this ticket's Comments for later.
