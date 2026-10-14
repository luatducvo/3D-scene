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


def test_separate_objects_seen_in_three_views_stay_separate_instances(tmp_path):
    workspace = SceneWorkspace(tmp_path, "two-objects")
    for frame in ("0000", "0001", "0002"):
        Image.new("RGB", (32, 32), (150, 80, 20)).save(workspace.dir("recon/rgb") / f"{frame}.png")
        depth = np.ones((32, 32))
        depth[:, 16:] = 2  # the second object stands one meter behind the first
        np.savez(workspace.dir("align/frames") / f"{frame}.npz", depth=depth, conf=np.ones((32, 32)), pose=np.eye(4), K=np.array([[32, 0, 16], [0, 32, 16], [0, 0, 1]]))
        masks = np.zeros((2, 32, 32), bool)
        masks[0, 8:24, 2:14] = True
        masks[1, 8:24, 18:30] = True
        np.savez(workspace.dir("segment/masks") / f"{frame}.npz", masks=masks, labels=np.array(["chair", "table"]), scores=np.array([.9, .8]))
    manifest = MaskClustering().run(workspace, {"min_views": 2})
    instances = json.loads(workspace.path("instances/instances.json").read_text())
    assert manifest.num_instances == 2
    assert sorted((item["label"], item["num_views"]) for item in instances) == [("chair", 3), ("table", 3)]
