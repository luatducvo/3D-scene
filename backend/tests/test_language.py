
import pytest

from s3d_app.ask import generate_program, stream_verified_wording
from s3d_app.gpu import GpuCoordinator, InsufficientGpuMemory
from s3d_app.llm import LlmRouter
from s3d_app.vision import chat_with_images, verified_wording


class FakeCloudRouter:
    managed = False

    def __init__(self):
        self.calls = 0

    def chat(self, *args, **kwargs):
        self.calls += 1
        content = "plain prose" if self.calls == 1 else (
            '{"intent":"count","vars":{"t":"chair"},"target":"t"}')
        return {"choices": [{"message": {"content": content}}]}


def test_invalid_json_is_retried_once():
    router = FakeCloudRouter()
    program, retry = generate_program("how many chairs?", ["chair"], router)
    assert program.intent == "count"
    assert retry == 1 and router.calls == 2


def test_wording_rejects_invented_ids_and_counts():
    fallback = "I found 2 chairs."
    assert verified_wording("Object 99 has 7 legs.", fallback, {1, 2}, {2}) == fallback
    assert verified_wording("I found 2 chairs.", fallback, {1, 2}, {2}) == fallback
    assert verified_wording("I found seven chairs.", fallback, {1, 2}, {2}) == fallback


@pytest.mark.parametrize("proposed", ["2.2 chairs", "one hundred chairs", "thirty chairs",
                                       "Object 2 has 2 legs"])
def test_wording_validates_complete_quantities(proposed):
    assert verified_wording(proposed, "fallback", {2}, set()) == "fallback"


def test_stream_never_emits_an_unverified_quantity():
    class FakeRouter:
        managed = False

        def stream_chat(self, *args):
            yield "There are "
            yield "99 "
            yield "chairs."

    emitted = []
    with pytest.raises(ValueError):
        for piece in stream_verified_wording(FakeRouter(), "I found 2 chairs.", {1, 2}, {2}):
            emitted.append(piece)  # noqa: PERF402 - inspect partial output before an exception
    assert "99" not in "".join(emitted)


def test_vision_memory_failure_skips_loading(monkeypatch):
    class FakeRouter:
        managed = True
        did_load = False

        def unload_all(self):
            pass

        def loaded(self):
            return []

        def load(self, model):
            self.did_load = True

    class FakeGpu(GpuCoordinator):
        def wait_for_memory(self, minimum_free_mb, *, timeout=30):
            super().wait_for_memory(minimum_free_mb, timeout=0)

    monkeypatch.setattr("s3d_app.vision.GPU", FakeGpu(lambda: 1000))
    router = FakeRouter()
    with pytest.raises(InsufficientGpuMemory):
        chat_with_images(router, "choose", ["data:image/jpeg;base64,AA"])
    assert not router.did_load


def test_sleeping_router_worker_is_unloaded_before_reloading(monkeypatch):
    router = LlmRouter("http://unused")
    state = {"value": "sleeping"}
    calls = []

    def request(path, body=None):
        calls.append(path)
        if path == "/models/unload":
            state["value"] = "unloaded"
            return {}
        return {"data": [{"id": "text", "status": state.copy()}]}

    monkeypatch.setattr(router, "request", request)
    router.unload_all()
    assert "/models/unload" in calls
    assert state["value"] == "unloaded"
