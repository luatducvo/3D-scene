"""Fetch weights for every installed Algorithm of the real pipeline (not PIPELINE_CONFIG, which may select fakes) into MODELS_DIR, without loading them on a GPU."""

import os
from importlib.metadata import PackageNotFoundError
from pathlib import Path

from scene_core.config import PipelineConfig
from scene_core.registry import Registry
from scene_core.resources import backend_folder


def main():
    pipeline_path = (
        Path(os.environ["MODELS_PIPELINE_CONFIG"])
        if os.getenv("MODELS_PIPELINE_CONFIG")
        else backend_folder("config", "CONFIG_DIR") / "pipeline.yaml"
    )
    pipeline = PipelineConfig.load(pipeline_path)
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
