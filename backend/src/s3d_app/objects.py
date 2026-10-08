"""CPU stage that turns Mask3D instances into measured Object records."""

import colorsys
import json
import sys
from pathlib import Path

import numpy as np
from plyfile import PlyData

from s3d_app.pipeline import artifact_dir
from s3d_app.storage import database


def dominant_color(rgb: np.ndarray) -> tuple[str, list[int]]:
    """Name the modal HSV color bin, preserving a representative RGB swatch."""
    if len(rgb) == 0:
        return "unknown", [128, 128, 128]
    hsv = np.asarray([colorsys.rgb_to_hsv(*(pixel / 255.0)) for pixel in rgb])
    saturation = hsv[:, 1]
    value = hsv[:, 2]
    names = np.full(len(rgb), None, dtype=object)
    names[value < 0.18] = "black"
    names[(value > 0.85) & (saturation < 0.14)] = "white"
    middle = (value >= 0.18) & (value <= 0.85)
    names[middle & (saturation < 0.14)] = "gray"
    chromatic = (names == None)
    hue = hsv[:, 0] * 360
    names[chromatic & ((hue < 15) | (hue >= 345))] = "red"
    names[chromatic & (hue >= 15) & (hue < 45)] = "orange"
    names[(names == "orange") & (value < 0.65)] = "brown"
    names[chromatic & (hue >= 45) & (hue < 70)] = "yellow"
    names[chromatic & (hue >= 70) & (hue < 165)] = "green"
    names[chromatic & (hue >= 165) & (hue < 255)] = "blue"
    names[chromatic & (hue >= 255) & (hue < 345)] = "purple"
    color = max(set(names), key=lambda name: int(np.count_nonzero(names == name)))
    sample = np.median(rgb[names == color], axis=0).astype(np.uint8).tolist()
    return str(color), sample


def best_frames(instance_ids: np.ndarray, frame_ids: np.ndarray,
                offsets: np.ndarray, indices: np.ndarray, object_id: int,
                limit: int = 5) -> list[int]:
    counts = []
    for position, frame_id in enumerate(frame_ids):
        visible = indices[offsets[position]:offsets[position + 1]]
        count = int(np.count_nonzero(instance_ids[visible] == object_id))
        if count:
            counts.append((count, int(frame_id)))
    return [frame_id for _, frame_id in sorted(counts, reverse=True)[:limit]]


def run(scene_id: str) -> None:
    target = artifact_dir(scene_id, "S4")
    if (target / "objects.json").is_file():
        return
    labels = json.loads(Path(__file__).with_name("scannet200_labels.json").read_text())
    source = artifact_dir(scene_id, "S1") / "mesh/vh_clean_2.ply"
    vertex = PlyData.read(source)["vertex"].data
    points = np.column_stack((vertex["x"], vertex["y"], vertex["z"])).astype(np.float32)
    rgb = np.column_stack((vertex["red"], vertex["green"], vertex["blue"]))
    with np.load(artifact_dir(scene_id, "S3") / "masks.npz", allow_pickle=False) as masks:
        instance_ids = masks["instance_ids"]
        label_ids = masks["labels"]
        confidences = masks["confidences"]
    with np.load(artifact_dir(scene_id, "S2") / "geometry.npz", allow_pickle=False) as geometry:
        frame_ids = geometry["frame_ids"]
        offsets = geometry["visibility_offsets"]
        indices = geometry["visibility_indices"]
    if len(points) != len(instance_ids):
        raise ValueError("S3 masks have a different vertex count")
    objects = []
    for object_id in range(len(label_ids)):
        mask = instance_ids == object_id
        if not mask.any():
            continue
        selected = points[mask]
        lower = selected.min(axis=0)
        upper = selected.max(axis=0)
        color, swatch = dominant_color(rgb[mask])
        label_id = int(label_ids[object_id])
        objects.append({"id": object_id, "label": labels[label_id],
                        "confidence": round(float(confidences[object_id]), 5),
                        "label_distribution": {labels[label_id]: round(float(confidences[object_id]), 5)},
                        "alt_labels": [], "label_source": "mask3d",
                        "center": ((lower + upper) / 2).round(4).tolist(),
                        "size": (upper - lower).round(4).tolist(),
                        "bounds": [lower.round(4).tolist(), upper.round(4).tolist()],
                        "vertices": int(mask.sum()), "color": color, "rgb": swatch,
                        "keyframes": best_frames(instance_ids, frame_ids, offsets,
                                                 indices, object_id)})
    target.mkdir(parents=True, exist_ok=True)
    partial = target / "objects.json.partial"
    partial.write_text(json.dumps(objects))
    with database() as connection:
        connection.execute("DELETE FROM objects WHERE scene_id = ?", (scene_id,))
        connection.executemany("INSERT INTO objects(scene_id, id, data, mask) VALUES (?, ?, ?, ?)",
                               ((scene_id, item["id"], json.dumps(item),
                                 np.flatnonzero(instance_ids == item["id"]).astype("<i4").tobytes())
                                for item in objects))
    partial.replace(target / "objects.json")


if __name__ == "__main__":
    run(sys.argv[1])
