# Project Refactoring Audit and Roadmap

This document outlines architectural, code quality, and tooling refactoring opportunities across the `3D-scene` repository, based on a comprehensive codebase audit conducted against the repository's architectural guidelines ([AGENTS.md](../AGENTS.md), [backend/AGENTS.md](../backend/AGENTS.md), and [frontend/AGENTS.md](../frontend/AGENTS.md)).

---

## 1. Priority Matrix

| Area | Component | Priority | Complexity | Impact |
| :--- | :--- | :---: | :---: | :---: |
| **Architecture** | Decouple `scene-api` from `scene-worker` | High 🔴 | Medium | High (enforces downward-only dependency) |
| **Architecture** | Modularize `create_app` into FastAPI Routers | High 🔴 | Medium | High (maintainability, testability) |
| **Robustness** | Eliminate hardcoded `parents[4]` directory traversal | High 🔴 | Low | High (avoids packaging/runtime crashes) |
| **Code Quality** | Format compressed code & resolve 79 Ruff violations | Medium 🟡 | Low | High (readability, PEP 8 compliance) |
| **Frontend** | Clean up `http.ts` & adopt / remove unused `typedClient` | Medium 🟡 | Low | Medium (type safety, removes dead code) |
| **Developer Tools**| Add backend launch tasks to `.claude/launch.json` | Medium 🟡 | Low | Medium (developer experience) |
| **DevOps / Tasks**| Add `test-unit`, `lint`, and `format` to `tasks.py` | Medium 🟡 | Low | High (allows fast feedback without Docker) |
| **DevOps** | Consolidate 3 `compose.yaml` files into root compose | Low 🟢 | Low | Medium (single source of truth) |

---

## 2. Architecture & Module Boundaries

### 2.1 Decouple `scene-api` from `scene-worker`
* **Files**:
  * [`backend/services/scene-api/pyproject.toml`](file:///d:/repo/3D-scene/backend/services/scene-api/pyproject.toml#L5)
  * [`backend/services/scene-api/src/scene_api/main.py`](file:///d:/repo/3D-scene/backend/services/scene-api/src/scene_api/main.py#L12-L13)
* **Problem**:
  * `backend/AGENTS.md` mandates:
    > *"Packages depend downward only: `scene-core` ← `scene-stages` ← the services."*
  * `scene-api` directly imports from `scene-worker`:
    ```python
    from scene_worker.compute.http import ComputeError
    from scene_worker.repository import Repository
    from scene_worker.container import configuration, delete_remote_workspaces
    ```
* **Solution**:
  * Move shared database models and repository logic (`Repository`, schema migrations runner) into either `scene-core` or a dedicated lightweight package (`scene-db` / `scene-store`).
  * Relocate compute client abstractions (`HttpBackend`, `ComputeError`) to `scene-core` or `scene-stages`, making them accessible to both `scene-api` and `scene-worker` without cross-service dependencies.

### 2.2 Modularize `create_app()` into Domain Routers
* **File**: [`backend/services/scene-api/src/scene_api/main.py`](file:///d:/repo/3D-scene/backend/services/scene-api/src/scene_api/main.py#L18-L221)
* **Problem**:
  * `create_app` is a 200+ line monolithic factory enclosing all routes, local helpers (`public_objects`, `search`, `input_store`, `query_embedder`), inline imports (`import numpy`, `from .qa import ...`), and the SSE streaming generator.
  * Dependency injection is bypassed in favor of state lookups (`app.state.repository`) and closure variables (`repo`, `data_dir`).
* **Solution**:
  * Decompose into domain APIRouters under `backend/services/scene-api/src/scene_api/routers/`:
    * `scenes.py`: Scene creation, retrieval, file serving, raw file uploads, deletion.
    * `objects.py`: Object listing, object retrieval, vector search.
    * `events.py`: SSE stage and status streaming endpoint.
    * `qa.py`: Grounded question answering stream endpoint.
  * Utilize FastAPI `Depends()` for injecting `Repository`, `SceneWorkspace`, and `LLM`.

### 2.3 Eliminate Hardcoded `parents[4]` Relative Paths
* **Files**:
  * [`backend/services/scene-worker/src/scene_worker/repository.py: L13`](file:///d:/repo/3D-scene/backend/services/scene-worker/src/scene_worker/repository.py#L13)
  * [`backend/services/scene-worker/src/scene_worker/container.py: L32`](file:///d:/repo/3D-scene/backend/services/scene-worker/src/scene_worker/container.py#L32)
* **Problem**:
  * `Path(__file__).resolve().parents[4] / "migrations"` and `parents[4] / "config"` assume a fixed 5-level directory depth from source file to repository root. This breaks when packages are built into wheels or installed inside site-packages.
* **Solution**:
  * Use environment variables with standard fallbacks:
    ```python
    def get_migrations_dir() -> Path:
        if env := os.getenv("MIGRATIONS_DIR"):
            return Path(env)
        # Fallback to traversing upwards until pyproject.toml or backend directory is found
        curr = Path(__file__).resolve()
        for parent in curr.parents:
            if (parent / "migrations").is_dir():
                return parent / "migrations"
            if (parent / "backend" / "migrations").is_dir():
                return parent / "backend" / "migrations"
        raise RuntimeError("Migrations directory not found")
    ```

---

## 3. Code Quality & Standards

### 3.1 Un-minify Compressed Python Code
* **Files**:
  * [`scene_core/contracts.py`](file:///d:/repo/3D-scene/backend/packages/scene-core/src/scene_core/contracts.py)
  * [`scene_core/domain.py`](file:///d:/repo/3D-scene/backend/packages/scene-core/src/scene_core/domain.py)
  * [`scene_core/executor.py`](file:///d:/repo/3D-scene/backend/packages/scene-core/src/scene_core/executor.py)
  * [`scene_stages/fake.py`](file:///d:/repo/3D-scene/backend/packages/scene-stages/src/scene_stages/fake.py)
  * [`scene_worker/runner.py`](file:///d:/repo/3D-scene/backend/services/scene-worker/src/scene_worker/runner.py)
* **Problem**:
  * Extensive semicolon usage and multiple statements per line (e.g. `self.data_dir=Path(data_dir);self.registry=registry or Registry();self._instances={};self._lock=threading.RLock()`).
  * Missing blank lines between classes and functions, violating PEP 8.
* **Solution**:
  * Run `uv run ruff format .` across the workspace.

### 3.2 Resolve 79 Ruff Linter Errors
* **Command**: `uv run ruff check .`
* **Summary of Violations**:
  * **`I001` (Import sorting)**: Imports unsorted across 20+ files.
  * **`RUF012` (Mutable class attribute)**: Mutable list defaults (`reads = ["raw"]`, `writes = ["keyframes"]` in stage classes, `calls = []` in test mock handlers). Convert to `typing.ClassVar` or tuples.
  * **`B008` (Function call in default argument)**: [`main.py: L72`](file:///d:/repo/3D-scene/backend/services/scene-api/src/scene_api/main.py#L72) uses `files: list[UploadFile] = File(...)`. Refactor to `Annotated[list[UploadFile], File()]`.
  * **`LOG015` (Logging on root logger)**: Replace `logging.warning()` and `logging.exception()` in `main.py`, `runner.py`, and `container.py` with `logger = logging.getLogger(__name__)`.
  * **`F401` (Unused import)**: Unused `Relation` in [`models.py: L4`](file:///d:/repo/3D-scene/backend/services/scene-api/src/scene_api/models.py#L4).
  * **`C401` (Unnecessary generator)**: Rewrite `set(o.id for o in ...)` as set comprehension `{o.id for o in ...}` in [`runner.py: L92`](file:///d:/repo/3D-scene/backend/services/scene-worker/src/scene_worker/runner.py#L92).
  * **`BLE001` (Blind exception catch)**: Narrow broad `except Exception:` handlers in `main.py` and `server.py`.
* **Configuration**:
  * Add standard Ruff configuration in [`pyproject.toml`](file:///d:/repo/3D-scene/pyproject.toml):
    ```toml
    [tool.ruff.lint]
    select = ["E", "F", "I", "UP", "B", "RUF", "C4"]
    ignore = ["RUF012"]  # or annotate attributes with ClassVar
    ```

---

## 4. Frontend & Client API

### 4.1 Reconcile `http.ts` and `typedClient`
* **File**: [`frontend/src/lib/api/http.ts`](file:///d:/repo/3D-scene/frontend/src/lib/api/http.ts#L9-L11)
* **Problem**:
  * Line 9 exports `typedClient = createClient<paths>({ baseUrl: apiOrigin })`, but it is unused across the entire frontend.
  * `httpSceneApi` uses manual `fetch` calls with hardcoded strings (`/scenes/${id}`), duplicating routing knowledge already present in `schema.d.ts`.
  * Duplicate re-export / import:
    ```typescript
    export { ApiError } from "./errors";
    import { ApiError } from "./errors";
    ```
* **Solution**:
  * Remove redundant duplicate import statement.
  * Either migrate standard REST methods in `httpSceneApi` (`listScenes`, `createScene`, `getScene`, `deleteScene`, `listObjects`, `searchObjects`, `getMessages`) to use `typedClient` for complete compile-time type validation against OpenAPI specs, or remove `typedClient` if custom fetch wrapper is preferred.

### 4.2 Expand IDE Task Configurations
* **File**: [`.claude/launch.json`](file:///d:/repo/3D-scene/.claude/launch.json)
* **Problem**:
  * Only contains frontend runners (`frontend`, `frontend-mock`). Developers running or debugging the backend must manually type shell commands.
* **Solution**:
  * Add launch configurations for `backend-api` and `backend-worker`:
    ```json
    {
      "name": "backend-api",
      "runtimeExecutable": "uv",
      "runtimeArgs": ["run", "uvicorn", "scene_api.main:app", "--reload", "--port", "8000"],
      "port": 8000
    },
    {
      "name": "backend-worker",
      "runtimeExecutable": "uv",
      "runtimeArgs": ["run", "python", "-m", "scene_worker.main"]
    }
    ```

---

## 5. DevOps, Tasks & Infrastructure

### 5.1 Enhance `tasks.py` with Unit Tests and Linting
* **File**: [`tasks.py`](file:///d:/repo/3D-scene/tasks.py)
* **Problem**:
  * Running `uv run tasks.py test` requires a running Docker daemon because it calls `ensure_test_database()`. If Docker is stopped, the task crashes with an unhandled `subprocess.CalledProcessError`.
  * 26 backend unit tests (`test_geometry.py`, `test_mesh.py`, `test_config.py`, `test_graph.py`, `test_lift.py`, `test_attributes.py`, `test_recon.py`, `test_registry.py`, `test_compute_contract.py`, `test_ingest.py`) require no database and execute in ~9 seconds, but cannot be run without starting Docker through `tasks.py`.
* **Solution**:
  * Add a `test-unit` command:
    ```python
    def test_unit(args):
        """Run fast unit tests that require no database or GPU."""
        non_db_tests = [
            "backend/tests/test_geometry.py",
            "backend/tests/test_config.py",
            "backend/tests/test_graph.py",
            "backend/tests/test_lift.py",
            "backend/tests/test_mesh.py",
            "backend/tests/test_recon.py",
            "backend/tests/test_registry.py",
            "backend/tests/test_attributes.py",
            "backend/tests/test_compute_contract.py",
            "backend/tests/test_ingest.py",
        ]
        run(sys.executable, "-m", "pytest", *non_db_tests, *args.pytest_args)
    ```
  * Add `lint` (`uv run ruff check .`) and `format` (`uv run ruff format .`) subcommands.
  * In `ensure_test_database()`, check `docker info` first and provide a user-friendly error message if the daemon is offline.

### 5.2 Consolidate Docker Compose Configurations
* **Files**:
  * [`compose.yaml`](file:///d:/repo/3D-scene/compose.yaml) (Root)
  * [`backend/compose.yaml`](file:///d:/repo/3D-scene/backend/compose.yaml)
  * [`frontend/compose.yaml`](file:///d:/repo/3D-scene/frontend/compose.yaml)
* **Problem**:
  * Three separate compose files exist. `ROOT/compose.yaml` has the complete configuration (Postgres, API, Worker, Compute, Frontend). Maintaining three files leads to configuration drift in environment variables, network configurations, and volume bindings.
* **Solution**:
  * Treat `ROOT/compose.yaml` as the canonical Compose file.
  * Use Docker Compose profiles (e.g. `backend`, `frontend`, `local-gpu`) to selectively run subsets of services rather than keeping multiple standalone files.

---

## 6. Phased Implementation Plan

1. **Phase 1: Code Formatting & Lint Fixes (Immediate)**
   * Run automated formatting (`uv run ruff format .`).
   * Fix safe linter errors (`uv run ruff check . --fix`).
   * Clean up unused import in `models.py` and duplicate import in `http.ts`.

2. **Phase 2: Developer Experience & Tasks**
   * Add `lint`, `format`, and `test-unit` commands to `tasks.py`.
   * Add backend launch entries to `.claude/launch.json`.
   * Add user-friendly Docker status checks in `ensure_test_database()`.

3. **Phase 3: API Modularization**
   * Break down `create_app` in `main.py` into dedicated APIRouters.
   * Introduce dependency injection for repository and storage backends.

4. **Phase 4: Architectural Decoupling & Config Cleanup**
   * Move `Repository` and common database utilities out of `scene-worker` into a shared package.
   * Replace `parents[4]` lookups with environment/root-aware directory resolvers.
   * Standardize on root `compose.yaml`.
