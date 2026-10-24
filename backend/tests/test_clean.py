"""Exercise cleanup through the CLI in disposable repositories, with an isolated uv cache."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def cleanup_cli(tmp_path):
    repository = tmp_path / "repository"
    repository.mkdir()
    shutil.copyfile(Path(__file__).resolve().parents[2] / "main.py", repository / "main.py")

    def invoke(*arguments):
        return subprocess.run(
            [sys.executable, str(repository / "main.py"), "clean", *arguments],
            cwd=repository,
            env={**os.environ, "UV_CACHE_DIR": str(tmp_path / "uv-cache")},
            capture_output=True,
            text=True,
        )

    return repository, invoke


def create_files(repository, paths):
    for relative in paths:
        path = repository / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("keep or clean", encoding="utf-8")


@pytest.mark.parametrize("target", ["python", "react"])
def test_clean_only_removes_selected_toolchain_artifacts(cleanup_cli, target):
    repository, invoke = cleanup_cli
    python_files = [
        ".ruff_cache/cache",
        "backend/.pytest_cache/cache",
        "backend/src/__pycache__/module.pyc",
        "backend/src/orphan.pyo",
    ]
    react_files = [
        "frontend/dist/index.html",
        "frontend/.next/cache/data",
        "frontend/node_modules/.cache/data",
        "frontend/node_modules/.vite/deps/data",
        "frontend/node_modules/.vite-temp/config.mjs",
        "frontend/tsconfig.tsbuildinfo",
        "frontend/next-env.d.ts",
    ]
    protected_files = [
        ".venv/lib/__pycache__/dependency.pyc",
        "venv/lib/__pycache__/dependency.pyc",
        ".git/cache.pyc",
        "backend/models/__pycache__/data.pyc",
        "backend/data/__pycache__/data.pyc",
        "backend/src/module.py",
        "backend/.env",
        "frontend/.env",
        "frontend/src/build/component.tsx",
        "frontend/src/App.tsx",
        "frontend/node_modules/react/index.js",
    ]
    create_files(repository, python_files + react_files + protected_files)

    result = invoke(target)

    assert result.returncode == 0, result.stdout + result.stderr
    removed, kept = (
        (python_files, react_files) if target == "python" else (react_files, python_files)
    )
    assert all(not (repository / path).exists() for path in removed)
    assert all((repository / path).is_file() for path in kept + protected_files)


@pytest.mark.parametrize("arguments", [(), ("unknown",)])
def test_clean_requires_an_explicit_valid_target(cleanup_cli, arguments):
    repository, invoke = cleanup_cli
    create_files(repository, [".ruff_cache/cache", "frontend/dist/index.html"])

    result = invoke(*arguments)

    assert result.returncode == 2
    assert (repository / ".ruff_cache/cache").is_file()
    assert (repository / "frontend/dist/index.html").is_file()


def test_clean_refuses_output_linked_outside_repository(cleanup_cli, tmp_path):
    repository, invoke = cleanup_cli
    external = tmp_path / "external"
    external.mkdir()
    create_files(external, ["important.txt"])
    (repository / "frontend").mkdir()
    try:
        (repository / "frontend/dist").symlink_to(external, target_is_directory=True)
    except OSError:
        pytest.skip("Creating directory symlinks is not permitted on this host")

    result = invoke("react")

    assert result.returncode != 0
    assert "outside the repository" in result.stderr
    assert (external / "important.txt").read_text(encoding="utf-8") == "keep or clean"
