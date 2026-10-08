"""Repeatable local JSON-schema smoke test for pinned llama.cpp presets.

Run from a Python environment with Pillow after `docker compose -f compose.yaml
-f compose.dev.yaml up -d llm`; no scene data is sent to an external service.
"""

import base64
import io
import json
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image

BASE_URL = "http://127.0.0.1:8080"
TEXT_CASES = [
    "the chair next to the window", "the bed near the desk", "the lamp on the table",
    "the cabinet behind the chair", "the pillow under the blanket", "the sofa by the wall",
    "the nearest chair to the door", "the largest table", "the smallest lamp",
    "the red chair", "the green plant", "the white cabinet", "the table between the chairs",
    "How many chairs are near the desk?", "How many pillows are on the bed?",
    "Is there a lamp on the table?", "Is any chair next to the window?",
    "What color is the sofa near the door?", "What is behind the bed?",
    "Find the object to the left of the cabinet", "Find the object to the right of the desk",
    "Which table is farthest from the window?", "Which chair is highest?",
    "What is this room used for?", "Describe the furniture in the room.",
]
VISION_CASES = [
    "What colors are these two images?",
    "Which image is red?",
    "Which image is blue?",
    "Is the first image brighter than the second?",
    "Describe the two colors briefly.",
]
PREDICATES = ["NONE", "ON", "UNDER", "NEAR", "FAR", "NEXT_TO", "LEFT", "RIGHT",
              "FRONT", "BEHIND", "BETWEEN", "CLOSEST", "FARTHEST", "LARGEST",
              "SMALLEST", "HIGHEST", "LOWEST", "COLOR"]
SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "enum": ["ground", "count", "exists", "attribute", "open"]},
        "target": {"type": "string"},
        "predicate": {"type": "string", "enum": PREDICATES},
        "anchor": {"type": "string"},
    },
    "required": ["intent", "target", "predicate", "anchor"],
    "additionalProperties": False,
}


def request_json(path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(BASE_URL + path, data=data,
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


def wait_loaded(preset: str) -> None:
    request_json("/models/load", {"model": preset})
    for _ in range(120):
        state = {model["id"]: model["status"]["value"]
                 for model in request_json("/models")["data"]}
        if state.get(preset) == "loaded":
            return
        time.sleep(1)
    raise RuntimeError(f"Model did not load: {preset}")


def image_url(color: str) -> str:
    output = io.BytesIO()
    Image.new("RGB", (768, 768), color).save(output, format="JPEG")
    return "data:image/jpeg;base64," + base64.b64encode(output.getvalue()).decode()


def gpu_used() -> int:
    output = subprocess.check_output(
        ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
        text=True,
    )
    return int(output.strip().splitlines()[0])


def run() -> dict:
    cases = [("qwen3-vl-4b-text", question, False) for question in TEXT_CASES]
    cases += [("qwen3-vl-4b-vision", question, True) for question in VISION_CASES]
    results = []
    baseline = gpu_used()
    red, blue = image_url("red"), image_url("blue")
    for preset in ("qwen3-vl-4b-text", "qwen3-vl-4b-vision"):
        wait_loaded(preset)
        for model, question, has_images in cases:
            if model != preset:
                continue
            content = ([{"type": "text", "text": question},
                        {"type": "image_url", "image_url": {"url": red}},
                        {"type": "image_url", "image_url": {"url": blue}}]
                       if has_images else question)
            body = {
                "model": preset, "messages": [
                    {"role": "system", "content": "Translate the question into a small scene program. Use empty anchor when absent."},
                    {"role": "user", "content": content},
                ],
                "response_format": {"type": "json_schema", "json_schema": {
                    "name": "program", "strict": True, "schema": SCHEMA,
                }},
                "temperature": 0, "max_tokens": 128,
            }
            started = time.monotonic()
            try:
                response = request_json("/v1/chat/completions", body)
                raw = response["choices"][0]["message"]["content"]
                parsed = json.loads(raw)
                valid = (set(parsed) == set(SCHEMA["required"])
                         and parsed["intent"] in SCHEMA["properties"]["intent"]["enum"]
                         and parsed["predicate"] in PREDICATES
                         and isinstance(parsed["target"], str)
                         and isinstance(parsed["anchor"], str))
                error = "" if valid else f"invalid shape: {raw}"
            except (urllib.error.URLError, ValueError, KeyError) as exc:
                valid, error = False, str(exc)
            results.append({"preset": preset, "question": question, "valid": valid,
                            "error": error, "seconds": round(time.monotonic() - started, 2),
                            "gpu_used_mb": gpu_used()})
            print(f"{len(results):02d}/30 {preset}: {'valid' if valid else error}", flush=True)
        request_json("/models/unload", {"model": preset})
        time.sleep(2)
    return {"build": "b11459", "baseline_used_mb": baseline,
            "after_used_mb": gpu_used(), "valid": sum(item["valid"] for item in results),
            "total": len(results), "results": results}


if __name__ == "__main__":
    report = run()
    Path("llm-spike-report.json").write_text(json.dumps(report, indent=2))
    print(f"Valid JSON: {report['valid']}/{report['total']}")
