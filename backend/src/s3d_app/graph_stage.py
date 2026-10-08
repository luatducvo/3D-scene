"""Build and cache a deterministic Scene graph in a CPU subprocess."""

import json
import sys

from s3d_app.pipeline import artifact_dir
from s3d_app.scene_graph import build_graph
from s3d_app.solver import ObjectNode


def run(scene_id: str) -> None:
    target = artifact_dir(scene_id, "S5")
    if (target / "graph.json").is_file():
        return
    objects = json.loads((artifact_dir(scene_id, "S4") / "objects.json").read_text())
    structures = json.loads((artifact_dir(scene_id, "S2") / "structures.json").read_text())
    nodes = [ObjectNode(id=item["id"], label=item["label"],
                        confidence=item["confidence"], center=tuple(item["center"]),
                        size=tuple(item["size"]), color=item["color"],
                        alt_labels=tuple(item["alt_labels"]),
                        keyframes=tuple(item["keyframes"])) for item in objects]
    graph = build_graph(scene_id, nodes, structures)
    target.mkdir(parents=True, exist_ok=True)
    partial = target / "graph.json.partial"
    partial.write_text(json.dumps(graph))
    partial.replace(target / "graph.json")


if __name__ == "__main__":
    run(sys.argv[1])
