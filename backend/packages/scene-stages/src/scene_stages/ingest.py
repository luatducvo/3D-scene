"""CPU RGB ingest with upright, metadata-free keyframes and an explicit rejection report."""

import json
import re
import subprocess
import tempfile

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError
from scene_core.contracts import IngestManifest
from scene_core.errors import SceneError
from scene_core.ports import StageAlgorithm


def capture_order(path):
    """Natural order, so frame-2 precedes frame-10 and ScanNet frames keep their sequence."""
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", path.name)]


def perceptual_hash(image):
    gray = np.asarray(image.convert("L").resize((32, 32)), float)
    positions = np.arange(32)
    frequencies = np.arange(8)[:, None]
    transform = np.cos(np.pi / 32 * (positions + 0.5) * frequencies)
    coefficients = (transform @ gray @ transform.T).ravel()[1:]
    return coefficients > np.median(coefficients)


def ready_keyframe(original, long_side):
    """True for an upright RGB JPEG within long_side that carries no metadata, such as the browser's
    upload copy: ingest keeps its bytes, so the photo is compressed only once."""
    return (
        original.format == "JPEG"
        and original.mode == "RGB"
        and max(original.size) <= long_side
        and not original.getexif()
        and "comment" not in original.info
        # APP0 is the JFIF header and APP2 an ICC colour profile; any other segment may hold metadata.
        and all(
            marker == "APP0" or (marker == "APP2" and data.startswith(b"ICC_PROFILE"))
            for marker, data in original.applist
        )
    )


class OpenCVIngest(StageAlgorithm):
    name, stage = "ingest.opencv", "ingest"
    reads, writes = ["raw"], ["keyframes"]
    manifest_type = IngestManifest

    def run(self, workspace, params):
        minimum = int(params.get("min_keyframes", 10))
        maximum = int(params.get("max_keyframes", 120))
        fps = float(params.get("video_fps", 3))
        # quality_filter: false keeps every readable frame; only unreadable files are rejected.
        quality_filter = bool(params.get("quality_filter", True))
        if minimum < 1 or maximum < minimum or fps <= 0:
            raise ValueError("Require 1 <= min_keyframes <= max_keyframes and positive video_fps")
        output = workspace.dir("keyframes")
        for old in output.glob("*.jpg"):
            old.unlink()
        rejected = {"blur": [], "exposure": [], "duplicate": [], "invalid": []}
        accepted, hashes = [], []
        raw_files = sorted(
            (p for p in workspace.path("raw").iterdir() if p.is_file()), key=capture_order
        )
        with tempfile.TemporaryDirectory() as temporary:
            from pathlib import Path

            temporary = Path(temporary)
            candidates = []
            for index, source in enumerate(raw_files):
                if source.suffix.lower() in (".mp4", ".mov", ".avi", ".mkv", ".webm"):
                    destination = temporary / f"video-{index}"
                    destination.mkdir()
                    subprocess.run(
                        [
                            "ffmpeg",
                            "-nostdin",
                            "-v",
                            "error",
                            "-i",
                            str(source),
                            "-vf",
                            f"fps={fps}",
                            str(destination / "%06d.png"),
                        ],
                        check=True,
                        timeout=300,
                    )
                    candidates.extend(
                        (path, f"{source.name}:{path.stem}")
                        for path in sorted(destination.glob("*.png"))
                    )
                else:
                    candidates.append((source, source.name))
            for index, (source, label) in enumerate(candidates):
                self.progress(index, len(candidates), "image")
                try:
                    with Image.open(source) as original:
                        long_side = int(params.get("long_side", 1600))
                        ready = ready_keyframe(original, long_side)
                        image = ImageOps.exif_transpose(original).convert("RGB")
                        image.thumbnail((long_side,) * 2)
                        gray = np.asarray(image.convert("L"), dtype=float)
                        if quality_filter and np.mean((gray < 10) | (gray > 245)) > 0.25:
                            rejected["exposure"].append(label)
                            continue
                        laplacian = (
                            -4 * gray[1:-1, 1:-1]
                            + gray[:-2, 1:-1]
                            + gray[2:, 1:-1]
                            + gray[1:-1, :-2]
                            + gray[1:-1, 2:]
                        )
                        if quality_filter and (
                            not laplacian.size
                            or laplacian.var() < float(params.get("blur_threshold", 100))
                        ):
                            rejected["blur"].append(label)
                            continue
                        signature = perceptual_hash(image)
                        if quality_filter and any(
                            np.count_nonzero(signature != previous)
                            < int(params.get("phash_distance", 6))
                            for previous in hashes
                        ):
                            rejected["duplicate"].append(label)
                            continue
                        hashes.append(signature)
                        path = temporary / f"accepted-{index}.jpg"
                        if ready:
                            path.write_bytes(source.read_bytes())
                        else:
                            # A fresh image guarantees EXIF, GPS and other metadata never survive.
                            Image.fromarray(np.asarray(image)).save(path, quality=95)
                        accepted.append(path)
                except (UnidentifiedImageError, OSError):
                    rejected["invalid"].append(label)
            self.progress(len(candidates), len(candidates), "image")
            selected = (
                np.linspace(0, len(accepted) - 1, min(len(accepted), maximum), dtype=int)
                if accepted
                else []
            )
            for index, source_index in enumerate(selected):
                (output / f"{index:04d}.jpg").write_bytes(accepted[source_index].read_bytes())
        manifest = IngestManifest(
            num_inputs=len(candidates), num_keyframes=len(selected), rejected=rejected
        )
        (output / "manifest.json").write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
        if len(selected) < minimum:
            counts = {reason: len(files) for reason, files in rejected.items()}
            raise SceneError(
                "NOT_ENOUGH_KEYFRAMES",
                f"Need {minimum} keyframes; kept {len(selected)}. Rejected: {json.dumps(counts)}",
                details={"rejection_counts": counts},
            )
        return manifest
