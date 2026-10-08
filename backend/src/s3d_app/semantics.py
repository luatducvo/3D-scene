"""YOLOE multi-view labels and MobileCLIP2 crop features in one-shot GPU stages."""

import json
import os
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image

from s3d_app.models import model_root
from s3d_app.objects import run as build_objects
from s3d_app.pipeline import artifact_dir
from s3d_app.storage import database


def vote_labels(votes: list[tuple[str, float, float, str]]) -> dict:
    totals: dict[str, float] = defaultdict(float)
    for label, confidence, coverage, source in votes:
        totals[label] += confidence * coverage * (0.35 if source == "prompt-free" else 1.0)
    ordered = sorted(totals.items(), key=lambda item: (-item[1], item[0]))
    denominator = sum(totals.values())
    return {label: round(score / denominator, 5) for label, score in ordered} if denominator else {}


def rofa_average(features: np.ndarray, threshold: float = -3.0) -> np.ndarray:
    features = features.astype(np.float32)
    features /= np.maximum(np.linalg.norm(features, axis=1, keepdims=True), 1e-8)
    mean = features.mean(axis=0)
    mean /= max(float(np.linalg.norm(mean)), 1e-8)
    similarities = features @ mean
    spread = float(similarities.std())
    keep = np.ones(len(features), dtype=bool) if spread < 1e-6 else (
        (similarities - similarities.mean()) / spread >= threshold)
    average = features[keep].mean(axis=0)
    return average / max(float(np.linalg.norm(average)), 1e-8)


def project(points: np.ndarray, pose: np.ndarray, intrinsic: np.ndarray,
            width: int, height: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    camera = (points - pose[:3, 3]) @ pose[:3, :3]
    valid = camera[:, 2] > 0.01
    safe_z = np.maximum(camera[:, 2], 0.01)
    u = np.rint(intrinsic[0, 0] * camera[:, 0] / safe_z + intrinsic[0, 2]).astype(np.int32)
    v = np.rint(intrinsic[1, 1] * camera[:, 1] / safe_z + intrinsic[1, 2]).astype(np.int32)
    valid &= (u >= 0) & (v >= 0) & (u < width) & (v < height)
    return u, v, valid


def persist(scene_id: str, objects: list[dict]) -> None:
    target = artifact_dir(scene_id, "S4")
    partial = target / "objects.json.partial"
    partial.write_text(json.dumps(objects))
    with database() as connection:
        for item in objects:
            connection.execute("UPDATE objects SET data = ? WHERE scene_id = ? AND id = ?",
                               (json.dumps(item), scene_id, item["id"]))
    partial.replace(target / "objects.json")


def label_scene(scene_id: str) -> None:
    import open_clip
    import torch
    from ultralytics import YOLOE

    build_objects(scene_id)
    target = artifact_dir(scene_id, "S4")
    if (target / "labels.complete").is_file():
        return
    source = artifact_dir(scene_id, "S1")
    objects = json.loads((target / "objects.json").read_text())
    labels = json.loads(Path(__file__).with_name("scannet200_labels.json").read_text())
    calibration = json.loads((source / "calib/intrinsics.json").read_text())
    intrinsic = np.asarray(calibration["color"]["intrinsic"])
    with np.load(artifact_dir(scene_id, "S3") / "masks.npz") as masks:
        instance_ids = masks["instance_ids"]
    with np.load(artifact_dir(scene_id, "S2") / "geometry.npz") as geometry:
        points = geometry["points"]
        frame_ids = geometry["frame_ids"]
        offsets = geometry["visibility_offsets"]
        indices = geometry["visibility_indices"]
    frame_positions = {int(fid): index for index, fid in enumerate(frame_ids)}
    needed_frames = sorted({fid for item in objects for fid in item["keyframes"][:5]})
    projection = {}
    for fid in needed_frames:
        position = frame_positions[fid]
        visible = indices[offsets[position]:offsets[position + 1]]
        image_path = source / "frames/color" / f"{fid:06d}.jpg"
        image = Image.open(image_path).convert("RGB")
        pose = np.loadtxt(source / "frames/pose" / f"{fid:06d}.txt")
        u, v, valid = project(points[visible], pose, intrinsic, image.width, image.height)
        ids = instance_ids[visible]
        projection[fid] = (u[valid], v[valid], ids[valid], image.width, image.height)
        for item in objects:
            if fid not in item["keyframes"][:5]:
                continue
            selected = valid & (ids == item["id"])
            if int(selected.sum()) < 10:
                continue
            x0, x1 = int(u[selected].min()), int(u[selected].max())
            y0, y1 = int(v[selected].min()), int(v[selected].max())
            padding = max(5, int(max(x1 - x0, y1 - y0) * 0.05))
            crop = image.crop((max(0, x0 - padding), max(0, y0 - padding),
                               min(image.width, x1 + padding + 1), min(image.height, y1 + padding + 1)))
            directory = target / "crops" / str(item["id"])
            directory.mkdir(parents=True, exist_ok=True)
            crop.save(directory / f"{fid:06d}.jpg", quality=90)
    all_votes: dict[int, list] = defaultdict(list)
    tokenizer = open_clip.get_tokenizer("MobileCLIP2-B")
    encoder = torch.jit.load(str(model_root() / "mobileclip2_b.ts"), map_location="cpu").eval()
    with torch.inference_mode():
        features = torch.cat([encoder(tokens) for tokens in tokenizer(labels).split(32)]).cuda()
    del encoder
    for source_name, filename in (("text-prompt", "yoloe-26l-seg.pt"),
                                  ("prompt-free", "yoloe-26l-seg-pf.pt")):
        model = YOLOE(str(model_root() / filename)).to("cuda")
        if source_name == "text-prompt":
            with torch.inference_mode():
                embeddings = model.model.model[-1].get_tpe(features.unsqueeze(0))
            model.set_classes(labels, embeddings)
        for fid in needed_frames:
            image_path = source / "frames/color" / f"{fid:06d}.jpg"
            result = model.predict(str(image_path), imgsz=int(os.getenv("S3D_IMAGE_SIZE", "640")), device=0, half=True,
                                   conf=0.15, max_det=100, verbose=False)[0]
            u, v, ids, width, height = projection[fid]
            boxes = result.boxes
            if boxes is None:
                continue
            for detection in range(len(boxes)):
                x0, y0, x1, y1 = boxes.xyxy[detection].cpu().numpy()
                hits = (u >= x0) & (u <= x1) & (v >= y0) & (v <= y1)
                if result.masks is not None:
                    mask = result.masks.data[detection].cpu().numpy()
                    hits &= mask[np.minimum((v * mask.shape[0] / height).astype(int), mask.shape[0] - 1),
                                 np.minimum((u * mask.shape[1] / width).astype(int), mask.shape[1] - 1)] > 0.5
                label = result.names[int(boxes.cls[detection])]
                confidence = float(boxes.conf[detection])
                for item in objects:
                    if fid not in item["keyframes"][:5]:
                        continue
                    visible_count = int(np.count_nonzero(ids == item["id"]))
                    count = int(np.count_nonzero(hits & (ids == item["id"])))
                    if visible_count and count:
                        all_votes[item["id"]].append((label, confidence,
                                                       count / visible_count, source_name))
        del model
        torch.cuda.empty_cache()
    for item in objects:
        distribution = vote_labels(all_votes[item["id"]])
        if distribution:
            ranked = list(distribution)
            item.update(label=ranked[0], confidence=distribution[ranked[0]],
                        label_distribution=distribution, alt_labels=ranked[1:4],
                        label_source="yoloe-multiview")
    persist(scene_id, objects)
    (target / "labels.complete").write_text(json.dumps({"frames": len(needed_frames),
        "peak_torch_reserved_mb": round(torch.cuda.max_memory_reserved() / 1048576)}))


def embed_scene(scene_id: str) -> None:
    import open_clip
    import torch

    target = artifact_dir(scene_id, "S4")
    if (target / "embeddings.npz").is_file():
        return
    objects = json.loads((target / "objects.json").read_text())
    model, _, preprocess = open_clip.create_model_and_transforms(
        "MobileCLIP2-B", pretrained=str(model_root() / "mobileclip2_b.pt"),
        image_mean=(0, 0, 0), image_std=(1, 1, 1))
    model = model.eval().cuda()
    vectors, object_ids = [], []
    for item in objects:
        paths = sorted((target / "crops" / str(item["id"])).glob("*.jpg"))[:5]
        if not paths:
            continue
        batch = torch.stack([preprocess(Image.open(path).convert("RGB")) for path in paths]).cuda()
        with torch.inference_mode(), torch.autocast("cuda"):
            features = model.encode_image(batch, normalize=True).float().cpu().numpy()
        vector = rofa_average(features)
        vectors.append(vector)
        object_ids.append(item["id"])
        with database() as connection:
            connection.execute("UPDATE objects SET embedding = ? WHERE scene_id = ? AND id = ?",
                               (vector.astype("<f4").tobytes(), scene_id, item["id"]))
    with (target / "embeddings.npz.partial").open("wb") as handle:
        np.savez_compressed(handle, object_ids=np.asarray(object_ids, dtype=np.int32),
                            vectors=np.asarray(vectors, dtype=np.float32))
    (target / "embeddings.npz.partial").replace(target / "embeddings.npz")
    (target / "embeddings.metrics.json").write_text(json.dumps({
        "peak_torch_reserved_mb": round(torch.cuda.max_memory_reserved() / 1048576)}))


if __name__ == "__main__":
    if sys.argv[1] == "labels":
        label_scene(sys.argv[2])
    elif sys.argv[1] == "embeddings":
        embed_scene(sys.argv[2])
