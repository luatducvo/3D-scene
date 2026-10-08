# Phát triển S3D

Đọc [README](../README.md) để hiểu luồng sử dụng và [AGENTS.md](../AGENTS.md)
trước khi sửa code. Các lệnh dưới đây chạy từ thư mục gốc repository bằng
PowerShell, trừ khi có ghi thư mục khác.

## Chạy native

Cần Python 3.12 qua `uv`, Node.js 24 và npm. Các dịch vụ GPU vẫn chạy bằng Docker.

```powershell
uv sync --project backend --extra dev --frozen
npm ci --prefix frontend
npm run build --prefix frontend
$env:S3D_DATA_DIR = Join-Path (Resolve-Path .).Path '.local-data'
$env:S3D_MODEL_DIR = Join-Path (Resolve-Path .).Path 'models'
$env:S3D_LLM_BASE_URL = 'http://127.0.0.1:8080'
$env:S3D_MASK3D_URL = 'http://127.0.0.1:9000'
uv run --project backend --frozen s3d models pull
docker compose -f compose.yaml -f compose.dev.yaml up -d llm mask3d
uv run --project backend --frozen s3d serve
```

Nếu API Compose đang dùng cổng 8000, dừng dịch vụ đó bằng
`docker compose stop api` trước khi chạy API native. `s3d serve` mở tại
`127.0.0.1:8000`. Cấu hình dev chia sẻ `.local-data` và `models` với dịch vụ GPU;
đường dẫn Windows được chuyển sang `/data` khi gọi Mask3D.

Để dùng hot reload, đặt `$env:S3D_DEV = '1'` trước khi khởi động API. Trong
terminal khác:

```powershell
$env:NEXT_PUBLIC_API_BASE_URL = 'http://127.0.0.1:8000'
npm run dev --prefix frontend
```

Production dùng web static export và API URL tương đối; CORS dev chỉ cho các
origin localhost đã cấu hình.

## Kiểm thử và hợp đồng API

```powershell
cd backend
uv run --frozen pytest
uv run --frozen ruff check . ../tools ../mask3d
uv run --frozen python -m s3d_app.export_openapi --check
cd ../frontend
npm run typecheck
npm test
npm run build
cd ..
uv run tools/test_scannet_prep.py
```

Khi API thay đổi, xuất schema và tạo lại TypeScript types từ thư mục gốc:

```powershell
uv run --project backend --frozen python -m s3d_app.export_openapi
npm run types:api --prefix frontend
```

Commit `backend/openapi.json` và `frontend/src/generated/api.ts` cùng thay đổi
source. Web prebuild kiểm tra hash của schema và API source; types cũ làm build
thất bại. CI chạy kiểm thử CPU, prep độc lập, lint, kiểm tra hợp đồng và web build.

Đánh giá câu hỏi cần model, Scene đã xử lý và API bật `S3D_DEBUG_PROGRAM=1`:

```powershell
uv run --project backend python tools/query_eval.py
```

Đây là so sánh với Program viết tay trên đồ vật được phát hiện, không phải
benchmark ScanRefer ground truth. Kết quả và giới hạn nằm trong
[verification](verification.md).

## Thay đổi GPU hoặc runtime

Backend và Mask3D dùng môi trường Python/CUDA riêng. Đọc Dockerfile tương ứng,
`models.lock`, [ADR về LLM](adr/0007-llm-spike-results.md) và
[ADR về Mask3D](adr/0008-mask3d-spike-results.md) trước khi thay đổi.
Image Mask3D hiện đặt `TORCH_CUDA_ARCH_LIST=8.6`; GPU có kiến trúc khác cần cấu
hình build phù hợp và kiểm chứng lại. Giữ API một process để dùng đúng cơ chế
điều phối GPU hiện tại. Kiểm thử synthetic không thay thế kiểm chứng inference
và VRAM trên GPU thực.
