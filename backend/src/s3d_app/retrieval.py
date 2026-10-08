"""CPU text embedding and cached brute-force lookup over Scene Object vectors."""

import threading
from functools import lru_cache

import numpy as np

from s3d_app.models import model_root
from s3d_app.pipeline import artifact_dir

TEXT_LOCK = threading.Lock()
_ENCODER = None
_TOKENIZER = None


def encode_text(texts: list[str]) -> np.ndarray:
    global _ENCODER, _TOKENIZER
    import open_clip
    import torch

    with TEXT_LOCK:
        if _ENCODER is None:
            _ENCODER = torch.jit.load(str(model_root() / "mobileclip2_b.ts"), map_location="cpu").eval()
            _TOKENIZER = open_clip.get_tokenizer("MobileCLIP2-B")
        with torch.inference_mode():
            features = _ENCODER(_TOKENIZER(texts)).float().numpy()
    return features / np.maximum(np.linalg.norm(features, axis=1, keepdims=True), 1e-8)


@lru_cache(maxsize=8)
def _matrix(scene_id: str, modified_ns: int) -> tuple[np.ndarray, np.ndarray]:
    with np.load(artifact_dir(scene_id, "S4") / "embeddings.npz", allow_pickle=False) as saved:
        return saved["object_ids"].copy(), saved["vectors"].copy()


def similarities(scene_id: str, phrase: str) -> dict[int, float]:
    path = artifact_dir(scene_id, "S4") / "embeddings.npz"
    if not path.is_file() or not (model_root() / "mobileclip2_b.ts").is_file():
        return {}
    object_ids, vectors = _matrix(scene_id, path.stat().st_mtime_ns)
    if not len(object_ids):
        return {}
    scores = vectors @ encode_text([phrase])[0]
    return {int(identifier): float(score) for identifier, score in zip(object_ids, scores)}


def normalize_nouns(phrases: dict, objects: list[dict]) -> dict:
    labels = sorted({item["label"] for item in objects})
    aliases = {alt.lower() for item in objects for alt in item.get("alt_labels", [])
               if item.get("label_distribution", {}).get(alt, 1.0) >= 0.1}
    result = {}
    unknown = []
    for variable, phrase in phrases.items():
        plain = phrase.lower().strip()
        if (plain in {"object", "thing", "any", ""} or plain in labels or plain in aliases
                or any(plain in label.lower() or label.lower() in plain for label in labels)):
            result[variable] = plain
        else:
            unknown.append((variable, phrase))
    if unknown and labels and (model_root() / "mobileclip2_b.ts").is_file():
        vectors = encode_text(labels + [phrase for _, phrase in unknown])
        label_vectors = vectors[:len(labels)]
        for index, (variable, _phrase) in enumerate(unknown):
            scores = label_vectors @ vectors[len(labels) + index]
            result[variable] = labels[int(scores.argmax())] if float(scores.max()) >= 0.9 else unknown[index][1]
    else:
        result.update(unknown)
    return result
