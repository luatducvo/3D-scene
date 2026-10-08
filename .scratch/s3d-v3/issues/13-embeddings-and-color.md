# 13: S4b embedding và màu chủ đạo

**What to build:** Mỗi Object có một vector MobileCLIP2 và một màu chủ đạo có tên, để Lookup tìm được theo ý nghĩa ("something to sit on") và Predicate `COLOR` trả lời chắc chắn về màu. Panel Object hiện màu. Xem `docs/implement_plan.md` mục 4 (S4b).

**Blocked by:** 12

**Status:** complete

- [x] Lấy 3–5 crop có nhiều điểm nhìn thấy nhất, encode bằng MobileCLIP2-B, bỏ crop có z-score độ giống dưới −3 (ROFA), lấy trung bình chuẩn hoá; vector lưu dạng BLOB cùng node.
- [x] Màu chủ đạo tính từ histogram HSV trên màu đỉnh mesh, lưu thành tên màu tiếng Anh (red, green, white…) kèm RGB.
- [x] Panel Object hiện tên màu và một ô màu mẫu.
- [x] ROFA và bước đặt tên màu có test.
- [x] Stage chạy dưới khoá GPU trong tiến trình con; VRAM đỉnh ghi vào `stage_runs`.

**Verification:** See [implementation evidence](../../../docs/verification.md) and [review](../../../docs/code-review.md).
