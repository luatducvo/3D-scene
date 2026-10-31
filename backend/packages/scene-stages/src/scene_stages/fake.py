"""Deterministic synthetic algorithms, explicitly selected through entry points."""

import json
import time

import numpy as np
from PIL import Image
from scene_core.contracts import (
    AlignManifest,
    EmbedManifest,
    IngestManifest,
    LiftManifest,
    MeshManifest,
    ObjectsManifest,
    ReconManifest,
    SegmentManifest,
)
from scene_core.domain import DESCRIPTIONS, OBJECT_LIST, ObjectDescription
from scene_core.errors import SceneError
from scene_core.ports import StageAlgorithm
from scene_core.results import EMBEDDING_DIM, SceneResults

from .mesh import GLTF_FLOAT, GLTF_UNSIGNED_SHORT, pack_glb, write_ply
from .objects import write_membership, write_objects

OBJECTS = [
    {
        "id": "chair-1",
        "label": "chair",
        "box": {"center": [1, 1, 0.5], "size": [0.5, 0.5, 1], "yaw": 0},
        "best_views": [{"frame_id": "0000", "bbox": [0, 0, 16, 16], "score": 1}],
    },
    {
        "id": "table-1",
        "label": "table",
        "box": {"center": [2, 1, 0.4], "size": [1, 1, 0.8], "yaw": 0},
        "best_views": [{"frame_id": "0000", "bbox": [0, 0, 16, 16], "score": 1}],
    },
]

# Each fake Object's Object Description; only the chair's mentions sitting.
FAKE_DESCRIPTIONS = {
    "chair-1": ObjectDescription(
        appearance="A brown wooden chair with four legs and a straight back.",
        use="It is used for sitting.",
        placement="It is about 1 m tall and stands on the floor in the open.",
    ),
    "table-1": ObjectDescription(
        appearance="A square brown wooden table.",
        use="It holds plates, books and cups.",
        placement="It is about 0.8 m tall and stands on the floor in the open.",
    ),
}


class Fake(StageAlgorithm):
    def run(self, w, p):
        if p.get("delay"):
            time.sleep(p["delay"])
        self.fail_if_scripted(p)
        steps = int(p.get("progress_steps", 1))
        self.progress(0, steps, "step")
        result = self.transform(w, p)
        for done in range(1, steps + 1):
            self.progress(done, steps, "step")
        return result

    def fail_if_scripted(self, p):
        if p.get("fail"):
            raise SceneError(
                p.get("fail_code", "FAKE_STAGE_FAILED"),
                str(p["fail"]),
                details=p.get("fail_details"),
            )


class IngestFake(Fake):
    name = "ingest.fake"
    stage = "ingest"
    manifest_type = IngestManifest
    reads = ["raw"]
    writes = ["keyframes"]

    def transform(self, w, p):
        files = list(w.dir("raw").iterdir())
        Image.new("RGB", (16, 16), (200, 150, 80)).save(w.dir("keyframes") / "0000.jpg")
        return IngestManifest(num_inputs=len(files), num_keyframes=1, rejected={})


class ReconFake(Fake):
    name = "recon.fake"
    stage = "recon"
    manifest_type = ReconManifest
    reads = ["keyframes"]
    writes = ["recon"]

    def transform(self, w, p):
        Image.open(w.path("keyframes/0000.jpg")).save(w.dir("recon", "rgb") / "0000.png")
        np.savez(
            w.dir("recon", "frames") / "0000.npz",
            depth=np.ones((16, 16)),
            conf=np.ones((16, 16)),
            pose=np.eye(4),
            K=np.array([[16, 0, 8], [0, 16, 8], [0, 0, 1]]),
        )
        return ReconManifest(num_frames=1, frame_ids=["0000"], metric_scale=1, image_size=(16, 16))


class AlignFake(Fake):
    name = "align.fake"
    stage = "align"
    manifest_type = AlignManifest
    reads = ["recon"]
    writes = ["align"]

    def transform(self, w, p):
        import shutil

        shutil.copyfile(w.path("recon/frames/0000.npz"), w.dir("align", "frames") / "0000.npz")
        return AlignManifest(world_to_aligned=np.eye(4).tolist(), floor_z=0, ceiling_height=2.5)


class MeshFake(Fake):
    name = "mesh.fake"
    stage = "mesh"
    manifest_type = MeshManifest
    reads = ["align", "recon"]
    writes = ["mesh"]

    def transform(self, w, p):
        # Five room faces, leaving the front open for the camera.
        vertices = np.array(
            [
                [0, 0, 0],
                [4, 0, 0],
                [4, 3, 0],
                [0, 3, 0],
                [0, 0, 2.5],
                [4, 0, 2.5],
                [4, 3, 2.5],
                [0, 3, 2.5],
            ],
            dtype="<f4",
        )
        indices = np.array(
            [0, 2, 1, 0, 3, 2, 0, 4, 7, 0, 7, 3, 3, 7, 6, 3, 6, 2, 2, 6, 5, 2, 5, 1], dtype="<u2"
        )
        binary = vertices.tobytes() + indices.tobytes()
        binary += b"\0" * ((-len(binary)) % 4)
        doc = {
            "asset": {"version": "2.0"},
            "scene": 0,
            "scenes": [{"nodes": [0]}],
            "nodes": [{"mesh": 0}],
            "meshes": [
                {"primitives": [{"attributes": {"POSITION": 0}, "indices": 1, "material": 0}]}
            ],
            "materials": [
                {
                    "doubleSided": True,
                    "pbrMetallicRoughness": {
                        "baseColorFactor": [0.6, 0.67, 0.74, 1],
                        "metallicFactor": 0,
                        "roughnessFactor": 1,
                    },
                }
            ],
            "buffers": [{"byteLength": len(binary)}],
            "bufferViews": [
                {"buffer": 0, "byteOffset": 0, "byteLength": vertices.nbytes},
                {"buffer": 0, "byteOffset": vertices.nbytes, "byteLength": indices.nbytes},
            ],
            "accessors": [
                {
                    "bufferView": 0,
                    "componentType": GLTF_FLOAT,
                    "count": 8,
                    "type": "VEC3",
                    "min": [0, 0, 0],
                    "max": [4, 3, 2.5],
                },
                {
                    "bufferView": 1,
                    "componentType": GLTF_UNSIGNED_SHORT,
                    "count": len(indices),
                    "type": "SCALAR",
                },
            ],
        }
        w.dir("mesh").joinpath("mesh.glb").write_bytes(pack_glb(doc, binary))
        # The same five faces as a colored point cloud on a 5 cm grid.
        u, v = (g.ravel() for g in np.meshgrid(np.linspace(0, 1, 81), np.linspace(0, 1, 81)))
        zero = np.zeros_like(u)
        faces = [
            (np.column_stack([4 * u, 3 * v, zero]), (150, 120, 90)),
            (np.column_stack([zero, 3 * u, 2.5 * v]), (200, 200, 190)),
            (np.column_stack([4 * u, zero, 2.5 * v]), (185, 190, 200)),
            (np.column_stack([4 * u, 3 + zero, 2.5 * v]), (185, 190, 200)),
            (np.column_stack([4 + zero, 3 * u, 2.5 * v]), (200, 200, 190)),
        ]
        points = np.concatenate([f for f, _ in faces])
        colors = np.concatenate([np.tile(c, (len(f), 1)) for f, c in faces]).astype(np.uint8)
        write_ply(w.path("mesh/points.ply"), points, colors)
        return MeshManifest(
            mesh_file="mesh/mesh.glb",
            points_file="mesh/points.ply",
            num_faces=8,
            num_points=len(points),
        )


class SegmentFake(Fake):
    name = "segment.fake"
    stage = "segment"
    manifest_type = SegmentManifest
    reads = ["recon"]
    writes = ["segment"]

    def transform(self, w, p):
        np.savez(
            w.dir("segment", "masks") / "0000.npz",
            masks=np.ones((2, 16, 16), dtype=bool),
            labels=np.array(["chair", "table"]),
            scores=np.ones(2),
        )
        return SegmentManifest(num_masks=2, vocabulary_size=2)


class LiftFake(Fake):
    name = "lift.fake"
    stage = "lift"
    manifest_type = LiftManifest
    reads = ["segment", "align", "recon"]
    writes = ["instances"]

    def transform(self, w, p):
        instances = []
        for obj in OBJECTS:
            points = np.array(obj["box"]["center"]) + np.array(
                [[-0.2, -0.2, -0.3], [0.2, 0.2, 0.3]]
            )
            np.save(w.dir("instances", "points") / (obj["id"] + ".npy"), points)
            Image.open(w.path("recon/rgb/0000.png")).save(
                w.dir("instances", "crops") / (obj["id"] + "_0.jpg")
            )
            instances.append(
                {
                    "id": obj["id"],
                    "label": obj["label"],
                    "score": 1,
                    "num_views": 1,
                    "points_file": "instances/points/" + obj["id"] + ".npy",
                    "best_views": obj["best_views"],
                }
            )
        w.dir("instances").joinpath("instances.json").write_text(json.dumps(instances))
        return LiftManifest(num_instances=2, instances_file="instances/instances.json")


class EmbedFake(Fake):
    name = "embed.fake"
    stage = "embed"
    manifest_type = EmbedManifest
    reads = ["objects", "instances", "mesh"]
    writes = ["embeddings"]

    def embed_text(self, texts, params=None):
        vectors = np.zeros((len(texts), EMBEDDING_DIM), dtype=np.float32)
        for i, text in enumerate(texts):
            if any(word in text.lower() for word in ("chair", "ghế", "sit")):
                vectors[i, 0] = 1
            if any(word in text.lower() for word in ("table", "bàn")):
                vectors[i, 1] = 1
        return vectors

    def rerank(self, query, descriptions, params=None):
        """The cosine of the fake embeddings: 1 for a Description about only what was asked. The
        Stage's fail params fail it as they fail a run."""
        self.fail_if_scripted(params or {})
        if not query.strip():
            raise SceneError("INVALID_PARAMETERS", "The query must not be empty")
        vectors = self.embed_text([query, *descriptions])
        norms = np.linalg.norm(vectors, axis=1)
        if not norms[0]:
            return [0.0] * len(descriptions)
        return [
            float(vector @ vectors[0] / (norm * norms[0])) if norm else 0.0
            for vector, norm in zip(vectors[1:], norms[1:], strict=True)
        ]

    def transform(self, w, p):
        w.dir("embeddings")
        np.savez(
            w.path(SceneResults.EMBEDDINGS),
            ids=np.array([o["id"] for o in OBJECTS]),
            vectors=self.embed_text([o["label"] for o in OBJECTS]),
        )
        w.path(SceneResults.DESCRIPTIONS).write_bytes(DESCRIPTIONS.dump_json(FAKE_DESCRIPTIONS))
        return EmbedManifest(
            model_id="synthetic",
            vlm_model_id="synthetic",
            reranker_model_id="synthetic",
            dim=EMBEDDING_DIM,
            embeddings_file=SceneResults.EMBEDDINGS,
            descriptions_file=SceneResults.DESCRIPTIONS,
        )


def inside_box(positions, box):
    """Indices of positions inside an axis-aligned box (the fake Objects have no yaw)."""
    half = np.asarray(box["size"]) / 2
    return np.flatnonzero(np.all(np.abs(positions - box["center"]) <= half, axis=1))


class ObjectsFake(Fake):
    name = "objects.fake"
    stage = "objects"
    manifest_type = ObjectsManifest
    reads = ["instances", "mesh"]
    writes = ["objects"]

    def transform(self, w, p):
        write_objects(w, OBJECT_LIST.validate_python(OBJECTS))
        # Members are the room's points and vertices inside each Object's box: floor points under
        # the chair and the table. The fake mesh has only the room's corners, so no vertex is inside.
        write_membership(
            w,
            [o["id"] for o in OBJECTS],
            lambda positions: [inside_box(positions, o["box"]) for o in OBJECTS],
        )
        return ObjectsManifest(num_objects=2)
