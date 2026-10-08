import threading
import time

import pytest

from s3d_app.gpu import GpuCoordinator, InsufficientGpuMemory


def test_gpu_reservation_serializes_two_operations() -> None:
    coordinator = GpuCoordinator(lambda: 4096)
    order = []

    def work(name: str) -> None:
        with coordinator.reserve(3500):
            order.append(name + " start")
            time.sleep(0.01)
            order.append(name + " end")

    first = threading.Thread(target=work, args=("first",))
    second = threading.Thread(target=work, args=("second",))
    first.start()
    second.start()
    first.join()
    second.join()
    assert order in (["first start", "first end", "second start", "second end"],
                     ["second start", "second end", "first start", "first end"])


def test_gpu_waits_for_unload_and_reports_missing_vram() -> None:
    free = [100]
    coordinator = GpuCoordinator(lambda: free[0])
    with coordinator.reserve(3500, unload=lambda: free.__setitem__(0, 3800)):
        assert free[0] == 3800
    free[0] = 100
    with pytest.raises(InsufficientGpuMemory, match="close other GPU apps"), coordinator.reserve(
        3500, timeout=0
    ):
        pass


def test_stage_does_not_ignore_unload_failure(monkeypatch):
    import urllib.error

    from s3d_app.pipeline import unload_llm

    def fail(self):
        raise urllib.error.URLError("unreachable")

    monkeypatch.setattr("s3d_app.llm.LlmRouter.unload_all", fail)
    with pytest.raises(RuntimeError, match="Cannot confirm LLM unloading"):
        unload_llm()
