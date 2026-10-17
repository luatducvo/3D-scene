import json

import numpy as np
import pytest
from PIL import Image
from scene_core.contracts import SceneWorkspace
from scene_stages.lift import MaskClustering, merge_same_label, unproject, view_support


def test_two_views_of_one_mask_become_one_stable_instance(tmp_path):
    workspace = SceneWorkspace(tmp_path, "lift")
    for frame in ("0000", "0001"):
        Image.new("RGB", (16, 16), (150, 80, 20)).save(workspace.dir("recon/rgb") / f"{frame}.png")
        np.savez(
            workspace.dir("align/frames") / f"{frame}.npz",
            depth=np.ones((16, 16)),
            conf=np.ones((16, 16)),
            pose=np.eye(4),
            K=np.array([[16, 0, 8], [0, 16, 8], [0, 0, 1]]),
        )
        mask = np.zeros((1, 16, 16), bool)
        mask[:, 4:12, 4:12] = True
        np.savez(
            workspace.dir("segment/masks") / f"{frame}.npz",
            masks=mask,
            labels=np.array(["chair"]),
            scores=np.array([0.9]),
        )
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


def pairwise_support(points, frame, mask, tolerance):
    """The per-pair definition view_support must reproduce: project one node into another's Frame."""
    camera = (points - frame["pose"][:3, 3]) @ frame["pose"][:3, :3]
    projected = camera @ frame["K"].T
    front = camera[:, 2] > 1e-6
    pixels = np.zeros((len(points), 2), dtype=int)
    pixels[front] = np.rint(projected[front, :2] / projected[front, 2:3]).astype(int)
    h, w = mask.shape
    visible = (
        front & (pixels[:, 0] >= 0) & (pixels[:, 0] < w) & (pixels[:, 1] >= 0) & (pixels[:, 1] < h)
    )
    x, y = pixels[visible].T
    observed = frame["depth"][y, x]
    agree = (
        np.isfinite(observed) & (observed > 0) & (abs(observed - camera[visible, 2]) <= tolerance)
    )
    return float(mask[y[agree], x[agree]].mean()) if agree.any() else 0.0


def test_view_support_matches_the_per_pair_projection(tmp_path):
    rng = np.random.default_rng(3)
    frames = {}
    for index in range(4):
        depth = rng.uniform(0.8, 1.6, (24, 32))
        depth[rng.random((24, 32)) < 0.1] = np.nan
        angle = 0.08 * index
        pose = np.eye(4)
        pose[:3, :3] = [
            [np.cos(angle), 0, np.sin(angle)],
            [0, 1, 0],
            [-np.sin(angle), 0, np.cos(angle)],
        ]
        pose[:3, 3] = [0.05 * index, 0, 0]
        frames[f"{index:04d}"] = {
            "depth": depth,
            "pose": pose,
            "K": np.array([[30.0, 0, 16], [0, 30.0, 12], [0, 0, 1]]),
        }
    nodes = []
    for frame_id, frame in frames.items():
        for _ in range(3):
            mask = np.zeros((24, 32), bool)
            top, left = rng.integers(0, 14), rng.integers(0, 20)
            mask[top : top + 10, left : left + 12] = True
            points = unproject(frame["depth"], frame["K"], frame["pose"], mask)
            nodes.append({"frame": frame_id, "mask": mask, "points": points})
    support = view_support(nodes, frames, 0.3)
    for i, a in enumerate(nodes):
        for j, b in enumerate(nodes):
            expected = (
                0.0
                if a["frame"] == b["frame"]
                else pairwise_support(a["points"], frames[b["frame"]], b["mask"], 0.3)
            )
            assert support[i, j] == pytest.approx(expected)
    assert 0 < support.max() <= 1


def test_separate_objects_seen_in_three_views_stay_separate_instances(tmp_path):
    workspace = SceneWorkspace(tmp_path, "two-objects")
    for frame in ("0000", "0001", "0002"):
        Image.new("RGB", (32, 32), (150, 80, 20)).save(workspace.dir("recon/rgb") / f"{frame}.png")
        depth = np.ones((32, 32))
        depth[:, 16:] = 2  # the second object stands one meter behind the first
        np.savez(
            workspace.dir("align/frames") / f"{frame}.npz",
            depth=depth,
            conf=np.ones((32, 32)),
            pose=np.eye(4),
            K=np.array([[32, 0, 16], [0, 32, 16], [0, 0, 1]]),
        )
        masks = np.zeros((2, 32, 32), bool)
        masks[0, 8:24, 2:14] = True
        masks[1, 8:24, 18:30] = True
        np.savez(
            workspace.dir("segment/masks") / f"{frame}.npz",
            masks=masks,
            labels=np.array(["chair", "table"]),
            scores=np.array([0.9, 0.8]),
        )
    manifest = MaskClustering().run(workspace, {"min_views": 2})
    instances = json.loads(workspace.path("instances/instances.json").read_text())
    assert manifest.num_instances == 2
    assert sorted((item["label"], item["num_views"]) for item in instances) == [
        ("chair", 3),
        ("table", 3),
    ]


def test_device_cuda_without_cupy_or_a_gpu_fails_instead_of_falling_back():
    from scene_core.errors import SceneError
    from scene_stages.arrays import array_module

    assert array_module({}) is np
    try:
        import cupy  # noqa: F401
    except ImportError:
        with pytest.raises(SceneError) as error:
            array_module({"device": "cuda"})
        assert error.value.code == "GPU_REQUIRED"
    with pytest.raises(ValueError):
        array_module({"device": "tpu"})


def write_frames(workspace, frame_masks, size=32):
    """Write Frames seen from one camera at 1 m; frame_masks[frame] = [(label, score, mask)]."""
    for frame, masks in frame_masks.items():
        Image.new("RGB", (size, size), (150, 80, 20)).save(
            workspace.dir("recon/rgb") / f"{frame}.png"
        )
        np.savez(
            workspace.dir("align/frames") / f"{frame}.npz",
            depth=np.ones((size, size)),
            conf=np.ones((size, size)),
            pose=np.eye(4),
            K=np.array([[size, 0, size / 2], [0, size, size / 2], [0, 0, 1]]),
        )
        np.savez(
            workspace.dir("segment/masks") / f"{frame}.npz",
            masks=np.stack([mask for _, _, mask in masks]),
            labels=np.array([label for label, _, _ in masks]),
            scores=np.array([score for _, score, _ in masks]),
        )


def region(top, left, bottom, right, size=32):
    mask = np.zeros((size, size), bool)
    mask[top:bottom, left:right] = True
    return mask


def seat_and_chair(seat_label):
    # Frame 0 sees the whole chair, frame 1 only its seat: a quarter of the chair falls inside the
    # seat, too little for view consensus to join them, but every seat point lies on the chair.
    chair, seat = region(4, 8, 28, 24), region(20, 8, 26, 24)
    return {"0000": [("office chair", 0.9, chair)], "0001": [(seat_label, 0.8, seat)]}


def test_same_label_instances_from_different_frames_merge_into_one(tmp_path):
    workspace = SceneWorkspace(tmp_path, "nested")
    write_frames(workspace, seat_and_chair("office chair"))
    unmerged = MaskClustering().run(workspace, {"min_views": 1, "merge_overlap": 1.0})
    assert unmerged.num_instances == 2

    manifest = MaskClustering().run(workspace, {"min_views": 1, "merge_overlap": 0.5})
    instances = json.loads(workspace.path("instances/instances.json").read_text())
    assert manifest.num_instances == 1
    assert instances[0]["label"] == "office chair"
    assert instances[0]["num_views"] == 2
    assert instances[0]["score"] == pytest.approx(0.9)
    # Best views recompute over the merged members: the larger, higher-scoring chair view first.
    assert [view["frame_id"] for view in instances[0]["best_views"]] == ["0000", "0001"]
    # With min_views 2 neither part alone would survive; merged, the chair does.
    assert MaskClustering().run(workspace, {"min_views": 2}).num_instances == 1


def test_a_contained_instance_with_another_label_stays_its_own(tmp_path):
    workspace = SceneWorkspace(tmp_path, "part")
    write_frames(workspace, seat_and_chair("cushion"))
    MaskClustering().run(workspace, {"min_views": 1, "merge_overlap": 0.5})
    instances = json.loads(workspace.path("instances/instances.json").read_text())
    assert sorted(item["label"] for item in instances) == ["cushion", "office chair"]


def test_adjacent_same_label_chairs_stay_separate(tmp_path):
    workspace = SceneWorkspace(tmp_path, "adjacent")
    left, right = region(8, 2, 24, 17), region(8, 17, 24, 30)
    write_frames(
        workspace,
        {frame: [("chair", 0.9, left), ("chair", 0.8, right)] for frame in ("0000", "0001")},
    )
    # 4 cm voxels are wider than a pixel at 1 m, so the touching chairs share a column of voxels.
    manifest = MaskClustering().run(
        workspace, {"min_views": 2, "merge_overlap": 0.5, "voxel_size_m": 0.04}
    )
    instances = json.loads(workspace.path("instances/instances.json").read_text())
    assert manifest.num_instances == 2
    assert [item["num_views"] for item in instances] == [2, 2]


def test_merge_same_label_takes_the_highest_overlap_first_and_repeats():
    def cells(*xs):
        return np.array([[x, 0, 0] for x in xs])

    groups = merge_same_label(
        [{0}, {1}, {2}, {3}],
        ["chair", "chair", "chair", "lamp"],
        [cells(0, 1, 2, 3), cells(2, 3, 4, 5), cells(4, 5, 6, 7), cells(0, 1, 2, 3)],
        0.4,
    )
    # 0 and 1 share half of each; merged, they hold half of 2; the lamp never joins.
    assert groups == [{0, 1, 2}, {3}]
    # Exactly half is not more than half.
    assert merge_same_label([{0}, {1}], ["chair"] * 2, [cells(0, 1), cells(1, 2)], 0.5) == [
        {0},
        {1},
    ]


def test_merge_overlap_outside_zero_to_one_is_rejected(tmp_path):
    from scene_core.errors import SceneError

    with pytest.raises(SceneError) as error:
        MaskClustering().run(SceneWorkspace(tmp_path, "bad"), {"merge_overlap": 1.5})
    assert error.value.code == "INVALID_PARAMETERS"
