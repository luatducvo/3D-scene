"""Download and verify pinned model assets."""

import hashlib
import json
import os
import shutil
import urllib.request
from pathlib import Path


def model_root() -> Path:
    return Path(os.getenv("S3D_MODEL_DIR", Path.cwd() / "models"))


def lock_path() -> Path:
    return Path(os.getenv("S3D_MODELS_LOCK", Path(__file__).resolve().parents[3] / "models.lock"))


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def pull_models(lock: Path | None = None, destination: Path | None = None) -> list[str]:
    manifest = json.loads((lock or lock_path()).read_text())
    if manifest.get("format_version") != 1:
        raise ValueError("Unsupported models.lock format")
    root = destination or model_root()
    root.mkdir(parents=True, exist_ok=True)
    downloaded = []
    for model in manifest["models"]:
        name = model["name"]
        if Path(name).name != name:
            raise ValueError(f"Invalid model file name: {name}")
        path = root / name
        expected = model["sha256"]
        if path.exists():
            if file_hash(path) != expected:
                raise ValueError(f"SHA-256 mismatch for existing model: {name}")
            continue
        partial = root / (name + ".partial")
        try:
            with urllib.request.urlopen(model["url"], timeout=60) as source, partial.open("wb") as output:
                shutil.copyfileobj(source, output, 1024 * 1024)
            if file_hash(partial) != expected:
                raise ValueError(f"SHA-256 mismatch after download: {name}")
            partial.replace(path)
            downloaded.append(name)
        finally:
            partial.unlink(missing_ok=True)
    return downloaded
