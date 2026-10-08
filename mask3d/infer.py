"""One-shot ScanNet200 Mask3D inference. The process exits to release CUDA memory."""

import argparse
import json
import time
from pathlib import Path

import MinkowskiEngine as ME
import numpy as np
import torch
from instances import InstanceProposal, dominant_component, select_proposals

from mask3d import get_model, load_mesh


def infer(mesh_path: Path, output: Path, checkpoint: Path, voxel_m: float = 0.02) -> dict:
    started = time.monotonic()
    torch.manual_seed(0)
    np.random.seed(0)
    model = get_model(str(checkpoint)).eval().cuda()
    mesh = load_mesh(str(mesh_path))
    points = np.asarray(mesh.vertices).astype(np.float32)
    colors = np.asarray(mesh.vertex_colors).astype(np.float32)
    colors = (colors - np.asarray([0.47793125906962, 0.4303257521323044, 0.3749598901421883])) / np.asarray(
        [0.2834475483823543, 0.27566157565723015, 0.27018971370874995])
    coordinates = np.floor(points / voxel_m)
    _, _, unique, inverse = ME.utils.sparse_quantize(coordinates=coordinates, features=colors,
                                                   return_index=True, return_inverse=True)
    collated, _ = ME.utils.sparse_collate([torch.from_numpy(coordinates[unique]).int()],
                                         [torch.from_numpy(colors[unique]).float()])
    data = ME.SparseTensor(coordinates=collated, features=torch.from_numpy(colors[unique]).float(),
                           device="cuda")
    raw_coordinates = torch.as_tensor(points[unique], device="cuda")
    with torch.no_grad(), torch.cuda.amp.autocast():
        outputs = model.model(data, raw_coordinates=raw_coordinates, is_eval=True)
    logits = outputs["pred_logits"][0].float().cpu()
    masks = outputs["pred_masks"][0].float().cpu()
    scores, labels = torch.softmax(logits, dim=-1).max(dim=-1)
    raw = []
    for index in range(len(scores)):
        probabilities = torch.sigmoid(masks[:, index])
        active = probabilities > 0.5
        confidence = float(scores[index] * probabilities[active].mean()) if active.any() else 0.0
        if int(labels[index]) < 200 and confidence >= 0.5:
            clean = dominant_component(points, active[inverse].numpy().astype(bool))
            raw.append(InstanceProposal(clean,
                                        int(labels[index]), confidence, "mask3d"))
    instance_ids, rows = select_proposals(raw, len(points))
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_suffix(".partial")
    with partial.open("wb") as handle:
        np.savez_compressed(handle, instance_ids=instance_ids,
                            labels=np.asarray([row["label_id"] for row in rows], dtype=np.int16),
                            confidences=np.asarray([row["confidence"] for row in rows], dtype=np.float32))
    partial.replace(output)
    report = {"instances": len(rows), "vertices": len(points), "voxel_m": voxel_m,
              "seconds": round(time.monotonic() - started, 2),
              "peak_torch_allocated_mb": round(torch.cuda.max_memory_allocated() / 1048576),
              "peak_torch_reserved_mb": round(torch.cuda.max_memory_reserved() / 1048576),
              "proposals": rows}
    output.with_suffix(".json").write_text(json.dumps(report))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mesh", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--checkpoint", type=Path, default=Path("/models/scannet200_val.ckpt"))
    parser.add_argument("--voxel", type=float, choices=[0.02, 0.03, 0.04], default=0.03)
    arguments = parser.parse_args()
    report = infer(arguments.mesh, arguments.output, arguments.checkpoint, arguments.voxel)
    print(json.dumps({key: value for key, value in report.items() if key != "proposals"}), flush=True)
