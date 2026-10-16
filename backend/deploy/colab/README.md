# Google Colab GPU Target

Tài liệu hướng dẫn triển khai `scene-compute` (GPU inference server) trên **Google Colab** (hỗ trợ cả tài khoản Colab Free T4 và Colab Pro L4/A100) để phục vụ tính toán cho hệ thống 3D Scene Understanding trên máy local của bạn.

---

## 1. Cơ chế hoạt động

```
[Máy Local của bạn]                                [Google Colab (GPU Cloud)]
- Next.js Web App                                 - NVIDIA GPU (T4 / L4 / A100)
- FastAPI scene-api                               - scene-compute (FastAPI uvicorn:9000)
- PostgreSQL (pgvector)                           - Cloudflare Tunnel (cloudflared)
- scene-worker -------- HTTP (Tunnel URL) -------> https://xxxx.trycloudflare.com
  (upload 25MB chunks, kích hoạt GPU Stage,
   poll tiến độ, tải kết quả về)
```

- Hệ thống phân chia theo kiến trúc SOLID: toàn bộ frontend, API và database chạy tại local.
- Chỉ các stage cần GPU (`recon.da3`, `align.geocalib_ransac`, `segment.sam3`, `embed.metaclip2`) được worker gửi qua HTTP contract tới Google Colab.
- Mọi request đều hoàn thành dưới 30 giây, dữ liệu truyền theo từng chunk 25 MB nên không bị giới hạn bởi timeout hay payload limits của Cloudflare / Ngrok tunnel.

---

## 2. Các bước triển khai trên Google Colab

Bạn có thể mở file notebook có sẵn: `backend/deploy/colab/scene_compute_colab.ipynb` hoặc tạo một Colab Notebook mới và chạy các cell sau.

### Bước 2.1: Chọn GPU Runtime trên Google Colab
1. Vào menu **Runtime** → **Change runtime type**.
2. Chọn **T4 GPU** (hoặc A100 / L4 nếu bạn có Colab Pro).
3. Bấm **Save**.

### Bước 2.2: Tải repository và chuẩn bị môi trường

Chạy cell sau trên Colab để cài đặt `uv`, Python 3.12 và tải mã nguồn:

```python
# 1. Cài đặt uv (trình quản lý package siêu nhanh)
!pip install -q uv
!uv python install 3.12

# 2. Clone mã nguồn repo (thay URL bằng repo của bạn hoặc upload zip)
# Nếu là repo private, bạn có thể truyền kèm GitHub Token: https://<TOKEN>@github.com/<USER>/3D-scene.git
!git clone https://github.com/<YOUR_GITHUB_USERNAME>/3D-scene.git /content/3D-scene
%cd /content/3D-scene
```

> **Mẹo nếu repo đang ở local chưa push lên Git:**  
> Bạn có thể nén thư mục dự án (loại trừ `.venv`, `.git`, `data`, `models`) thành file `.zip`, upload lên Colab rồi chạy `!unzip -q 3D-scene.zip -d /content/3D-scene && %cd /content/3D-scene`.

### Bước 2.3: Cài đặt phụ thuộc cho `scene-compute`

- **Nếu muốn test kết nối nhanh (Fake GPU):**
  ```bash
  !uv sync --python 3.12 --package scene-compute
  ```

- **Nếu chạy Model GPU thực tế (Full GPU):**
  ```bash
  !uv sync --python 3.12 --package scene-compute --extra gpu
  ```

### Bước 2.4: Mount Google Drive để lưu trữ Model Weights (Khuyên dùng)

Các mô hình AI (Depth Anything 3, SAM 3, MetaCLIP 2, GeoCalib) có dung lượng khá lớn (> 10 GB). Ổ đĩa `/content` của Colab sẽ bị xóa sạch mỗi khi phiên làm việc bị ngắt. **Bằng cách gắn (mount) Google Drive**, toàn bộ model weights sẽ được tải và lưu vĩnh viễn trên Drive của bạn:
- Lần đầu: Tải weights về Google Drive (khoảng vài phút).
- Các lần sau: Chỉ cần mount Drive là có thể chạy ngay lập tức, không tốn thời gian tải lại!

```python
# Gắn kết nối với Google Drive của bạn
from google.colab import drive
drive.mount('/content/drive')

import os
# Tạo thư mục lưu weights trên Google Drive
DRIVE_DIR = "/content/drive/MyDrive/3D-scene"
MODELS_DIR = f"{DRIVE_DIR}/models"
os.makedirs(MODELS_DIR, exist_ok=True)

# Thiết lập biến môi trường trỏ vào Google Drive
os.environ["DATA_DIR"] = "/content/data"        # Data scene tạm để ở SSD Colab cho nhanh
os.environ["MODELS_DIR"] = MODELS_DIR          # Weights lưu vĩnh viễn trên Drive
os.environ["HF_HOME"] = f"{MODELS_DIR}/hf"
os.environ["TORCH_HOME"] = f"{MODELS_DIR}/torch"
os.environ["MODELS_PIPELINE_CONFIG"] = "/content/3D-scene/backend/config/pipeline.yaml"

# Thêm HF_TOKEN nếu cần cho các weights yêu cầu access (như SAM 3)
# os.environ["HF_TOKEN"] = "hf_xxx"

# Tải weights về Drive (chỉ cần chạy lần đầu tiên)
!uv run --python 3.12 python -m scene_compute.download_models
```

### Bước 2.5: Cài đặt Cloudflare Tunnel (Miễn phí, không cần đăng ký)

Cloudflare Tunnel (`cloudflared`) sẽ mở đường hầm HTTPS từ Colab ra internet hoàn toàn miễn phí:

```python
import subprocess, time, re

# Tải và cài đặt cloudflared
!wget -q -nc https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
!dpkg -i cloudflared-linux-amd64.deb > /dev/null 2>&1

# Chạy tunnel ngầm chuyển tiếp port 9000
!pkill cloudflared || true
tunnel_proc = subprocess.Popen(
    ["cloudflared", "tunnel", "--url", "http://127.0.0.1:9000"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True
)

# Đọc URL từ log tunnel
public_url = None
for _ in range(30):
    line = tunnel_proc.stdout.readline()
    match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
    if match:
        public_url = match.group(0)
        break
    time.sleep(0.5)

print("="*60)
print(f"URL PUBLIC CỦA BẠN: {public_url}")
print("="*60)
```

*(Ghi chú: Nếu bạn muốn dùng **ngrok**, chỉ cần `!pip install pyngrok` và chạy `ngrok.connect(9000)`).*

### Bước 2.6: Khởi chạy `scene-compute` Server

Đặt `COMPUTE_TOKEN` (khớp với token bạn sẽ điền ở máy local):

```python
import os
token = "my-secret-token" # Đặt token bảo mật tùy ý

# Thư mục models trên Google Drive
MODELS_DIR = "/content/drive/MyDrive/3D-scene/models"

os.environ["COMPUTE_TOKEN"] = token
os.environ["PORT"] = "9000"
os.environ["DATA_DIR"] = "/content/data"
os.environ["MODELS_DIR"] = MODELS_DIR
os.environ["HF_HOME"] = f"{MODELS_DIR}/hf"
os.environ["TORCH_HOME"] = f"{MODELS_DIR}/torch"
os.environ["CHUNK_SIZE_MB"] = "25"

!uv run --python 3.12 uvicorn scene_compute.server:app --host 0.0.0.0 --port 9000
```

---

## 3. Cấu hình máy local để kết nối tới Colab

Mở file `backend/.env` trên máy của bạn và cập nhật:

```env
# 1. Chọn target colab
GPU_TARGET=colab

# 2. Dán URL Cloudflare lấy được từ Colab ở Bước 2.5
COLAB_URL=https://<subdomain>.trycloudflare.com

# 3. Điền COMPUTE_TOKEN khớp với Bước 2.6
COMPUTE_TOKEN=my-secret-token

# 4. Pipeline muốn chạy:
# Thử nghiệm với fake trước:
# PIPELINE_CONFIG=/app/backend/config/pipeline.fake-gpu.yaml
# Chạy mô hình thật:
PIPELINE_CONFIG=/app/backend/config/pipeline.yaml
```

Sau khi lưu file `.env`, khởi động lại hệ thống container trên máy local:

```bash
uv run tasks.py up
```

---

## 4. Kiểm tra kết nối (Smoke Test)

Từ máy local (trong PowerShell hoặc Git Bash), kiểm tra endpoint Colab:

1. **Kiểm tra readiness probe:**
   ```bash
   curl -i https://<subdomain>.trycloudflare.com/ping
   ```
   *Kết quả mong đợi:* `HTTP/1.1 200 OK` (hoặc `204` nếu đang khởi tạo).

2. **Kiểm tra thông tin GPU và algorithms đã cài:**
   ```bash
   curl -H "X-Compute-Token: my-secret-token" https://<subdomain>.trycloudflare.com/info
   ```
   *Kết quả mong đợi:* JSON trả về phiên bản image, tên GPU (ví dụ `Tesla T4`) và danh sách algorithms (`recon.da3`, `align.geocalib_ransac`, `segment.sam3`, `embed.metaclip2`).

Bây giờ bạn có thể mở giao diện web (`http://localhost:3000`), upload ảnh và bắt đầu xử lý scene. Quá trình tính toán GPU nặng sẽ được thực hiện hoàn toàn trên Google Colab!

---

## 5. Lưu ý quan trọng khi dùng Google Colab

1. **VRAM của GPU T4 (Free Tier):**
   - Colab Free cung cấp GPU NVIDIA T4 (~15 GB VRAM).
   - Với Depth Anything 3 + SAM 3 + MetaCLIP 2, hãy giữ `max_keyframes` trong `backend/config/pipeline.yaml` ở mức **80** hoặc thấp hơn (40–60 nếu phòng nhỏ) để tránh tràn VRAM (OOM).
   - Nếu bạn có Colab Pro (A100 40GB/80GB hoặc L4 24GB), hệ thống có thể xử lý hơn 150–200 keyframes một lượt.

2. **Thời gian sống của session Colab:**
   - Colab Free sẽ tự động ngắt kết nối nếu tab trình duyệt bị đóng hoặc không tương tác trong 60–90 phút (idle timeout).
   - Hãy giữ tab Colab luôn mở trong khi đang chạy pipeline xử lý phòng.

3. **Mỗi lần khởi động lại Colab:**
   - Mỗi lần chạy lại Colab, Cloudflare Tunnel sẽ sinh ra một URL mới (`https://xxx.trycloudflare.com`).
   - Bạn chỉ cần cập nhật `COLAB_URL` trong `backend/.env` và chạy `uv run tasks.py up` để worker nhận URL mới.
