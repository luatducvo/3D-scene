"""Single-process GPU admission lock used by stages and local LLM requests."""

import subprocess
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager


class InsufficientGpuMemory(RuntimeError):
    """The Windows desktop left too little VRAM for a requested operation."""


def free_vram_mb() -> int:
    try:
        import pynvml
    except ImportError:
        pass
    else:
        try:
            pynvml.nvmlInit()
            try:
                info = pynvml.nvmlDeviceGetMemoryInfo(pynvml.nvmlDeviceGetHandleByIndex(0))
                return int(info.free / 1048576)
            finally:
                pynvml.nvmlShutdown()
        except pynvml.NVMLError:
            pass
    output = subprocess.check_output(
        ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
        text=True, timeout=10,
    )
    return int(output.strip().splitlines()[0])


class GpuCoordinator:
    def __init__(self, measure: Callable[[], int] = free_vram_mb):
        self._measure = measure
        self._lock = threading.Lock()

    def wait_for_memory(self, minimum_free_mb: int, *, timeout: float = 30) -> None:
        deadline = time.monotonic() + timeout
        while self._measure() < minimum_free_mb:
            if time.monotonic() >= deadline:
                raise InsufficientGpuMemory(
                    f"Need {minimum_free_mb} MiB free GPU memory; close other GPU apps and retry"
                )
            time.sleep(min(1, max(0, deadline - time.monotonic())))

    @contextmanager
    def reserve(self, minimum_free_mb: int, *, timeout: float = 60,
                unload: Callable[[], None] | None = None) -> Iterator[None]:
        """Hold the only GPU slot after any loaded model releases its VRAM."""
        with self._lock:
            if unload is not None:
                unload()
            self.wait_for_memory(minimum_free_mb, timeout=timeout)
            yield


GPU = GpuCoordinator()


def used_vram_mb() -> int:
    output = subprocess.check_output(
        ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
        text=True, timeout=10)
    return int(output.strip().splitlines()[0])


class VramMeter:
    def __enter__(self):
        self.baseline = used_vram_mb()
        self.peak = self.baseline
        self.stop = threading.Event()

        def sample():
            while not self.stop.wait(0.2):
                try:
                    self.peak = max(self.peak, used_vram_mb())
                except (OSError, subprocess.SubprocessError, ValueError):
                    pass

        self.thread = threading.Thread(target=sample, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.stop.set()
        self.thread.join(timeout=2)
        self.end = used_vram_mb()

    def report(self) -> dict:
        return {"baseline_vram_mb": self.baseline, "peak_device_vram_mb": self.peak,
                "peak_vram_mb": max(0, self.peak - self.baseline), "end_vram_mb": self.end}
