"""Small llama.cpp router client. The same chat endpoint can target a cloud base URL."""

import json
import os
import time
import urllib.error
import urllib.request
from contextlib import contextmanager


@contextmanager
def model_session(router, preset: str, minimum_free_mb: int, gpu):
    """Hold the shared admission lock throughout local inference."""
    if not router.managed:
        yield
        return
    with gpu.reserve(0):
        if preset not in router.loaded():
            router.unload_all()
            gpu.wait_for_memory(minimum_free_mb)
            router.load(preset)
        yield


class LlmRouter:
    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or os.getenv("S3D_LLM_BASE_URL", "http://llm:8080")).rstrip("/")
        self.managed = os.getenv("S3D_LLM_MANAGED", "1") == "1"

    def request(self, path: str, body: dict | None = None) -> dict:
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json"}
        if os.getenv("S3D_LLM_API_KEY"):
            headers["Authorization"] = "Bearer " + os.environ["S3D_LLM_API_KEY"]
        request = urllib.request.Request(self.base_url + path, data=data, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"LLM request failed ({exc.code}): {detail[:1000]}") from exc

    def loaded(self) -> list[str]:
        if not self.managed:
            return []
        return [model["id"] for model in self.request("/models")["data"]
                if model["status"]["value"] == "loaded"]

    def resident(self) -> list[str]:
        if not self.managed:
            return []
        return [model["id"] for model in self.request("/models")["data"]
                if model["status"]["value"] in {"loaded", "sleeping", "loading"}]

    def unload_all(self) -> None:
        for model in self.resident():
            self.request("/models/unload", {"model": model})
        for _ in range(120):
            if not self.resident():
                return
            time.sleep(0.25)
        raise TimeoutError("llm did not release its loaded model")

    def load(self, preset: str) -> None:
        if not self.managed:
            return
        if preset in self.loaded():
            return
        self.unload_all()
        self.request("/models/load", {"model": preset})
        for _ in range(120):
            if preset in self.loaded():
                return
            time.sleep(0.25)
        raise TimeoutError(f"llm did not load preset {preset}")

    def chat(self, preset: str, messages: list[dict], response_format: dict | None = None,
             *, max_tokens: int = 256) -> dict:
        body = {"model": preset, "messages": messages, "max_tokens": max_tokens}
        if not self.managed:
            body["model"] = os.getenv("S3D_LLM_MODEL", preset)
        if response_format is not None:
            body["response_format"] = response_format
        return self.request("/chat/completions" if self.base_url.endswith("/v1")
                            else "/v1/chat/completions", body)

    def stream_chat(self, preset: str, messages: list[dict]):
        body = {"model": preset if self.managed else os.getenv("S3D_LLM_MODEL", preset),
                "messages": messages, "max_tokens": 128, "stream": True}
        headers = {"Content-Type": "application/json"}
        if os.getenv("S3D_LLM_API_KEY"):
            headers["Authorization"] = "Bearer " + os.environ["S3D_LLM_API_KEY"]
        path = "/chat/completions" if self.base_url.endswith("/v1") else "/v1/chat/completions"
        request = urllib.request.Request(self.base_url + path, json.dumps(body).encode(), headers)
        with urllib.request.urlopen(request, timeout=120) as response:
            for raw in response:
                line = raw.decode("utf-8").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    return
                choices = json.loads(data).get("choices", [])
                if choices:
                    content = choices[0].get("delta", {}).get("content")
                    if content:
                        yield content
