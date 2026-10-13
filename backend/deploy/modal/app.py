"""Deploy the portable HTTP server; provider SDK usage stays in this file."""
import os
from pathlib import Path
import subprocess

import modal

REPOSITORY = Path(__file__).resolve().parents[3]
app = modal.App(os.environ.get("MODAL_APP_NAME", "scene-compute"))
image = modal.Image.from_dockerfile(
    REPOSITORY / "backend/docker/compute.Dockerfile",
    context_dir=REPOSITORY,
    build_args={"EXTRAS": os.environ.get("COMPUTE_EXTRAS", "")},
)
models = modal.Volume.from_name("scene-models", create_if_missing=True)


@app.function(
    image=image,
    gpu=os.environ.get("MODAL_GPU", "A100-80GB"),
    min_containers=0,
    max_containers=1,
    scaledown_window=600,
    timeout=900,
    startup_timeout=900,
    volumes={"/models": models},
    secrets=[modal.Secret.from_name("scene-compute", required_keys=["COMPUTE_TOKEN"])],
)
@modal.concurrent(max_inputs=16)
@modal.web_server(port=9000, startup_timeout=900)
def serve():
    if not os.environ.get("COMPUTE_TOKEN"):
        raise RuntimeError("COMPUTE_TOKEN must be set for a public compute endpoint")
    subprocess.Popen([
        "/app/.venv/bin/python", "-m", "uvicorn", "scene_compute.server:app",
        "--host", "0.0.0.0", "--port", "9000",
    ])
