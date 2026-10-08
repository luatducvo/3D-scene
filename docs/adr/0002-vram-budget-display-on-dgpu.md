# Thiết kế cho ~3,8 GB VRAM trống, màn hình vẫn chạy trên RTX 3050

Màn hình và các app Windows (trình duyệt, IDE, Electron…) chạy trên chính RTX 3050 6 GB và chiếm khoảng 2 GB, nên ngân sách thiết kế cho mọi việc GPU là **~3,8 GB trống**, không phải 6 GB như kiến trúc v3 giả định. Ta chọn không chuyển màn hình sang iGPU; thay vào đó cấu hình mặc định nhỏ hơn: ngữ cảnh `llm` 4k token, tối đa 2 ảnh ≤ 768 px khi phân xử, Mask3D voxel hoá sớm hơn, và khoá GPU chỉ cho stage chạy khi NVML báo đủ VRAM trống (báo người dùng đóng bớt app nếu thiếu).

## Consequences

- Số VRAM ở mục 4 và mục 10 của `docs/implement_plan.md` (4–4,5 GB cho `llm`) không còn vừa; cần đo lại ở tuần 1 với Windows đang chạy.
- Nếu sau này bật iGPU cho màn hình, chỉ cần nới các ngưỡng trong config, không đổi kiến trúc.
