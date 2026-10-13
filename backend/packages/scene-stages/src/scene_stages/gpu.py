"""Lazy model adapters. Upstream interfaces and manual checks: docs/GPU-INTEGRATION.md."""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
from PIL import Image

from scene_core.contracts import AlignManifest, EmbedManifest, ReconManifest, SegmentManifest
from scene_core.errors import SceneError
from scene_core.geometry import fit_plane
from scene_core.ports import StageAlgorithm


def _cache():
    root = Path(os.environ.get("MODELS_DIR", "models"))
    os.environ.setdefault("HF_HOME", str(root / "hf"))
    os.environ.setdefault("TORCH_HOME", str(root / "torch"))


def _cuda():
    _cache()
    import torch
    if not torch.cuda.is_available():
        raise SceneError("GPU_REQUIRED", "This Algorithm requires a CUDA compute Target")
    return torch


def _numpy(value):
    return value.detach().float().cpu().numpy()


class MapAnythingReconstruction(StageAlgorithm):
    name = "recon.mapanything"
    stage = "recon"
    manifest_type = ReconManifest
    reads = ["keyframes"]
    writes = ["recon"]
    model_id = "facebook/map-anything"

    def setup(self):
        _cache()
        self.model = None

    def download_weights(self):
        _cache()
        from huggingface_hub import snapshot_download
        snapshot_download(self.model_id)

    def run(self, workspace, params):
        torch = _cuda()
        from mapanything.models import MapAnything
        from mapanything.utils.image import load_images

        model_id = params.get("model_id", self.model_id)
        if self.model is None or model_id != self.model_id:
            self.model = MapAnything.from_pretrained(model_id).to("cuda").eval()
            self.model_id = model_id
        files = sorted(workspace.path("keyframes").glob("*.jpg"))
        if not files:
            raise SceneError("NOT_ENOUGH_KEYFRAMES", "Reconstruction requires Keyframes")
        views = load_images([str(path) for path in files])
        with torch.inference_mode():
            predictions = self.model.infer(
                views, memory_efficient_inference=params.get("memory_efficient_inference", True),
                minibatch_size=params.get("minibatch_size", 1), use_amp=True, amp_dtype="bf16",
                apply_mask=True, mask_edges=True, apply_confidence_mask=True,
                confidence_percentile=float(params.get("confidence_percentile", 10)),
            )
        if len(predictions) != len(files):
            raise SceneError("INVALID_MODEL_OUTPUT", "Reconstruction dropped an input Frame")
        image_size = None
        scales = []
        for path, result in zip(files, predictions):
            depth = _numpy(result["depth_z"])[0, ..., 0]
            confidence = _numpy(result["conf"])[0]
            pose = _numpy(result["camera_poses"])[0]
            intrinsics = _numpy(result["intrinsics"])[0]
            rgb = _numpy(result["img_no_norm"])[0]
            valid = _numpy(result["mask"])[0, ..., 0] > 0
            if (depth.ndim != 2 or confidence.shape != depth.shape
                    or rgb.shape != (*depth.shape, 3) or valid.shape != depth.shape
                    or pose.shape != (4, 4) or intrinsics.shape != (3, 3)
                    or not np.isfinite(pose).all() or not np.isfinite(intrinsics).all()):
                raise SceneError("INVALID_MODEL_OUTPUT", "MapAnything output violates Frame shapes")
            valid &= np.isfinite(depth) & (depth > 0) & np.isfinite(confidence)
            depth = np.where(valid, depth, 0).astype(np.float32)
            confidence = np.where(valid, confidence, 0).astype(np.float32)
            Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8)).save(
                workspace.dir("recon/rgb") / f"{path.stem}.png")
            np.savez_compressed(workspace.dir("recon/frames") / f"{path.stem}.npz",
                                depth=depth, conf=confidence, pose=pose, K=intrinsics)
            image_size = (depth.shape[1], depth.shape[0])
            scales.append(float(_numpy(result["metric_scaling_factor"]).mean()))
        if not np.isfinite(scales).all() or min(scales) <= 0:
            raise SceneError("INVALID_MODEL_OUTPUT", "Invalid metric scaling factor")
        return ReconManifest(num_frames=len(files), frame_ids=[path.stem for path in files],
                             metric_scale=float(np.mean(scales)), image_size=image_size)


def _rotation_to_up(up):
    up = np.asarray(up, dtype=float)
    up /= np.linalg.norm(up)
    target = np.array([0., 0., 1.])
    cross = np.cross(up, target)
    cosine = float(up @ target)
    if cosine < -1 + 1e-8:
        return np.diag([1., -1., -1.])
    skew = np.array([[0, -cross[2], cross[1]], [cross[2], 0, -cross[0]],
                     [-cross[1], cross[0], 0]])
    return np.eye(3) + skew + skew @ skew / (1 + cosine)


def _world_points(frame, stride):
    depth = frame["depth"][::stride, ::stride]
    confidence = frame["conf"][::stride, ::stride]
    yy, xx = np.mgrid[:depth.shape[0], :depth.shape[1]] * stride
    valid = np.isfinite(depth) & (depth > 0) & np.isfinite(confidence) & (confidence > 0)
    pixels = np.column_stack((xx[valid], yy[valid], np.ones(int(valid.sum()))))
    camera = (pixels @ np.linalg.inv(frame["K"]).T) * depth[valid, None]
    return camera @ frame["pose"][:3, :3].T + frame["pose"][:3, 3]


class GeoCalibAlignment(StageAlgorithm):
    name = "align.geocalib_ransac"
    stage = "align"
    manifest_type = AlignManifest
    reads = ["recon"]
    writes = ["align"]

    def setup(self):
        _cache()
        self.model = None

    def download_weights(self):
        _cache()
        import torch
        destination = Path(torch.hub.get_dir()) / "geocalib" / "pinhole.tar"
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            torch.hub.download_url_to_file(
                "https://github.com/cvg/GeoCalib/releases/download/v1.0/geocalib-pinhole.tar",
                str(destination))

    def run(self, workspace, params):
        _cuda()
        from geocalib import GeoCalib
        if self.model is None:
            self.model = GeoCalib().to("cuda").eval()
        files = sorted(workspace.path("recon/frames").glob("*.npz"))
        if not files:
            raise SceneError("ALIGNMENT_FAILED", "No reconstructed Frames")
        count = max(1, int(params.get("num_calibration_frames", 20)))
        selected = set(np.linspace(0, len(files) - 1, min(count, len(files)), dtype=int))
        vectors, clouds = [], []
        for index, path in enumerate(files):
            with np.load(path, allow_pickle=False) as data:
                frame = dict(data)
            clouds.append(_world_points(frame, max(1, int(params.get("point_stride", 8)))))
            if index in selected:
                image = self.model.load_image(workspace.path(f"recon/rgb/{path.stem}.png"))
                result = self.model.calibrate(image.to("cuda"))
                # GeoCalib's zero-roll/pitch vector is (0,-1,0): up in OpenCV camera axes.
                camera_up = _numpy(result["gravity"].vec3d).reshape(-1, 3)[0]
                vectors.append(frame["pose"][:3, :3] @ camera_up)
        vectors = np.asarray(vectors)
        if not np.isfinite(vectors).all():
            raise SceneError("ALIGNMENT_FAILED", "Invalid gravity estimate")
        up = vectors.mean(axis=0)
        if np.linalg.norm(up) < 1e-6:
            raise SceneError("ALIGNMENT_FAILED", "Gravity estimates disagree")
        up /= np.linalg.norm(up)
        for _ in range(20):
            weights = 1 / np.maximum(np.arccos(np.clip(vectors @ up, -1, 1)), 1e-4)
            estimate = np.sum(vectors * weights[:, None], axis=0)
            up = estimate / np.linalg.norm(estimate)
        cloud = np.concatenate(clouds)
        cloud = cloud[np.isfinite(cloud).all(axis=1)]
        if len(cloud) < 100:
            raise SceneError("ALIGNMENT_FAILED", "Too few valid depth points for floor fitting")
        if len(cloud) > 30000:
            cloud = cloud[np.random.default_rng(42).choice(len(cloud), 30000, replace=False)]
        threshold = float(params.get("ransac_threshold_m", .02))
        remaining, horizontal, vertical = cloud.copy(), [], []
        minimum = max(30, int(.02 * len(cloud)))
        for _ in range(12):
            if len(remaining) < minimum:
                break
            normal, offset, inliers = fit_plane(remaining, threshold=threshold)
            if inliers.sum() < minimum:
                break
            points = remaining[inliers]
            agreement = float(normal @ up)
            if abs(agreement) >= np.cos(np.deg2rad(15)):
                if agreement < 0:
                    normal, offset = -normal, -offset
                horizontal.append((float(np.median(points @ up)), normal, points))
            elif abs(agreement) <= np.sin(np.deg2rad(15)):
                vertical.append((normal, offset, len(points)))
            remaining = remaining[~inliers]
        if not horizontal:
            raise SceneError("FLOOR_NOT_FOUND", "No large horizontal floor plane found")
        floor = min(horizontal, key=lambda plane: plane[0])
        rotation = _rotation_to_up(floor[1])
        if not vertical:
            raise SceneError("WALLS_NOT_FOUND", "No vertical planes for Manhattan alignment")
        normals = np.asarray([rotation @ normal for normal, _, _ in vertical])
        angles = np.arctan2(normals[:, 1], normals[:, 0])
        votes = np.asarray([weight for _, _, weight in vertical])
        yaw = np.arctan2(np.sum(votes * np.sin(4 * angles)),
                         np.sum(votes * np.cos(4 * angles))) / 4
        c, s = np.cos(-yaw), np.sin(-yaw)
        rotation = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]]) @ rotation
        floor_z = float(np.median((floor[2] @ rotation.T)[:, 2]))
        transform = np.eye(4)
        transform[:3, :3], transform[2, 3] = rotation, -floor_z
        ceilings = [float(np.median((plane[2] @ rotation.T)[:, 2])) - floor_z
                    for plane in horizontal if plane[0] > floor[0] + 1.5]
        for path in files:
            with np.load(path, allow_pickle=False) as data:
                frame = dict(data)
            frame["pose"] = transform @ frame["pose"]
            np.savez_compressed(workspace.dir("align/frames") / path.name, **frame)
        walls = [{"normal": (rotation @ normal).tolist(),
                  "offset": float(offset - (rotation @ normal) @ transform[:3, 3]),
                  "support": weight} for normal, offset, weight in vertical]
        workspace.dir("align").joinpath("walls.json").write_text(
            json.dumps(walls), encoding="utf-8")
        return AlignManifest(world_to_aligned=transform.tolist(), floor_z=0,
                             ceiling_height=max(ceilings) if ceilings else None)


class Sam3Segmentation(StageAlgorithm):
    name = "segment.sam3"
    stage = "segment"
    manifest_type = SegmentManifest
    reads = ["recon"]
    writes = ["segment"]

    def setup(self):
        _cache()
        self.model = None

    def download_weights(self):
        _cache()
        from huggingface_hub import hf_hub_download
        for filename in ("config.json", "sam3.pt"):
            hf_hub_download("facebook/sam3", filename)

    def run(self, workspace, params):
        torch = _cuda()
        from sam3.model_builder import build_sam3_image_model
        from sam3.model.sam3_image_processor import Sam3Processor
        if self.model is None:
            self.model = build_sam3_image_model(device="cuda")
        threshold = float(params.get("score_threshold", .5))
        processor = Sam3Processor(self.model, device="cuda", confidence_threshold=threshold)
        vocabulary_root = Path(os.environ.get("VOCABULARY_DIR", "backend/config/vocabularies"))
        vocabulary_path = vocabulary_root / params.get("vocabulary_file", "indoor-en.txt")
        if not vocabulary_path.resolve().is_relative_to(vocabulary_root.resolve()):
            raise SceneError("INVALID_VOCABULARY", "Vocabulary must be inside VOCABULARY_DIR")
        vocabulary = list(dict.fromkeys(line.strip() for line in vocabulary_path.read_text(
            encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")))
        if not vocabulary:
            raise SceneError("INVALID_VOCABULARY", "Vocabulary is empty")
        files = sorted(workspace.path("recon/rgb").glob("*.png"))
        stride = int(params.get("frame_stride", 2))
        if stride < 1:
            raise SceneError("INVALID_PARAMETERS", "frame_stride must be positive")
        total = 0
        for path in files[::stride]:
            candidates = []
            with Image.open(path) as source, torch.inference_mode():
                image = source.convert("RGB")
                state = processor.set_image(image)
                for label in vocabulary:
                    result = processor.set_text_prompt(state=state, prompt=label)
                    masks = _numpy(result["masks"])
                    if masks.ndim == 4 and masks.shape[1] == 1:
                        masks = masks[:, 0]
                    scores = _numpy(result["scores"]).reshape(-1)
                    if masks.shape != (len(scores), image.height, image.width):
                        raise SceneError("INVALID_MODEL_OUTPUT", "SAM 3 mask dimensions differ from RGB")
                    for mask, score in zip(masks, scores):
                        binary = mask > .5
                        if np.isfinite(score) and score >= threshold and binary.any():
                            candidates.append((float(score), label, binary))
                kept = []
                for candidate in sorted(candidates, key=lambda item: item[0], reverse=True):
                    mask = candidate[2]
                    if any(np.count_nonzero(mask & item[2]) / np.count_nonzero(mask | item[2])
                           > .8 for item in kept):
                        continue
                    kept.append(candidate)
                masks = np.stack([item[2] for item in kept]) if kept else np.empty(
                    (0, image.height, image.width), dtype=bool)
                np.savez_compressed(workspace.dir("segment/masks") / f"{path.stem}.npz",
                                    masks=masks, labels=np.asarray([item[1] for item in kept], dtype=str),
                                    scores=np.asarray([item[0] for item in kept], dtype=np.float32))
                total += len(kept)
        return SegmentManifest(num_masks=total, vocabulary_size=len(vocabulary))


class MetaClipEmbeddings(StageAlgorithm):
    name = "embed.metaclip2"
    stage = "embed"
    manifest_type = EmbedManifest
    reads = ["instances"]
    writes = ["embeddings"]
    model_id = "facebook/metaclip-2-worldwide-huge-quickgelu"

    def setup(self):
        _cache()
        self.model = None

    def download_weights(self):
        _cache()
        from huggingface_hub import snapshot_download
        snapshot_download(self.model_id)

    def _load(self, model_id=None):
        torch = _cuda()
        from transformers import AutoModel, AutoProcessor
        model_id = model_id or self.model_id
        if self.model is None or self.model_id != model_id:
            self.processor = AutoProcessor.from_pretrained(model_id)
            self.model = AutoModel.from_pretrained(model_id).to("cuda").eval()
            self.model_id = model_id
        if self.model.config.projection_dim != 1024:
            raise SceneError("EMBEDDING_DIMENSION_MISMATCH", "Expected the database's 1024 dimensions")
        return torch

    def _normalized(self, features):
        array = _numpy(features)
        norms = np.linalg.norm(array, axis=-1, keepdims=True)
        if array.ndim != 2 or array.shape[1] != 1024 or not np.isfinite(array).all() or (norms <= 0).any():
            raise SceneError("INVALID_MODEL_OUTPUT", "Invalid MetaCLIP embedding")
        return array / norms

    def embed_text(self, texts):
        torch = self._load()
        if not texts:
            return np.empty((0, 1024), dtype=np.float32)
        batches = []
        for start in range(0, len(texts), 32):
            inputs = self.processor(text=texts[start:start + 32], padding=True, truncation=True,
                                    return_tensors="pt").to("cuda")
            with torch.inference_mode():
                batches.append(self._normalized(self.model.get_text_features(**inputs)))
        return np.concatenate(batches)

    def run(self, workspace, params):
        torch = self._load(params.get("model_id"))
        instances = json.loads(workspace.path("instances/instances.json").read_text(encoding="utf-8"))
        ids, vectors = [], []
        for instance in instances:
            crops, weights = [], []
            for index, view in enumerate(instance["best_views"]):
                path = workspace.path(f"instances/crops/{instance['id']}_{index}.jpg")
                with Image.open(path) as source:
                    crops.append(source.convert("RGB"))
                weights.append(max(0, float(view["score"])))
            if not crops or sum(weights) <= 0:
                raise SceneError("MISSING_EVIDENCE", f"No scored crops for {instance['id']}")
            inputs = self.processor(images=crops, return_tensors="pt").to("cuda")
            with torch.inference_mode():
                features = self._normalized(self.model.get_image_features(**inputs))
            vector = np.average(features, axis=0, weights=weights)
            norm = np.linalg.norm(vector)
            if not np.isfinite(norm) or norm <= 0:
                raise SceneError("INVALID_MODEL_OUTPUT", "Object embedding has zero norm")
            ids.append(instance["id"])
            vectors.append(vector / norm)
        array = np.asarray(vectors, dtype=np.float32).reshape(-1, 1024)
        np.savez_compressed(workspace.dir("embeddings") / "objects.npz",
                            ids=np.asarray(ids, dtype=str), vectors=array)
        return EmbedManifest(model_id=self.model_id, dim=1024, embeddings_file="embeddings/objects.npz")
