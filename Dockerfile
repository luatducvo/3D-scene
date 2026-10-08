FROM node:24-alpine AS web
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
COPY backend/openapi.json /app/backend/openapi.json
COPY backend/src/s3d_app/api.py /app/backend/src/s3d_app/api.py
RUN npm run build

FROM ghcr.io/astral-sh/uv:0.12.2 AS uv

FROM python:3.12-slim AS api
COPY --from=uv /uv /uvx /usr/local/bin/
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/src ./src
COPY models.lock /app/models.lock
RUN uv sync --frozen --no-dev
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=web /app/frontend/out /app/web
ENV S3D_WEB_DIR=/app/web S3D_DATA_DIR=/data S3D_INBOX_DIR=/inbox S3D_MODEL_DIR=/models
ENV PATH="/app/backend/.venv/bin:${PATH}"
EXPOSE 8000
CMD ["/app/backend/.venv/bin/uvicorn", "s3d_app.api:app", "--host", "0.0.0.0", "--port", "8000"]
