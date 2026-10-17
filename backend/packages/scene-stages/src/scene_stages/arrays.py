"""The array module a geometry Stage computes with: NumPy, or CuPy on the GPU.

CuPy mirrors the NumPy API, so one implementation serves both: tests run it on NumPy without a GPU,
and a CUDA compute Target runs the same code on CuPy. A Stage chooses with its `device` parameter.
"""

import numpy as np
from scene_core.errors import SceneError


def array_module(params):
    """NumPy for `device: cpu` (the default), CuPy for `device: cuda`; no fallback between them."""
    device = params.get("device", "cpu")
    if device == "cpu":
        return np
    if device != "cuda":
        raise ValueError("device must be cpu or cuda")
    try:
        import cupy

        if cupy.cuda.runtime.getDeviceCount() < 1:
            raise RuntimeError("no CUDA device")
    except (ImportError, RuntimeError) as exc:
        raise SceneError(
            "GPU_REQUIRED", f"device: cuda needs CuPy and a CUDA GPU on the compute Target: {exc}"
        ) from exc
    return cupy


def to_numpy(array):
    """A NumPy copy of a NumPy or CuPy array."""
    return array.get() if hasattr(array, "get") else np.asarray(array)
