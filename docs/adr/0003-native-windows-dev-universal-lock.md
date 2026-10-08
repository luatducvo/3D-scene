# Dev native trên Windows với uv.lock đa nền tảng; Docker cho mask3d, llm và bản chạy thật

Kiến trúc v3 yêu cầu đặt repo trong filesystem WSL2 và khoá `uv.lock` chỉ cho wheel Linux, nhưng máy dev không có distro WSL nào ngoài `docker-desktop`, và kiến trúc cũng muốn chạy `api` ngoài Docker khi dev. Ta giữ repo trên ổ D:, để `uv.lock` resolve cho cả Windows lẫn Linux (torch từ index PyTorch CUDA có wheel cho cả hai), dev và chạy test native trên Windows kể cả stage GPU; `mask3d` và `llm` luôn chạy trong Docker (compose override mở cổng `127.0.0.1` khi dev), bản chạy thật là `docker compose up`.

## Consequences

- Dữ liệu chạy thật vẫn ở named volume (SQLite WAL không an toàn trên bind mount); khi dev native, thư mục dữ liệu nằm trên ổ local của Windows.
- Đường dẫn trong code phải dùng `pathlib`, không giả định dấu `/` hay quyền file kiểu POSIX.
