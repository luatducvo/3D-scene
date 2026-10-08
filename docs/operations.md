# Vận hành S3D

Hướng dẫn khởi động và sử dụng nằm trong [README](../README.md).
Các lệnh dưới đây chạy từ thư mục gốc repository bằng PowerShell.

## Chuẩn hoá nhiều Scan

Tạo `scenes.txt` với một mã Scan mỗi dòng, rồi chạy:

```powershell
uv run tools/scannet_prep.py batch dataset/scans --list scenes.txt --out dataset/preprocessing --workers 2
```

Batch bỏ qua Package đã hợp lệ và ghi `prep_report.csv` trong thư mục kết quả.
Script ghi file `.partial`, verify rồi đổi tên thành `.s3dpkg` khi thành công.
Chi tiết định dạng nằm trong [Package contract](s3dpkg-spec.md).

## Cấu hình LLM

Mặc định S3D dùng llama.cpp với model local được cấu hình trong
`docker/llm-models.ini`. Để dùng endpoint tương thích OpenAI, đặt biến môi trường
rồi tạo lại API:

```powershell
$env:S3D_LLM_BASE_URL = 'https://your-endpoint.example/v1'
$env:S3D_LLM_MANAGED = '0'
$env:S3D_LLM_MODEL = 'your-model-name'
$env:S3D_LLM_API_KEY = 'your-key'
docker compose up -d api
```

Chế độ này gửi câu hỏi, nhãn/ngữ cảnh và ảnh Keyframe khi cần thị giác tới
endpoint. Package và mesh đầy đủ vẫn lưu local. Kết quả Solver được diễn đạt
local; ID đồ vật, số lượng, hình học và quan hệ không được gửi để viết lại.
API không gọi các endpoint quản lý model local trong chế độ này.

Caption mặc định tạo khi cần và được cache. Có thể đặt `S3D_CAPTIONS_TOP_N=N`
trước khi tạo lại API để mô tả trước N đồ vật lớn nhất khi xử lý Scene
(mặc định 0, tối đa 20).

## Sao lưu và khôi phục

Sao lưu SQLite, Package và artifact cùng nhau khi API đã dừng.
Các lệnh dưới đây dùng tên volume của dự án Compose mặc định `3d-scene`;
kiểm tra `docker volume ls` và thay tên nếu checkout của bạn dùng tên khác.

### Sao lưu dữ liệu Scene

```powershell
$backupDir = Join-Path (Resolve-Path .).Path '.backups'
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
docker compose stop api
docker run --rm --mount 'type=volume,src=3d-scene_s3d-data,dst=/data,readonly' --mount "type=bind,src=$backupDir,dst=/backup" alpine:3.22 tar -C /data -czf /backup/s3d-final-backup.tar.gz .
docker compose up -d api
```

Archive này chứa volume dữ liệu ứng dụng. Sao lưu riêng raw Scan,
`dataset/preprocessing/` và model nếu cần chuyển toàn bộ môi trường sang máy khác.

### Khôi phục dữ liệu Scene

**Các lệnh này xoá và thay thế volume dữ liệu hiện tại.** Chỉ thực hiện sau khi
đã giữ bản sao cần thiết bên ngoài volume và kiểm tra archive muốn khôi phục.

```powershell
$backupDir = Join-Path (Resolve-Path .).Path '.backups'
docker compose down
docker volume rm 3d-scene_s3d-data
docker volume create 3d-scene_s3d-data
docker run --rm --mount 'type=volume,src=3d-scene_s3d-data,dst=/data' --mount "type=bind,src=$backupDir,dst=/backup,readonly" alpine:3.22 tar -C /data -xzf /backup/s3d-final-backup.tar.gz
docker compose up -d
```

### Giữ image Mask3D đã biên dịch

Image này mất nhiều thời gian để build. Có thể lưu lại sau khi build thành công:

```powershell
New-Item -ItemType Directory -Force .backups | Out-Null
docker save s3d-mask3d:1 -o .backups/s3d-mask3d.tar
# Khôi phục image:
docker load -i .backups/s3d-mask3d.tar
```

## Model và dữ liệu

Model được cố định nguồn và checksum trong `models.lock`. Lệnh `s3d models pull`
bỏ qua file đúng checksum và báo lỗi nếu file hiện có bị hỏng. Các lần chạy sau
dùng model đã tải mà không cần tải lại.

Các ghi chú giấy phép của dự án:

- Ultralytics YOLOE: AGPL-3.0.
- Apple MobileCLIP2: giấy phép model và code của Apple.
- Mask3D: code MIT; cần kiểm tra riêng điều khoản checkpoint.
- Qwen3-VL: Apache-2.0; llama.cpp: MIT.
- ScanNet: điều khoản nghiên cứu/phi thương mại. Việc chia sẻ raw Scan và Package
  cần phù hợp với quyền sử dụng dữ liệu.

Dữ liệu, Package, model và backup được Git bỏ qua. Kết quả kiểm chứng vận hành
và các giới hạn được ghi theo ngày/revision trong [verification](verification.md).
