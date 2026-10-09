FROM ghcr.io/astral-sh/uv:0.12.2 AS uv

FROM nvidia/cuda:11.3.1-devel-ubuntu20.04@sha256:e26c89e76b66307f4b7a2bd3e3009c2ec9067be354b12187c44a895657f498f1
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    git build-essential libopenblas-dev ca-certificates && \
    rm -rf /var/lib/apt/lists/*
COPY --from=uv /uv /uvx /usr/local/bin/
ENV UV_PYTHON_INSTALL_DIR=/opt/uv-python \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:/usr/local/cuda/bin:${PATH} \
    FORCE_CUDA=1 \
    TORCH_CUDA_ARCH_LIST=7.5 \
    MAX_JOBS=2
#TORCH_CUDA_ARCH_LIST=7.5
RUN uv python install 3.10 && uv venv /opt/venv --python 3.10
RUN uv pip install --python /opt/venv/bin/python numpy==1.24.2 ninja==1.10.2.3 \
    torch==1.12.1+cu113 torchvision==0.13.1+cu113 \
    --extra-index-url https://download.pytorch.org/whl/cu113
RUN uv pip install --python /opt/venv/bin/python setuptools==65.6.3 wheel pip==23.1
RUN git clone https://github.com/NVIDIA/MinkowskiEngine.git /opt/MinkowskiEngine && \
    cd /opt/MinkowskiEngine && git checkout 02fc608bea4c0549b0a7b00ca1bf15dee4a0b228 && \
    python setup.py install --force_cuda --blas=openblas
RUN git clone https://github.com/cvg/Mask3D.git /opt/Mask3D && \
    cd /opt/Mask3D && git checkout 7ae86b759a1d6838945a5c2e1204effdae1b9d07
RUN uv pip install --python /opt/venv/bin/python \
    hydra-core==1.0.5 omegaconf==2.0.6 albumentations==1.2.1 \
    open3d==0.17.0 scipy==1.9.0 scikit-learn==1.1.2 \
    pytorch-lightning==1.7.2 plyfile==0.7.4 opencv-python-headless==4.7.0.72 \
    "numpy==1.24.2" "setuptools==65.6.3" \
    "torch==1.12.1+cu113" "torchvision==0.13.1+cu113" \
    --extra-index-url https://download.pytorch.org/whl/cu113
RUN uv pip install --python /opt/venv/bin/python \
    torch-scatter==2.1.0+pt112cu113 -f https://data.pyg.org/whl/torch-1.12.1+cu113.html
RUN cd /opt/Mask3D/third_party/pointnet2 && python setup.py install
RUN uv pip install --python /opt/venv/bin/python loguru==0.6.0
RUN apt-get update && apt-get install -y --no-install-recommends \
    libx11-6 libgl1 libgomp1 && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/Mask3D
ENV PYTHONPATH=/opt/Mask3D:/opt/Mask3D/mask3d OMP_NUM_THREADS=4
COPY mask3d/infer.py mask3d/server.py /app/
COPY backend/src/s3d_app/instances.py /app/instances.py
CMD ["python", "/app/server.py"]
