# ADR 0007: Keep the two-preset Qwen3-VL-4B router after a local GPU spike

Date: 2026-10-08

## Decision

Keep the `text` and `vision` presets from ADR 0004 on the tested machine. The pinned
llama.cpp image is `server-cuda-b11459` at digest
`sha256:fff6185edd2fbc4093aa5970bf6db53ed11c283e3a1c52a3e244cf27047264f4`
(CUDA 12.8.1). Model and projector are the SHA-256-pinned Qwen releases in `models.lock`.

## Measurements on RTX 3050 6 GiB

The desktop's baseline VRAM use changed as applications closed during the spike, so
measurements should be read as observed states, not a guarantee of future headroom.

| Observation | Result |
| --- | --- |
| Unloaded baseline during 30-case run | 814 MiB used |
| Maximum used with `text` during that run | 3,957 MiB |
| Maximum used with `vision` during that run | 4,678 MiB |
| After both presets unloaded | 917 MiB used |
| Separate two-image test | Two 768×768 JPEGs; answer was "Red and blue."; 5,785 MiB used with other desktop apps open |
| `POST /models/unload` | `GET /models` changed to `unloaded`; free VRAM recovered (3,494 MiB in one measurement) |
| Unloaded model request | HTTP 400 `model is not loaded`; `--no-models-autoload` held |
| JSON schema test | 30/30 structurally valid (25 text, 5 vision) |

The JSON smoke test uses the flat schema and 30 English prompts in
`tools/llm_spike.py`; individual outcomes and timings are in
`docs/spikes/llm-b11459.json`. It checks syntax and enumerated fields, not Program
semantic accuracy or grounding against a processed scene. The two-image test used
solid-color synthetic images. Vision left little headroom in the high-desktop-use
measurement, so GPU admission must read current NVML free memory before loading it.

No 2B vision fallback is needed for this measured configuration. A later failure on
a more heavily loaded desktop should route to Clarify as planned in ADR 0004.
