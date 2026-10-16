"""Fetch weights for every installed Algorithm of the real pipeline (not PIPELINE_CONFIG, which may select fakes) into MODELS_DIR, without loading them on a GPU."""
import os
from importlib.metadata import PackageNotFoundError

from scene_core.config import PipelineConfig
from scene_core.registry import Registry


from pathlib import Path


def _find_pipeline_config() -> str:
    candidates = [
        os.environ.get("MODELS_PIPELINE_CONFIG"),
        "backend/config/pipeline.yaml",
        "/app/backend/config/pipeline.yaml",
        str(Path(__file__).resolve().parents[4] / "config/pipeline.yaml"),
    ]
    for path in candidates:
        if path and Path(path).exists():
            return str(path)
    return os.environ.get("MODELS_PIPELINE_CONFIG", "backend/config/pipeline.yaml")


def main():
    pipeline = PipelineConfig.load(_find_pipeline_config())
    registry = Registry()
    installed = set(registry.available())
    for stage, config in pipeline.stages.items():
        if config.algorithm not in installed:
            print(f"skip {stage}: {config.algorithm} is not installed in this image")
            continue
        try:
            algorithm = registry.resolve(config.algorithm)()
        except (ImportError, PackageNotFoundError) as exc:
            print(f"skip {stage}: {config.algorithm} dependencies missing ({exc})")
            continue
        print(f"download {config.algorithm}", flush=True)
        algorithm.download_weights()


if __name__ == "__main__":
    main()
