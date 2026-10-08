# 06: models.lock và s3d models pull

**What to build:** Một lệnh tải mọi model cần thiết vào thư mục model (named volume khi chạy Compose, thư mục local khi dev native) và kiểm sha256, để sau đó hệ thống chạy hoàn toàn offline. Xem `docs/implement_plan.md` mục 2 (model dùng trong hệ thống), 9, 10.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] `models.lock` liệt kê tên file, nguồn và sha256 của YOLOE-26-L-seg, MobileCLIP2-B, Qwen3-VL-4B-Instruct Q4_K_M và mmproj Q8_0; checkpoint Mask3D ScanNet200 được thêm nếu spike Mask3D chọn nhánh Mask3D.
- [ ] `s3d models pull` tải các model còn thiếu, bỏ qua file đã đúng sha256, báo lỗi rõ khi sha256 sai.
- [ ] Chạy được cả native lẫn `docker compose run --rm api s3d models pull`.
- [ ] Sau khi pull, khởi động hệ thống không cần mạng.
