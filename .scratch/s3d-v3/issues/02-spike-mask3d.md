# 02: Spike Mask3D

**What to build:** Trả lời câu hỏi rủi ro nhất của dự án: Mask3D có chạy được trên máy này với ~3,8 GB VRAM trống không. Build image `mask3d` (CUDA 11.3.1 ghim digest, PyTorch 1.12, MinkowskiEngine biên dịch với `FORCE_CUDA=1`), chạy checkpoint ScanNet200 trên hai scan có sẵn, đo VRAM, rồi chốt nhánh S3 bằng một ADR. Timebox 2 ngày công. Xem `docs/implement_plan.md` mục 4 (S3), mục 10 (mask3d.Dockerfile), mục 11 (việc kiểm chứng 1, 5) và ADR 0002.

**Blocked by:** None (can start immediately)

**Status:** complete

- [x] Image build từ đầu trong Docker Desktop; trong container đang chạy, chẩn đoán của MinkowskiEngine báo có CUDA.
- [x] Mask3D fp16 chạy được trên scene0000_00 và scene0000_01, đọc thẳng mesh raw (chưa cần Package); ghi VRAM đỉnh (PyTorch và `nvidia-smi`), thời gian và số Instance ở mỗi mức voxel đã thử.
- [x] Ghi VRAM trống ban đầu khi Windows đang chạy.
- [x] Kiểm bằng mắt: các đồ nội thất lớn đều có Instance.
- [x] Image đạt được lưu dự phòng bằng `docker save`.
- [x] Có ADR mới kèm số đo, chốt một trong hai: Mask3D (đạt cả ba điều kiện: có CUDA, VRAM đỉnh ≤ 3,5 GB với voxel ≤ 3 cm, mask hợp lý) hoặc nhánh 2D-only (chưa đạt sau 2 ngày công).

**Verification:** See [implementation evidence](../../../docs/verification.md) and [review](../../../docs/code-review.md).
