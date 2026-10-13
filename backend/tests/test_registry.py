import subprocess
import sys

from scene_core.config import PipelineConfig
from scene_core.registry import Registry


def test_every_configured_algorithm_and_relation_is_installed():
    available = set(Registry().available())
    for name in ("pipeline.yaml", "pipeline.fake.yaml", "pipeline.fake-gpu.yaml"):
        pipeline = PipelineConfig.load(f"backend/config/{name}")
        assert {stage.algorithm for stage in pipeline.stages.values()} <= available, name
    graph = PipelineConfig.load("backend/config/pipeline.yaml").stages["graph"].params["relations"]
    assert set(graph) == set(Registry("scene_relations").available())


def test_listing_algorithms_does_not_import_heavy_libraries():
    code = "import sys;from scene_core.registry import Registry;Registry().available();print('torch' in sys.modules)"
    assert subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout.strip() == "False"
