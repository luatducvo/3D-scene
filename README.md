# 3D Scene Understanding System

Hệ thống hiểu không gian và tái tạo cảnh 3D từ ảnh RGB/video: tự động trích xuất keyframe, ước tính camera pose và chiều sâu, căn chỉnh trọng lực (gravity alignment), tái tạo mesh, phân đoạn vật thể 3D, xây dựng Scene Graph và cung cấp giao diện trực quan 3D tương tác kèm tính năng hỏi đáp (Visual QA).

Tài liệu này hướng dẫn chi tiết cách cấu hình và khởi động toàn bộ hệ thống bằng **Docker Compose** (thông qua task runner `tasks.py` hoặc dùng lệnh Docker Compose trực tiếp).

---

## 1. Kiến trúc dịch vụ (Services Architecture)

Hệ thống được chia thành hai nhóm dịch vụ chính kết nối với nhau qua mạng Docker nội bộ `scene-net`:

| Dịch vụ | Docker Image / Build | Cổng exposed | Vai trò |
|---|---|---|---|
| **`postgres`** | `pgvector/pgvector:pg16` | Nội bộ: `5432` | Lưu trữ dữ liệu quan hệ, vector embeddings (`pgvector`), quản lý Job queue và Scene metadata. |
| **`scene-api`** | `backend/docker/python.Dockerfile` | `127.0.0.1:8000` | REST API (FastAPI) & SSE: Tiếp nhận upload ảnh/video, quản lý Scene, truy vấn Scene Graph, hỏi đáp LLM/VLM. |
| **`scene-worker`** | `backend/docker/python.Dockerfile` | Không (chạy ngầm) | Background worker: Lắng nghe hàng đợi Postgres, điều phối thực thi các Stage trong pipeline, publish kết quả vào database. |
| **`scene-compute`** *(tùy chọn)* | `backend/docker/compute.Dockerfile` | `9000` (nội bộ mạng) | GPU server container (profile `local-gpu`): Chạy suy luận các mô hình nặng (Reconstruction, Segmentation, Embeddings) trên GPU cục bộ. |
| **`web`** *(frontend)* | `frontend/Dockerfile` | `127.0.0.1:3000` | Giao diện Next.js: Trực quan hóa 3D Three.js canvas, công cụ đo đạc, tìm kiếm vật thể và chat panel. |

### Cơ chế lưu trữ (Storage Layout)

- **`scene-data`** (Docker named volume): Gắn tại `/data` trong container. Chứa dữ liệu làm việc của các Scene (`/data/scenes/{scene_id}/raw`, kết quả từng Stage) và bản ghi compute run.
- **`postgres-data`** (Docker named volume): Gắn tại `/var/lib/postgresql/data`. Lưu trữ database PostgreSQL.
- **`./models`** (Host bind-mount): Thư mục cache trọng số mô hình AI trên máy host (MapAnything, SAM 3, CLIP...). Thư mục này **không bị xóa** khi chạy lệnh reset volume (`down -v`), giúp tránh việc tải lại hàng chục GB weights.

---

## 2. Yêu cầu trước khi cài đặt (Prerequisites)

1. **Docker Engine & Docker Compose**:
   - Docker phiên bản 24.0+ trở lên.
   - Docker Compose phiên bản v2 trở lên (lệnh `docker compose`).
2. **NVIDIA GPU & Container Toolkit** *(chỉ cần nếu chạy GPU cục bộ)*:
   - Driver NVIDIA tương thích.
   - [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) đã được cài đặt và cấu hình cho Docker runtime.
3. **Python & uv** *(khuyên dùng để sử dụng task runner tiện lợi)*:
   - [uv](https://github.com/astral-sh/uv) (công cụ quản lý Python cực nhanh).
4. **Node.js >= 20 & npm** *(tùy chọn, chỉ cần khi muốn chạy frontend dev trực tiếp trên máy host)*.

---

## 3. Cấu hình biến môi trường (Environment Setup)

Trước khi khởi động, cần tạo các file `.env` cho cả backend và frontend từ các file mẫu:

### 3.1. Cấu hình Backend (`backend/.env`)

Sao chép file mẫu:

```bash
cp backend/.env.example backend/.env
# Trên Windows PowerShell:
# Copy-Item backend\.env.example backend\.env
```

Các biến môi trường chính trong `backend/.env`:

- `PIPELINE_CONFIG`: Đường dẫn file cấu hình pipeline:
  - `/app/backend/config/pipeline.fake.yaml`: Chạy thử nghiệm nhanh (dùng fake algorithm, không cần tải model nặng hoặc GPU).
  - `/app/backend/config/pipeline.fake-gpu.yaml`: Chạy fakes trên Modal.
  - `/app/backend/config/pipeline.yaml`: Chạy với các mô hình AI thật.
- `HOST_MODELS_DIR`: Thư mục lưu cache weights trên host (mặc định `./models`).
- `COMPUTE_TOKEN`: Mã token bí mật dùng để bảo vệ endpoint GPU compute.
- `MODAL_*`, `RUNPOD_*`, `GENERIC_*`: Điền URL/API Key tương ứng nếu bạn chạy compute stage trên dịch vụ GPU đám mây.
- `HF_TOKEN`: Hugging Face Token (bắt buộc nếu tải các mô hình có bản quyền/gated).
- `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`: Cấu hình endpoint LLM tương thích OpenAI để trả lời câu hỏi QA.
- `VLM_BASE_URL`, `VLM_API_KEY`, `VLM_MODEL`: Cấu hình endpoint VLM để trích xuất thuộc tính vật thể.

### 3.2. Cấu hình Frontend (`frontend/.env`)

Sao chép file mẫu:

```bash
cp frontend/.env.example frontend/.env
# Trên Windows PowerShell:
# Copy-Item frontend\.env.example frontend\.env
```

Các biến trong `frontend/.env`:

- `NEXT_PUBLIC_API_URL`: `http://localhost:8000` (địa chỉ browser gọi đến API).
- `API_INTERNAL_URL`: `http://scene-api:8000` (địa chỉ Next.js Server gọi API qua mạng Docker nội bộ `scene-net`).
- `NEXT_PUBLIC_API_MODE`: `http` (mặc định) hoặc `mock` (nếu chạy frontend độc lập với dữ liệu giả lập).

---

## 4. Hướng dẫn khởi động

### Cách 1: Khởi động toàn bộ hệ thống bằng 1 lệnh duy nhất (Khuyên dùng)

Từ thư mục gốc của repository (`d:\repo\3D-scene`), bạn có thể khởi động **toàn bộ hệ thống** (Postgres, API, Worker và Frontend) chỉ với đúng **1 lệnh**:

#### 1. Khởi động (Chế độ tiêu chuẩn: CPU / Remote GPU / Fake pipeline):
```bash
docker compose up -d --build
```
*(Hoặc dùng Task Runner nếu máy có sẵn `uv`: `uv run tasks.py up`)*

#### 2. Khởi động kèm Local GPU (`scene-compute`):
Nếu máy tính có card đồ họa NVIDIA và đã cài đặt NVIDIA Container Toolkit:
```bash
docker compose --profile local-gpu up -d --build
```
*(Hoặc dùng Task Runner: `uv run tasks.py up-local-gpu`)*

#### 3. Dừng toàn bộ hệ thống:
```bash
docker compose down
# Hoặc nếu chạy kèm local GPU:
docker compose --profile local-gpu down
# Hoặc: uv run tasks.py down
```

#### 4. Khởi tạo lại trạng thái trắng (Reset):
Xóa toàn bộ Scenes và Database để bắt đầu lại từ đầu, nhưng **giữ nguyên** cache model weights trong `backend/models`:
```bash
docker compose --profile local-gpu down -v
# Hoặc: uv run tasks.py reset
```

---

### Cách 2: Khởi động riêng lẻ từng phần (Dành cho phát triển chuyên biệt)

Nếu bạn muốn tách biệt Backend và Frontend (ví dụ: phát triển Frontend độc lập với API mock, hoặc chỉ chạy Backend headless):

#### Khởi động riêng Backend:
```bash
docker compose -f backend/compose.yaml --env-file backend/.env up -d --build
# Kèm GPU cục bộ:
docker compose -f backend/compose.yaml --env-file backend/.env --profile local-gpu up -d --build
```

#### Khởi động riêng Frontend:
- **Chạy bằng Docker (cần mạng `scene-net` của Backend đã tạo trước):**
  ```bash
  docker compose -f frontend/compose.yaml --env-file frontend/.env up -d --build
  ```
- **Hoặc chạy trực tiếp trên máy host (hỗ trợ Mock API không cần Backend):**
  ```bash
  cd frontend
  npm ci
  NEXT_PUBLIC_API_MODE=mock npm run dev   # Giao diện chạy tại http://localhost:3000
  ```

---

## 5. Kiểm tra và sử dụng hệ thống

Sau khi các dịch vụ đã khởi động thành công:

1. **Frontend Web UI**: Truy cập [http://localhost:3000](http://localhost:3000)
   - Tải lên ảnh phòng hoặc video.
   - Bấm nút **Process** để tiến hành tái tạo cảnh 3D.
   - Tương tác với không gian 3D, đo đạc khoảng cách và hỏi đáp thông tin phòng qua thanh Chat.

2. **Backend API Documentation**: Truy cập Swagger UI tại [http://localhost:8000/docs](http://localhost:8000/docs)
   - Kiểm tra các endpoint quản lý scene: `GET /api/v1/scenes`, `POST /api/v1/scenes/{scene_id}/process`.

3. **Kiểm tra Logs thời gian thực**:
   - Theo dõi logs toàn bộ backend:
     ```bash
     docker compose -f backend/compose.yaml logs -f
     ```
   - Theo dõi riêng worker xử lý pipeline:
     ```bash
     docker compose -f backend/compose.yaml logs -f scene-worker
     ```
   - Theo dõi logs frontend:
     ```bash
     docker compose -f frontend/compose.yaml logs -f web
     ```

4. **Kiểm tra trạng thái Container**:
   ```bash
   docker compose -f backend/compose.yaml ps
   docker compose -f frontend/compose.yaml ps
   ```

---

## 6. Các lệnh hữu ích khác

| Tác vụ | Lệnh |
|---|---|
| Tải trước model weights vào `./models` | `uv run tasks.py download-models` |
| Kiểm tra dung lượng Docker volumes & cache model | `uv run tasks.py disk-usage` |
| Chạy bộ kiểm thử tự động (Pytest với test DB riêng) | `uv run tasks.py test` |
| Xuất schema OpenAPI sang file json | `uv run tasks.py openapi` |
| Đồng bộ kiểu dữ liệu OpenAPI sang frontend | `cd frontend && npm run api:sync` |
| Build image GPU compute | `uv run tasks.py compute-image --image <tag>` |
| Deploy `scene-compute` lên Modal | `uv run tasks.py deploy-modal --variant [fake\|recon\|perception]` |

---

## 7. Xử lý sự cố thường gặp (Troubleshooting)

- **Lỗi `network scene-net declared as external, but could not be found` khi bật Frontend:**
  - *Nguyên nhân:* Frontend yêu cầu mạng `scene-net` đã được tạo bởi backend.
  - *Khắc phục:* Khởi động backend trước (`uv run tasks.py up`), hoặc tạo mạng thủ công bằng lệnh `docker network create scene-net`.
- **Lỗi `could not select device driver "" with capabilities: [[gpu]]`:**
  - *Nguyên nhân:* Máy chưa cài đặt hoặc cấu hình NVIDIA Container Toolkit.
  - *Khắc phục:* Cài đặt NVIDIA Container Toolkit hoặc khởi động hệ thống mà không dùng flag GPU: chạy `uv run tasks.py up` thay vì `up-local-gpu`.
- **Lỗi `SCENE_LOCKED` hoặc `SCENE_BUSY` khi gọi API:**
  - Theo thiết kế vòng đời Scene, một Scene đang trong tiến trình xử lý Job thì không nhận thêm file tải lên hoặc lệnh xử lý mới cùng lúc. Hãy chờ Job hiện tại hoàn tất hoặc kiểm tra log của `scene-worker`.
- **Thay đổi file cấu hình `pipeline.yaml` hoặc `compute.yaml` không có hiệu lực:**
  - Khởi động lại các container để nạp cấu hình mới:
    ```bash
    docker compose -f backend/compose.yaml restart scene-api scene-worker
    ```

---

## 8. Tài liệu tham khảo thêm

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): Kiến trúc hệ thống chi tiết, thiết kế module và storage layout.
- [docs/SPEC.md](docs/SPEC.md): Đặc tả yêu cầu kỹ thuật và user stories.
- [GLOSSARY.md](GLOSSARY.md): Thuật ngữ chuẩn trong toàn bộ dự án.
- [docs/ADR-0001-worker-publishes-scene-graph.md](docs/ADR-0001-worker-publishes-scene-graph.md): Quyết định kiến trúc về publication và database ownership.
