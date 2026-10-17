# 11: Format the Python code with Ruff

**What to build:** Run `uv run tasks.py format` and the safe `ruff check --fix` rules over the
backend as one mechanical change, committed on its own so earlier diffs stay readable (REFACTORING
3.1, 3.2). No behavior change.

**Blocked by:** 10, and tickets 01–10 committed first

**Status:** implemented

- [x] Only formatting and safe autofixes; `uv run tasks.py test` passes unchanged.
- [x] Remaining `ruff check` findings listed in this ticket's Comments for later.

## Comments

- 2026-10-17: `ruff format` reformatted 46 files (the Colab notebook's code cells included) and
  `ruff check --fix` applied 40 safe fixes (import order, one import per line, `__all__` order).
  `uv run tasks.py test` passed 86 tests and the exported OpenAPI contract is unchanged.
  55 findings remain for hand fixes, none from formatting:
  - F403/F405 (33): `from .models import *` in scene_api/main.py and
    `from scene_core.contracts import *` in scene_stages/fake.py.
  - B905 (6): `zip()` without `strict=` in geometry.py, gpu.py, lift.py, mesh.py.
  - E731 (3): lambda assignments in mesh.py, scene_target/__init__.py, test_api.py.
  - B027 (2): `StageAlgorithm.setup` and `download_weights` are empty optional hooks.
  - E402 (2): imports inside Colab notebook cells, by design.
  - One each: B008 `File(...)` default (main.py), B020 `cursor` loop variable (main.py),
    B904 (server.py), F401 unused `SceneError` (scene_target), F841 (test_api.py),
    RUF005 (server.py, test_recon.py), RUF015 (test_store.py), RUF043 (test_api.py).
