# Hệ thống thấu hiểu không gian 3D (3D Scene Understanding System)

[English](README.md) | [Tiếng Việt](README.vi.md)

Chuyển đổi ảnh RGB hoặc video ngắn của một căn phòng thành một Scene 3D theo tỉ lệ thực (metric): Lựa chọn Keyframe, ước tính góc chụp camera và độ sâu (depth), căn chỉnh theo phương trọng lực, tạo đám mây điểm dày đặc (dense point cloud) và lưới 3D (mesh), nhận diện các Object 3D từ vựng mở (open-vocabulary), xây dựng biểu đồ không gian (Scene Graph), cùng một trình xem 3D trực quan hỗ trợ hỏi đáp chuẩn xác (grounded question answering) bằng tiếng Việt hoặc tiếng Anh.

Chạy cục bộ cho một người dùng (single user). Tất cả dịch vụ chạy qua Docker Compose; các Stage nặng chạy trên một GPU host do bạn cấu hình. Nếu là người mới với dự án, hãy đọc trước [docs/architecture/overview.md](docs/architecture/overview.md).

## Các dịch vụ (Services)

| Dịch vụ | Cổng (Port) | Vai trò |
|---|---|---|
| `postgres` (pgvector) | nội bộ 5432 | Lưu trữ Scene, hàng đợi Job, sự kiện tiến độ, Object và vector embeddings |
| `scene-api` | `127.0.0.1:8000` | REST + SSE API, tìm kiếm, hỏi đáp (question answering) |
| `scene-worker` | không có | Thực thi Job trên GPU Target và xuất bản (publish) kết quả |
| `scene-compute` *(profile `local-gpu`)* | nội bộ 9000 | GPU server trên NVIDIA GPU cục bộ |
| `frontend` | `127.0.0.1:3000` | Giao diện Next.js: tải ảnh/video, xem tiến độ, 3D viewer, công cụ đo, hỏi đáp |

Lưu trữ: Các Docker volume `scene-data` và `postgres-data` giữ toàn bộ trạng thái hệ thống và sẽ bị xóa khi reset. Trọng số mô hình (model weights) được lưu tạm (cache) tại thư mục host `./models` và được giữ lại khi reset.

## Yêu cầu môi trường (Prerequisites)

- Docker Engine 24+ đi kèm Compose v2.
- [uv](https://github.com/astral-sh/uv) để chạy task runner và các công cụ Python.
- Một GPU Target: host từ xa (Vast.ai, Colab, Modal, RunPod, hoặc bất kỳ máy Docker nào) hoặc NVIDIA GPU cục bộ có cài [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html). Pipeline thực tế cần tối thiểu 48 GB VRAM. Pipeline giả lập (fake pipeline) không cần GPU.
- Node.js 20+ và npm, chỉ cần khi chạy riêng frontend bên ngoài Docker.

## Cấu hình (Configure)

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

Trên Windows PowerShell, sử dụng `Copy-Item backend\.env.example backend\.env` (tương tự cho frontend).

Các biến môi trường chính trong `backend/.env` (file example có chú thích chi tiết cho các biến còn lại):

| Biến | Ý nghĩa |
|---|---|
| `PIPELINE_CONFIG` | `pipeline.fake.yaml` (giả lập trên CPU, không cần GPU), `pipeline.fake-gpu.yaml` (giả lập trên `GPU_TARGET`) hoặc `pipeline.yaml` (mô hình thật) |
| `GPU_TARGET` | Tên một Target trong [compute.yaml](backend/config/compute.yaml). Không có giá trị mặc định; worker sẽ từ chối khởi động nếu thiếu biến này khi pipeline cần GPU. |
| `VAST_URL`, `COLAB_URL`, `MODAL_COMPUTE_URL`, ... | URL của Target mà bạn sử dụng |
| `COMPUTE_TOKEN` | Khóa bí mật dùng chung để bảo vệ các endpoint GPU từ xa |
| `HF_TOKEN` | Hugging Face token cho các trọng số mô hình có kiểm soát truy cập (SAM 3) |
| `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` | Bất kỳ endpoint tương thích OpenAI nào dùng cho tính năng hỏi đáp |
| `COMPUTE_IMAGE_REPO` | Docker Hub repository chứa GPU image |

`frontend/.env` thiết lập `NEXT_PUBLIC_API_URL` (trình duyệt → API), `API_INTERNAL_URL` (Next.js server → API thông qua mạng `scene-net`) và `NEXT_PUBLIC_API_MODE` (`http` hoặc `mock`).

## Khởi chạy (Run)

Từ thư mục gốc của repository:

```bash
uv run tasks.py up
```

Lệnh này sẽ khởi động Postgres, API, worker và giao diện web từ [compose.yaml](compose.yaml), file Compose duy nhất. Các profile là `backend`, `frontend` và `local-gpu`: `uv run tasks.py up backend` (hoặc `up frontend`) chỉ khởi động một phần. Nếu sử dụng GPU cục bộ, hãy dùng `uv run tasks.py up-local-gpu`. Để dừng hệ thống: `uv run tasks.py down`; để xóa toàn bộ Scene và database nhưng vẫn giữ lại model weights: `uv run tasks.py reset`.

Sau đó mở:

- Giao diện Web: <http://localhost:3000>. Tạo một Scene, tải ảnh hoặc video lên, nhấn Process, sau đó khám phá không gian 3D, đo đạc kích thước và đặt câu hỏi.
- Tài liệu API (Swagger UI): <http://localhost:8000/docs>.

Xem logs: `docker compose logs -f scene-worker` (hoặc `scene-api`, `frontend`).

Nếu chỉ muốn chạy riêng Frontend kết nối với mock backend (không cần Docker, không cần GPU):

```bash
cd frontend
npm ci
NEXT_PUBLIC_API_MODE=mock npm run dev
```

## Các lệnh công việc (Tasks)

Chạy `uv run tasks.py --help` để xem danh sách đầy đủ. Các lệnh thường dùng:

| Tác vụ | Lệnh |
|---|---|
| Chạy kiểm thử backend (database kiểm thử dùng một lần) | `uv run tasks.py test` |
| Xuất hợp đồng API (OpenAPI) | `uv run tasks.py openapi`, sau đó `cd frontend && npm run api:sync` |
| Tải trọng số mô hình vào `./models` | `uv run tasks.py download-models` |
| Xem dung lượng volume và bộ nhớ đệm mô hình | `uv run tasks.py disk-usage` |
| Build / push GPU image | `uv run tasks.py compute-image` / `push-compute-image` |
| Triển khai lên Modal (build từ xa) | `uv run tasks.py deploy-modal` |

## Build và push GPU image

Vast.ai, RunPod và các Docker host thông thường sẽ pull image `scene-compute` từ Docker Hub; Modal sẽ tự build. Có 2 biến thể:

| Biến thể | Cờ (Flag) | Nội dung | Tag |
|---|---|---|---|
| fake | *(không có)* | Chỉ gồm các thuật toán giả lập; dung lượng nhẹ, dùng để kiểm tra kết nối với nhà cung cấp | `fake-<git short sha>` |
| gpu | `--extras gpu` | Toàn bộ thuật toán GPU thực tế trong 1 image ([ADR-0002](docs/adr/0002-single-gpu-image-ultralytics-sam3.md)); dung lượng trên 10 GB | `gpu-<git short sha>` |

1. Tạo một repository trên Docker Hub (chọn public nếu dùng Vast.ai) và đăng nhập `docker login -u <user>` bằng personal access token.
2. Thiết lập `COMPUTE_IMAGE_REPO=<user>/scene-compute` trong `backend/.env`.
3. Commit mã nguồn trước: tag được lấy từ commit `HEAD`, nhưng build context là working tree hiện tại.
4. Chạy `uv run tasks.py push-compute-image --extras gpu` (hoặc bỏ `--extras` nếu chỉ build bản fake). Quá trình sẽ build cho nền tảng `linux/amd64` (máy build không cần GPU), push lên hub và in ra tag cùng digest. Luôn sử dụng tag hoặc digest cụ thể, không dùng `latest`, và ghi lại digest vào nhật ký kiểm tra trực tiếp trong [docs/GPU-INTEGRATION.md](docs/GPU-INTEGRATION.md).
5. Kiểm tra image trên máy có GPU: `docker run --rm --gpus all -p 127.0.0.1:9000:9000 <image>`, sau đó mở `http://localhost:9000/ping` và `/info`.

Sau đó cấu hình nhà cung cấp tương ứng ([backend/deploy/](backend/deploy/)) và đặt biến `GPU_TARGET`.

## Khắc phục sự cố (Troubleshooting)

| Hiện tượng | Cách xử lý |
|---|---|
| `could not select device driver "" with capabilities: [[gpu]]` | Cài đặt NVIDIA Container Toolkit, hoặc dùng lệnh `up` thay cho `up-local-gpu` |
| `SCENE_BUSY` / `SCENE_LOCKED` | Có Job đang chạy, hoặc Scene đã được xử lý xong: hãy đợi hoặc tạo một Scene mới |
| `COMPUTE_UNAVAILABLE` khi upload hoặc search | GPU Target chưa chạy hoặc URL trong `backend/.env` không còn hiệu lực; hãy sửa lại URL và chạy `uv run tasks.py up` |
| `Pass --image or set COMPUTE_IMAGE_REPO` | Điền `COMPUTE_IMAGE_REPO` vào `backend/.env` hoặc truyền cờ `--image` |
| `denied: requested access to the resource is denied` khi push | Chạy lại `docker login` với token có quyền đọc/ghi (read/write); tag phải bắt đầu bằng username của bạn |
| Thay đổi `pipeline.yaml`, `compute.yaml` hoặc `.env` nhưng không có tác dụng | Worker chỉ đọc cấu hình khi khởi động: chạy `uv run tasks.py up` để tạo lại các container |

## Tài liệu tham khảo (Documentation)

| Tài liệu | Nội dung |
|---|---|
| [docs/architecture/](docs/architecture/overview.md) | Cách hệ thống hoạt động, bắt đầu từ bài viết tổng quan |
| [docs/SPEC.md](docs/SPEC.md) | Phạm vi, user stories, tiêu chuẩn nghiệm thu và các điểm nối kiểm thử (test seams) |
| [CONTEXT.md](CONTEXT.md) | Từ điển và thuật ngữ miền (Domain language) |
| [docs/adr/](docs/adr/) | Các bản ghi quyết định kiến trúc (Architecture decisions) |
| [docs/GPU-INTEGRATION.md](docs/GPU-INTEGRATION.md) | Giao diện các mô hình và nhật ký kiểm tra GPU trực tiếp |
| [backend/deploy/](backend/deploy/) | Hướng dẫn triển khai chi tiết cho từng nhà cung cấp |
| [docs/architecture/frontend.md](docs/architecture/frontend.md) | Quyết định thiết kế giao diện UI, cách chạy và quy trình kiểm tra frontend |
