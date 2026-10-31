# scene-compute on a Google Colab GPU runtime: the notebook cells, one block per cell.
#
# Colab opens only .ipynb files, so this file is kept as text that git can diff. To run it:
# create a notebook in Colab, then paste each block below into its own code cell, in order,
# and run the cells one by one. Each `CELL` banner starts a new cell; its comments can be pasted too.
#
# Lines starting with `!` (shell commands) and `%` (IPython magics) only work inside a
# notebook cell, so this file is not valid Python and Ruff skips it (pyproject.toml).
# backend/deploy/colab/README.md explains each step and what to configure locally.


# ==================================================================================================
# CELL 0 - Step 0: Download model weights to Google Drive
# ==================================================================================================
# Run this once on any runtime, a free CPU runtime is enough, so a GPU runtime never spends time
# downloading. It needs no clone or install and fills the Drive cache that Step 5 checks; Step 5
# stops if any weight is missing. Add `HF_TOKEN` to Colab secrets first, from an account that
# accepted the gated SAM 3 license.
#
# Paste everything below, up to the next CELL banner, into one code cell.

import shutil
import urllib.request
from pathlib import Path

from google.colab import drive, userdata
from huggingface_hub import hf_hub_download, snapshot_download

drive.mount("/content/drive")
# Same layout as Step 5: HF_HOME = MODELS_DIR/hf, TORCH_HOME = MODELS_DIR/torch.
MODELS_DIR = Path("/content/drive/MyDrive/model-weights/models")
HF_CACHE = MODELS_DIR / "hf" / "hub"
TORCH_HOME = MODELS_DIR / "torch"
# Download to the runtime SSD first: the Drive mount mishandles the chunked writes of large
# Hugging Face downloads, which left the big files missing.
LOCAL_CACHE = Path("/content/hf-download")
HF_TOKEN = userdata.get("HF_TOKEN")


def copy_to_drive(snapshot):
    """Copy a local snapshot into the Drive cache as plain files, skipping those already complete."""
    repo_dir = snapshot.parent.parent
    drive_repo = HF_CACHE / repo_dir.name
    for source in sorted(snapshot.rglob("*")):
        if source.is_dir():
            continue
        target = drive_repo / source.relative_to(repo_dir)
        if target.is_file() and target.stat().st_size == source.stat().st_size:
            continue
        print(f"  copy {source.name} ({source.stat().st_size / 1e9:.2f} GB)", flush=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        # Write to a temporary name so an interrupted copy never looks cached.
        partial = target.with_name(target.name + ".part")
        shutil.copyfile(source, partial)
        partial.replace(target)
    (drive_repo / "refs").mkdir(parents=True, exist_ok=True)
    (drive_repo / "refs" / "main").write_text(snapshot.name)


# Mirrors download_weights() in backend/packages/scene-stages/src/scene_stages/gpu.py and mg3d_doc.py;
# keep the model ids in sync with backend/config/pipeline.yaml.
for repo_id in [
    "depth-anything/DA3NESTED-GIANT-LARGE-1.1",
    "Qwen/Qwen3-VL-8B-Instruct",
    "BAAI/bge-m3",
    "BAAI/bge-reranker-v2-m3",
]:
    print(f"download {repo_id}", flush=True)
    copy_to_drive(Path(snapshot_download(repo_id, cache_dir=LOCAL_CACHE, token=HF_TOKEN)))
print("download facebook/sam3 sam3.pt", flush=True)
copy_to_drive(Path(hf_hub_download("facebook/sam3", "sam3.pt", cache_dir=LOCAL_CACHE, token=HF_TOKEN)).parent)

geocalib = TORCH_HOME / "hub" / "geocalib" / "pinhole.tar"
if not geocalib.is_file():
    print("download GeoCalib pinhole", flush=True)
    geocalib.parent.mkdir(parents=True, exist_ok=True)
    partial = geocalib.with_suffix(".part")
    urllib.request.urlretrieve("https://github.com/cvg/GeoCalib/releases/download/v1.0/geocalib-pinhole.tar", partial)
    partial.rename(geocalib)

# Drive uploads new files in the background; wait for it before releasing the runtime.
drive.flush_and_unmount()
shutil.rmtree(LOCAL_CACHE)
print(f"All weights cached in {MODELS_DIR}")


# ==================================================================================================
# CELL 1 - Step 1: Check the GPU
# ==================================================================================================
# Paste everything below, up to the next CELL banner, into one code cell.

!nvidia-smi


# ==================================================================================================
# CELL 2 - Step 2: Install `uv` and Python 3.12
# ==================================================================================================
# Paste everything below, up to the next CELL banner, into one code cell.

!pip install -q uv
!uv python install 3.12


# ==================================================================================================
# CELL 3 - Step 3: Clone the repository
# ==================================================================================================
# Paste everything below, up to the next CELL banner, into one code cell.

import os

REPO_URL = "https://github.com/luatducvo/3D-scene.git"
if not os.path.exists("/content/3D-scene"):
    !git clone $REPO_URL /content/3D-scene

%cd /content/3D-scene


# ==================================================================================================
# CELL 4 - Step 4: Install `scene-compute` dependencies
# ==================================================================================================
# Use `--extra gpu` for Depth Anything 3, SAM 3, GeoCalib, Qwen3-VL, bge-m3 and bge-reranker-v2-m3.
#
# Paste everything below, up to the next CELL banner, into one code cell.

# Install GPU Algorithm dependencies.
!uv sync --python 3.12 --package scene-compute --extra gpu


# ==================================================================================================
# CELL 5 - Step 5: Check model weights on Google Drive
# ==================================================================================================
# Only checks the weights Step 0 downloaded; it never downloads. If any is missing it raises an
# error and stops: run Step 0, then this cell again. Add `HF_TOKEN` to Colab secrets; it is used
# to read file sizes from Hugging Face.
#
# Paste everything below, up to the next CELL banner, into one code cell.

import os
from pathlib import Path

import yaml
from google.colab import drive, userdata
from huggingface_hub import HfApi

drive.mount("/content/drive")
DRIVE_DIR = "/content/drive/MyDrive/model-weights"
MODELS_DIR = f"{DRIVE_DIR}/models"

# Keep disposable Scene data on the runtime SSD and model weights on Drive.
os.environ["DATA_DIR"] = "/content/data"
os.environ["MODELS_DIR"] = MODELS_DIR
os.environ["HF_HOME"] = f"{MODELS_DIR}/hf"
os.environ["TORCH_HOME"] = f"{MODELS_DIR}/torch"
os.environ["MODELS_PIPELINE_CONFIG"] = "/content/3D-scene/backend/config/pipeline.yaml"
os.environ["HF_TOKEN"] = userdata.get("HF_TOKEN")

# Check that every weight Step 0 downloads is complete on Drive; never download here.
# Mirrors download_weights() in backend/packages/scene-stages/src/scene_stages/gpu.py and mg3d_doc.py.
hf_api = HfApi(token=os.environ["HF_TOKEN"])
missing = []


def check_hf(repo_id, filenames=None):
    info = hf_api.model_info(repo_id, files_metadata=True)
    snapshot = Path(os.environ["HF_HOME"]) / "hub" / f"models--{repo_id.replace('/', '--')}" / "snapshots" / info.sha
    files = [s for s in info.siblings if filenames is None or s.rfilename in filenames]
    incomplete = [
        s.rfilename
        for s in files
        if not (snapshot / s.rfilename).is_file()
        or (s.size is not None and (snapshot / s.rfilename).stat().st_size != s.size)
    ]
    if incomplete:
        print(f"MISSING  {repo_id}: {len(incomplete)} of {len(files)} files ({', '.join(incomplete)})")
        missing.append(repo_id)
    else:
        size_gb = sum(s.size or 0 for s in files) / 1e9
        print(f"cached   {repo_id}: {len(files)} files, {size_gb:.1f} GB")


stages = yaml.safe_load(Path(os.environ["MODELS_PIPELINE_CONFIG"]).read_text())["stages"]
check_hf(stages["recon"]["params"]["model_id"])
check_hf("facebook/sam3", ["sam3.pt"])
for key in ("vlm_model_id", "embedder_model_id", "reranker_model_id"):
    check_hf(stages["embed"]["params"][key])
geocalib = Path(os.environ["TORCH_HOME"]) / "hub" / "geocalib" / "pinhole.tar"
if geocalib.is_file():
    print(f"cached   GeoCalib pinhole: {geocalib}")
else:
    print(f"MISSING  GeoCalib pinhole: {geocalib}")
    missing.append("GeoCalib pinhole")

if missing:
    raise RuntimeError(f"Model weights missing on Drive: {', '.join(missing)}. Run Step 0, then this cell again.")

# The compute server must use the cached weights only, never download at run time.
os.environ["HF_HUB_OFFLINE"] = "1"
print("All model weights are cached on Drive.")


# ==================================================================================================
# CELL 6 - Step 6: Start the Cloudflare Tunnel
# ==================================================================================================
# Copy the public HTTPS URL into `COLAB_URL` on your local machine.
#
# Paste everything below, up to the next CELL banner, into one code cell.

import re
import subprocess
import time

# Install cloudflared and forward the compute server on port 9001.
!wget -q -nc https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
!dpkg -i cloudflared-linux-amd64.deb > /dev/null 2>&1
!pkill cloudflared || true
tunnel_proc = subprocess.Popen(
    ["cloudflared", "tunnel", "--url", "http://127.0.0.1:9001"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
)

public_url = None
for _ in range(40):
    line = tunnel_proc.stdout.readline()
    match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
    if match:
        public_url = match.group(0)
        break
    time.sleep(0.5)

print("Public compute URL:", public_url)


# ==================================================================================================
# CELL 7 - Step 7: Start the compute server
# ==================================================================================================
# Add `COMPUTE_TOKEN` to Colab secrets and use the same value locally. Restarting this server
# clears Scene data while preserving model weights on Drive.
#
# Paste everything below, up to the next CELL banner, into one code cell.

# Reuse the model-cache configuration above; never print secrets.
os.environ["COMPUTE_TOKEN"] = userdata.get("COMPUTE_TOKEN")
os.environ["CHUNK_SIZE_MB"] = "100"
os.environ["REQUEST_TIMEOUT_S"] = "300"
os.environ["CLEAN_ON_START"] = "1"

print("Starting scene-compute on port 9001")
!uv run --python 3.12 uvicorn scene_compute.server:app --host 0.0.0.0 --port 9001
