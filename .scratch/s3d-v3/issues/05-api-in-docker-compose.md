# 05: api chạy trong Docker Compose

**What to build:** Bản chạy thật: `docker compose up` dựng image `api` (build web bằng `node:24-alpine`, rồi `python:3.12-slim` + uv) và phục vụ đúng trang skeleton như khi chạy native. Từ đây mọi ticket sau phải giữ Compose chạy được. Xem `docs/implement_plan.md` mục 9, 10 và ADR 0003.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] `docker compose up` rồi mở `http://localhost:8000` thấy trang skeleton; cổng chỉ bind `127.0.0.1`.
- [ ] Image `api` cài từ cùng `uv.lock` (frozen); lớp phụ thuộc chỉ build lại khi lock đổi.
- [ ] Dữ liệu và model nằm trong named volume; inbox là bind mount, cấu hình được bằng biến môi trường.
- [ ] `compose.dev.yaml` mở cổng `llm` và `mask3d` trên `127.0.0.1` để `api` chạy native gọi được.
- [ ] Build context loại dataset, môi trường ảo, `node_modules` và mọi Package.
- [ ] Container `api` thấy GPU: NVML đọc được VRAM trống.
