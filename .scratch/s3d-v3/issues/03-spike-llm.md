# 03: Spike llm

**What to build:** Xác nhận Qwen3-VL-4B vừa ngân sách ~3,8 GB với hai preset `text` và `vision`, và router mode của `llama-server` gỡ model thật sự trả lại VRAM. Kết quả quyết định thiết kế của ADR 0004 có giữ được không. Xem `docs/implement_plan.md` mục 10 (llama.cpp, ngân sách VRAM, giao thức khoá GPU), mục 11 (việc kiểm chứng 2, 3, 4).

**Blocked by:** None (can start immediately)

**Status:** complete

- [x] Service `llm` trong Compose dùng image llama.cpp `server-cuda` (CUDA 12) ghim build và digest, router mode với `--models-max 1` và `--no-models-autoload`; không mở cổng ra ngoài mạng Compose (khi dev chỉ mở trên `127.0.0.1`).
- [x] File preset có `text` (không mmproj) và `vision` (mmproj Q8_0), ngữ cảnh 4k, KV cache q8_0.
- [x] Đo VRAM thực của từng preset khi Windows đang chạy; preset `vision` đo với 2 ảnh ≤ 768 px.
- [x] Gỡ model qua `/models/unload`: `GET /models` báo đã gỡ và NVML xác nhận VRAM về mức ban đầu.
- [x] Bộ 30 câu hỏi mẫu tiếng Anh (một phần kèm ảnh) chạy qua `response_format` với JSON schema phẳng; ghi tỉ lệ JSON hợp lệ; bộ câu được lưu để chạy lại mỗi khi nâng build.
- [x] Nếu preset `vision` OOM: thử Qwen3-VL-2B cho vai trò vision và ghi ADR thay thế ADR 0004.

**Verification:** See [implementation evidence](../../../docs/verification.md) and [review](../../../docs/code-review.md).
