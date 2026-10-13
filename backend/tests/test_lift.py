import json
import numpy as np
from PIL import Image
from scene_core.contracts import SceneWorkspace
from scene_stages.lift import MaskClustering


def test_two_views_of_one_mask_become_one_stable_instance(tmp_path):
    workspace = SceneWorkspace(tmp_path, "lift")
    for frame in ("0000", "0001"):
        Image.new("RGB", (16, 16), (150, 80, 20)).save(workspace.dir("recon/rgb") / f"{frame}.png")
        np.savez(workspace.dir("align/frames") / f"{frame}.npz", depth=np.ones((16, 16)), conf=np.ones((16, 16)), pose=np.eye(4), K=np.array([[16, 0, 8], [0, 16, 8], [0, 0, 1]]))
        mask = np.zeros((1, 16, 16), bool)
        mask[:, 4:12, 4:12] = True
        np.savez(workspace.dir("segment/masks") / f"{frame}.npz", masks=mask, labels=np.array(["chair"]), scores=np.array([.9]))
    manifest = MaskClustering().run(workspace, {"min_views": 2})
    instances = json.loads(workspace.path("instances/instances.json").read_text())
    assert manifest.num_instances == 1
    assert instances[0]["label"] == "chair"
    assert instances[0]["num_views"] == 2
    assert len(instances[0]["best_views"]) == 2
    assert workspace.path(f"instances/crops/{instances[0]['id']}_0.jpg").is_file()
    first_id = instances[0]["id"]
    MaskClustering().run(workspace, {"min_views": 2})
    assert json.loads(workspace.path("instances/instances.json").read_text())[0]["id"] == first_id
