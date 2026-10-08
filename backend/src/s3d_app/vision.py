"""Bounded real-Keyframe evidence and optional vision-model inference."""

import base64
import io
import json
import re

import numpy as np
from PIL import Image, ImageDraw

from s3d_app.gpu import GPU
from s3d_app.llm import LlmRouter
from s3d_app.pipeline import artifact_dir
from s3d_app.semantics import project
from s3d_app.storage import database


def image_url(image: Image.Image) -> str:
    image.thumbnail((768, 768), Image.Resampling.LANCZOS)
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=90)
    return "data:image/jpeg;base64," + base64.b64encode(output.getvalue()).decode()


def annotated_frames(scene_id: str, objects: list[dict], targets: list[int]) -> list[dict]:
    by_id = {item["id"]: item for item in objects}
    frame_scores = {}
    for identifier in targets:
        for rank, fid in enumerate(by_id[identifier]["keyframes"]):
            frame_scores[fid] = frame_scores.get(fid, 0) + 10 + (5 - rank)
    chosen = sorted(frame_scores, key=lambda fid: (-frame_scores[fid], fid))[:2]
    source = artifact_dir(scene_id, "S1")
    calibration = json.loads((source / "calib/intrinsics.json").read_text())
    intrinsic = np.asarray(calibration["color"]["intrinsic"])
    with np.load(artifact_dir(scene_id, "S2") / "geometry.npz") as geometry:
        points = geometry["points"]
        frame_positions = {int(fid): index for index, fid in enumerate(geometry["frame_ids"])}
        offsets = geometry["visibility_offsets"]
        indices = geometry["visibility_indices"]
    with np.load(artifact_dir(scene_id, "S3") / "masks.npz") as masks:
        instance_ids = masks["instance_ids"]
    frames = []
    colors = ["#ffca28", "#26c6da", "#ef5350", "#ab47bc", "#66bb6a", "#ffa726"]
    for fid in chosen:
        image = Image.open(source / "frames/color" / f"{fid:06d}.jpg").convert("RGB")
        position = frame_positions[fid]
        visible = indices[offsets[position]:offsets[position + 1]]
        pose = np.loadtxt(source / "frames/pose" / f"{fid:06d}.txt")
        u, v, valid = project(points[visible], pose, intrinsic, image.width, image.height)
        draw = ImageDraw.Draw(image)
        for number, identifier in enumerate(targets, 1):
            selected = valid & (instance_ids[visible] == identifier)
            if int(selected.sum()) < 5:
                continue
            box = (int(u[selected].min()), int(v[selected].min()),
                   int(u[selected].max()), int(v[selected].max()))
            color = colors[(number - 1) % len(colors)]
            draw.rectangle(box, outline=color, width=5)
            draw.rectangle((box[0], box[1], box[0] + 40, box[1] + 28), fill=color)
            draw.text((box[0] + 10, box[1] + 6), str(number), fill="black")
        frames.append({"frame_id": fid, "url": image_url(image)})
    return frames


def chat_with_images(router: LlmRouter, question: str, images: list[str]) -> str:
    content = [{"type": "text", "text": question}]
    content += [{"type": "image_url", "image_url": {"url": url}} for url in images[:2]]
    if not router.managed:
        response = router.chat("qwen3-vl-4b-vision", [{"role": "user", "content": content}])
    else:
        with GPU.reserve(0):
            if "qwen3-vl-4b-vision" not in router.loaded():
                router.unload_all()
                GPU.wait_for_memory(4200)
                router.load("qwen3-vl-4b-vision")
            response = router.chat("qwen3-vl-4b-vision", [{"role": "user", "content": content}])
    return response["choices"][0]["message"]["content"].strip()


def tiebreak(scene_id: str, question: str, objects: list[dict], targets: list[int],
             router: LlmRouter) -> tuple[int | None, list[dict]]:
    frames = annotated_frames(scene_id, objects, targets)
    if not frames:
        return None, []
    answer = chat_with_images(router,
        f"Choose the outlined candidate matching: {question}. Return only its displayed number "
        f"from 1 to {len(targets)}. If uncertain return 0.", [frame["url"] for frame in frames])
    if not re.fullmatch(r"\d+", answer):
        return None, frames
    number = int(answer)
    return (targets[number - 1] if 1 <= number <= len(targets) else None), frames


def caption(scene_id: str, item: dict, router: LlmRouter) -> str:
    if item.get("caption"):
        return item["caption"]
    crops = sorted((artifact_dir(scene_id, "S4") / "crops" / str(item["id"])).glob("*.jpg"))
    if not crops:
        raise ValueError("No readable Keyframe crop is available for this Object.")
    preferred = artifact_dir(scene_id, "S4") / "crops" / str(item["id"]) / f"{item['keyframes'][0]:06d}.jpg"
    chosen = preferred if preferred.is_file() else crops[0]
    text = chat_with_images(router, "Describe the visible object briefly. Do not invent IDs or quantities.",
                            [image_url(Image.open(chosen).convert("RGB"))])
    text = verified_wording(text, f"A {item.get('color', '')} {item.get('label', 'Object')}.",
                            {item["id"]}, set())
    item["caption"] = text
    with database() as connection:
        connection.execute("UPDATE objects SET data = ? WHERE scene_id = ? AND id = ?",
                           (json.dumps(item), scene_id, item["id"]))
    return text


def verified_wording(proposed: str, fallback: str, allowed_ids: set[int | str],
                     allowed_numbers: set[int]) -> str:
    normalized = proposed.lower()
    words = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
             "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
             "seventeen", "eighteen", "nineteen", "twenty"]
    for number, word in enumerate(words):
        normalized = re.sub(rf"\b{word}\b", str(number), normalized)
    mentioned = set(re.findall(r"(?:object\s*#?\s*|#)([a-z][a-z0-9-]*|\d+)", normalized))
    allowed = {str(identifier).lower() for identifier in allowed_ids}
    id_numbers = {int(value) for identifier in mentioned for value in re.findall(r"\d+", identifier)}
    numbers = {int(value) for value in re.findall(r"\b\d+\b", normalized)}
    return proposed if mentioned <= allowed and (numbers - id_numbers) <= allowed_numbers else fallback
