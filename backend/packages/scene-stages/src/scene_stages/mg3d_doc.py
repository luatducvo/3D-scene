"""embed.mg3d_doc: a VLM writes each Object's Object Description, a sentence model embeds it, and a
cross-encoder reranks Descriptions against Search queries."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np
from PIL import Image
from pydantic import ValidationError
from scene_core.contracts import EmbedManifest
from scene_core.domain import DESCRIPTIONS, OBJECT_LIST, ObjectDescription
from scene_core.errors import SceneError
from scene_core.ports import StageAlgorithm
from scene_core.results import EMBEDDING_DIM, SceneResults

from .gpu import _cache, _cuda, _numpy
from .mesh import read_glb_positions
from .placement import DEFAULTS as PLACEMENT_DEFAULTS
from .placement import Placement, placement_facts

# A malformed answer is asked for again this many times before the Stage fails.
RETRIES = 2
PROMPT = """These images show one object from a scan of a room. Its label is "{label}".
Measured facts about where it is: {facts}
Answer with a JSON object and nothing else, with three keys:
"appearance": one English sentence on how it looks (colour, material, shape),
"use": one English sentence on what it is used for,
"placement": one English sentence on where it is, using the measured facts.
Each value must be exactly one sentence."""
FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)
SENTENCE_BREAK = re.compile(r"[.!?]\s+\S")


@dataclass
class DescriptionRequest:
    """What the VLM is shown to describe one Object: its Best View crops, label and placement facts."""

    id: str
    label: str
    facts: str
    images: list = field(default_factory=list)

    def prompt(self) -> str:
        return PROMPT.format(label=self.label, facts=self.facts)


def placement_text(placement: Placement, labels: dict[str, str]) -> str:
    """The placement facts as plain English, naming other Objects by their labels."""
    width, depth, height = placement.size_m
    if placement.support == "object":
        support = f"it rests on the {labels[placement.support_id]}"
    elif placement.support == "floor":
        support = "it rests on the floor"
    else:
        support = "nothing is under it (mounted or hanging)"
    position = {"corner": "in a corner", "wall": "by a wall", "open": "in the open"}
    neighbours = ", ".join(
        f"the {labels[n.id]} ({n.distance_m:.2f} m)" for n in placement.neighbours
    )
    return (
        f"it is {width:.2f} x {depth:.2f} x {height:.2f} m (width x depth x height); "
        f"its bottom is {placement.height_above_floor_m:.2f} m above the floor; {support}; "
        f"nearest objects: {neighbours or 'none'}; it stands {position[placement.room_position]}."
    )


def parse_description(answer: str) -> ObjectDescription:
    """The Object Description in a VLM answer; ValueError when it is not three single sentences."""
    text = answer.strip()
    fenced = FENCE.match(text)
    value = json.loads(fenced.group(1) if fenced else text)
    if not isinstance(value, dict) or set(value) != {"appearance", "use", "placement"}:
        raise ValueError("Expected exactly the keys appearance, use and placement")
    try:
        description = ObjectDescription.model_validate(
            {key: str(sentence).strip() for key, sentence in value.items()}
        )
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc
    for sentence in (description.appearance, description.use, description.placement):
        if SENTENCE_BREAK.search(sentence):
            raise ValueError(f"Expected one sentence, got {sentence!r}")
    return description


def describe(
    requests: list[DescriptionRequest],
    generate: Callable[[list[DescriptionRequest]], list[str]],
    on_round: Callable[[int, int], None] | None = None,
) -> dict[str, ObjectDescription]:
    """Each request's Object Description by id. `generate` answers a batch of requests in order;
    an Object whose answer is malformed is asked again, RETRIES times at most."""
    descriptions, pending, errors = {}, list(requests), {}
    for _ in range(1 + RETRIES):
        if not pending:
            break
        answers = generate(pending)
        if len(answers) != len(pending):
            raise SceneError(
                "INVALID_MODEL_OUTPUT",
                f"The VLM answered {len(answers)} of {len(pending)} Objects",
            )
        retry = []
        for request, answer in zip(pending, answers, strict=True):
            try:
                descriptions[request.id] = parse_description(answer)
            except ValueError as exc:
                errors[request.id] = str(exc)
                retry.append(request)
        pending = retry
        if on_round:
            on_round(len(descriptions), len(requests))
    if pending:
        raise SceneError(
            "INVALID_MODEL_OUTPUT",
            f"The VLM gave no valid Object Description for {pending[0].id}: {errors[pending[0].id]}",
            details={"objects": [request.id for request in pending]},
        )
    return descriptions


class MG3DDocEmbeddings(StageAlgorithm):
    name = "embed.mg3d_doc"
    stage = "embed"
    manifest_type = EmbedManifest
    reads = ["objects", "instances", "mesh"]
    writes = ["embeddings"]
    vlm_id = "Qwen/Qwen3-VL-8B-Instruct"
    embedder_id = "BAAI/bge-m3"
    reranker_id = "BAAI/bge-reranker-v2-m3"
    # Files of these repos PyTorch never loads: bge-m3's ONNX export and README images.
    IGNORE_PATTERNS = ("onnx/*", "imgs/*", "assets/*", "*.jpg", "*.png", "*.webp")

    def setup(self):
        _cache()
        self.vlm = self.embedder = self.reranker = None
        # The id each loaded model was loaded from; run() params may name other models.
        self.loaded = {}

    def download_weights(self):
        _cache()
        from huggingface_hub import snapshot_download

        for model_id in (self.vlm_id, self.embedder_id, self.reranker_id):
            snapshot_download(model_id, ignore_patterns=list(self.IGNORE_PATTERNS))

    def _load_embedder(self):
        torch = _cuda()
        from transformers import AutoModel, AutoTokenizer

        if self.embedder is None or self.loaded.get("embedder") != self.embedder_id:
            self.embedder_tokenizer = AutoTokenizer.from_pretrained(self.embedder_id)
            self.embedder = AutoModel.from_pretrained(self.embedder_id, dtype=torch.float16)
            self.embedder = self.embedder.to("cuda").eval()
            self.loaded["embedder"] = self.embedder_id
        if self.embedder.config.hidden_size != EMBEDDING_DIM:
            raise SceneError(
                "EMBEDDING_DIMENSION_MISMATCH",
                f"Expected the database's {EMBEDDING_DIM} dimensions",
            )
        return torch

    def _load_reranker(self):
        torch = _cuda()
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        if self.reranker is None or self.loaded.get("reranker") != self.reranker_id:
            self.reranker_tokenizer = AutoTokenizer.from_pretrained(self.reranker_id)
            self.reranker = AutoModelForSequenceClassification.from_pretrained(
                self.reranker_id, dtype=torch.float16
            )
            self.reranker = self.reranker.to("cuda").eval()
            self.loaded["reranker"] = self.reranker_id
        return torch

    def _configure(self, params):
        """Take the model ids from the Stage's params, so Search uses the models a run used."""
        params = params or {}
        self.vlm_id = params.get("vlm_model_id", self.vlm_id)
        self.embedder_id = params.get("embedder_model_id", self.embedder_id)
        self.reranker_id = params.get("reranker_model_id", self.reranker_id)

    def embed_text(self, texts, params=None, batch_size=32):
        """bge-m3 dense vectors: the first token's state, L2-normalised."""
        self._configure(params)
        torch = self._load_embedder()
        if not texts:
            return np.empty((0, EMBEDDING_DIM), dtype=np.float32)
        batches = []
        for start in range(0, len(texts), batch_size):
            inputs = self.embedder_tokenizer(
                texts[start : start + batch_size],
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="pt",
            ).to("cuda")
            with torch.inference_mode():
                batches.append(_numpy(self.embedder(**inputs).last_hidden_state[:, 0]))
        array = np.concatenate(batches)
        norms = np.linalg.norm(array, axis=-1, keepdims=True)
        if not np.isfinite(array).all() or (norms <= 0).any():
            raise SceneError("INVALID_MODEL_OUTPUT", "Invalid bge-m3 embedding")
        return (array / norms).astype(np.float32)

    def rerank(self, query, descriptions, params=None, batch_size=32):
        """How well each Object Description answers the query: the cross-encoder's logit through a sigmoid."""
        if not query.strip():
            raise SceneError("INVALID_PARAMETERS", "The query must not be empty")
        self._configure(params)
        torch = self._load_reranker()
        scores = []
        for start in range(0, len(descriptions), batch_size):
            pairs = [[query, text] for text in descriptions[start : start + batch_size]]
            inputs = self.reranker_tokenizer(
                pairs, padding=True, truncation=True, max_length=512, return_tensors="pt"
            ).to("cuda")
            with torch.inference_mode():
                logits = self.reranker(**inputs).logits.view(-1)
            scores.extend(_numpy(torch.sigmoid(logits)).tolist())
        if not np.isfinite(scores).all():
            raise SceneError("INVALID_MODEL_OUTPUT", "Invalid reranker score")
        return scores

    def _generate(self, requests, batch_size, max_new_tokens):
        torch = _cuda()
        from transformers import AutoModelForImageTextToText, AutoProcessor

        if self.vlm is None or self.loaded.get("vlm") != self.vlm_id:
            self.loaded["vlm"] = self.vlm_id
            self.processor = AutoProcessor.from_pretrained(self.vlm_id)
            self.processor.tokenizer.padding_side = "left"
            self.vlm = AutoModelForImageTextToText.from_pretrained(
                self.vlm_id, dtype=torch.bfloat16, device_map="cuda"
            ).eval()
        answers = []
        for start in range(0, len(requests), batch_size):
            messages = [
                [
                    {
                        "role": "user",
                        "content": [
                            *({"type": "image", "image": image} for image in request.images),
                            {"type": "text", "text": request.prompt()},
                        ],
                    }
                ]
                for request in requests[start : start + batch_size]
            ]
            inputs = self.processor.apply_chat_template(
                messages,
                tokenize=True,
                add_generation_prompt=True,
                return_dict=True,
                return_tensors="pt",
                padding=True,
            ).to(self.vlm.device)
            with torch.inference_mode():
                output = self.vlm.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
            answers.extend(
                self.processor.batch_decode(
                    output[:, inputs["input_ids"].shape[1] :], skip_special_tokens=True
                )
            )
        return answers

    def _requests(self, workspace, objects, placements, max_views):
        labels = {obj.id: obj.label for obj in objects}
        requests = []
        for obj in objects:
            # Crops are saved in Best View order; the highest scores are shown.
            ranked = sorted(
                range(len(obj.best_views)), key=lambda i: obj.best_views[i].score, reverse=True
            )[:max_views]
            if not ranked:
                raise SceneError("MISSING_EVIDENCE", f"No Best View crops for {obj.id}")
            images = []
            for index in ranked:
                with Image.open(workspace.path(f"instances/crops/{obj.id}_{index}.jpg")) as crop:
                    images.append(crop.convert("RGB"))
            facts = placement_text(placements[obj.id], labels)
            requests.append(DescriptionRequest(obj.id, obj.label, facts, images))
        return requests

    def run(self, workspace, params):
        self._configure(params)
        sizes = {
            name: int(params.get(name, default))
            for name, default in (
                ("vlm_batch_size", 8),
                ("embed_batch_size", 32),
                ("max_views", 3),
                ("max_new_tokens", 256),
            )
        }
        if min(sizes.values()) < 1:
            raise SceneError(
                "INVALID_PARAMETERS", f"Batch sizes and limits must be positive: {sizes}"
            )
        objects = OBJECT_LIST.validate_json(
            workspace.path(SceneResults.OBJECTS).read_text(encoding="utf-8")
        )
        placements = placement_facts(
            objects,
            read_glb_positions(workspace.path(SceneResults.ASSETS["mesh"])),
            {name: params[name] for name in PLACEMENT_DEFAULTS if name in params},
        )
        requests = self._requests(workspace, objects, placements, sizes["max_views"])
        self.progress(0, len(objects), "object")
        descriptions = describe(
            requests,
            lambda batch: self._generate(batch, sizes["vlm_batch_size"], sizes["max_new_tokens"]),
            on_round=lambda done, total: self.progress(done, total, "object"),
        )
        # Search needs only the embedder and the reranker; the VLM's memory goes back to the GPU.
        self.vlm = None
        _cuda().cuda.empty_cache()
        ids, batch = [obj.id for obj in objects], sizes["embed_batch_size"]
        chunks = []
        for start in range(0, len(ids), batch):
            self.progress(start, len(ids), "embedding")
            texts = [descriptions[i].text() for i in ids[start : start + batch]]
            chunks.append(self.embed_text(texts, batch_size=batch))
        self.progress(len(ids), len(ids), "embedding")
        vectors = np.concatenate(chunks) if chunks else np.empty((0, EMBEDDING_DIM), np.float32)
        workspace.dir("embeddings")
        np.savez_compressed(
            workspace.path(SceneResults.EMBEDDINGS),
            ids=np.asarray(ids, dtype=str),
            vectors=vectors,
        )
        workspace.path(SceneResults.DESCRIPTIONS).write_bytes(DESCRIPTIONS.dump_json(descriptions))
        return EmbedManifest(
            model_id=self.embedder_id,
            vlm_model_id=self.vlm_id,
            reranker_model_id=self.reranker_id,
            dim=EMBEDDING_DIM,
            embeddings_file=SceneResults.EMBEDDINGS,
            descriptions_file=SceneResults.DESCRIPTIONS,
        )
