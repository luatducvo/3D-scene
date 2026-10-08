"""Run the pinned ScanNet200 model on a prepared scene and report GPU usage."""

import argparse
import json
import subprocess
import threading
import time
from pathlib import Path

import MinkowskiEngine as ME
import numpy as np
import torch

from mask3d import get_model, load_mesh, prepare_data


def gpu_used_mb() -> int:
    output = subprocess.check_output(
        ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
        text=True, timeout=5,
    )
    return int(output.splitlines()[0].strip())


def run(mesh_path: Path, checkpoint: Path, voxel_m: float = 0.02) -> dict:
    baseline = gpu_used_mb()
    peak_device = baseline
    done = threading.Event()

    def sample() -> None:
        nonlocal peak_device
        while not done.wait(0.1):
            try:
                peak_device = max(peak_device, gpu_used_mb())
            except (OSError, subprocess.SubprocessError, ValueError):
                pass

    observer = threading.Thread(target=sample, daemon=True)
    observer.start()
    started = time.monotonic()
    try:
        model = get_model(str(checkpoint)).eval().cuda()
        mesh = load_mesh(str(mesh_path))
        data, points, colors, _features, unique, inverse = prepare_data(mesh, torch.device("cuda"))
        if voxel_m != 0.02:
            coordinates = np.floor(points / voxel_m)
            _, _, unique, inverse = ME.utils.sparse_quantize(coordinates=coordinates, features=colors,
                                                           return_index=True, return_inverse=True)
            collated, _ = ME.utils.sparse_collate([torch.from_numpy(coordinates[unique]).int()],
                                                 [torch.from_numpy(colors[unique]).float()])
            data = ME.SparseTensor(coordinates=collated, features=torch.from_numpy(colors[unique]).float(),
                                   device="cuda")
        raw_coordinates = torch.as_tensor(points[unique], dtype=torch.float32, device="cuda")
        with torch.no_grad(), torch.cuda.amp.autocast():
            outputs = model.model(data, raw_coordinates=raw_coordinates, is_eval=True)
        logits = outputs["pred_logits"][0].float().cpu()
        masks = outputs["pred_masks"][0].float().cpu()
        labels = torch.softmax(logits, dim=-1)
        scores, label_ids = labels.max(dim=-1)
        instances = []
        for index in range(len(scores)):
            mask = torch.sigmoid(masks[:, index]) > 0.5
            confidence = float(scores[index] * torch.sigmoid(masks[:, index])[mask].mean()) if mask.any() else 0.0
            count = int(mask[inverse].sum())
            if int(label_ids[index]) < 200 and confidence >= 0.5 and count >= 100:
                instances.append({"label_id": int(label_ids[index]), "confidence": confidence,
                                  "vertices": count})
        return {"scene": mesh_path.parent.parent.parent.parent.name, "vertices": len(points),
                "voxel_m": voxel_m, "instances": len(instances), "largest": sorted(
                    instances, key=lambda item: item["vertices"], reverse=True)[:10],
                "seconds": round(time.monotonic() - started, 2),
                "baseline_vram_mb": baseline, "peak_device_vram_mb": peak_device,
                "peak_torch_allocated_mb": round(torch.cuda.max_memory_allocated() / 1048576),
                "peak_torch_reserved_mb": round(torch.cuda.max_memory_reserved() / 1048576)}
    finally:
        done.set()
        observer.join(timeout=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mesh", type=Path)
    parser.add_argument("--checkpoint", type=Path, default=Path("/models/scannet200_val.ckpt"))
    parser.add_argument("--voxel", type=float, default=0.02)
    arguments = parser.parse_args()
    print(json.dumps(run(arguments.mesh, arguments.checkpoint, arguments.voxel)), flush=True)
