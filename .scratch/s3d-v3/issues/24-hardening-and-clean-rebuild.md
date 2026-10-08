# 24: Hoàn thiện và dựng lại từ đầu

**What to build:** Hệ thống dựng lại được từ đầu trên một máy sạch chỉ với Docker, driver và `s3d models pull`, và xử lý lỗi tử tế. Gồm công tắc LLM cloud, xử lý lỗi xuyên suốt, sao lưu volume dữ liệu và tài liệu cài đặt. Xem `docs/implement_plan.md` mục 6 (công tắc LLM cloud), 9 (sao lưu), 10.

**Blocked by:** 05, 22, 23

**Status:** complete

- [x] Từ một bản clone mới: build, models pull, `docker compose up`, import scene0000_00 rồi hỏi đáp nhiều lượt, chỉ làm theo README, không có bước ẩn.
- [x] Đổi `llm.base_url` sang một endpoint tương thích OpenAI thì hỏi đáp vẫn chạy mà không sửa code; chỉ câu hỏi, danh sách Label và (khi Tiebreak) Keyframe được gửi ra ngoài.
- [x] Các lỗi thường gặp (`llm` hoặc `mask3d` không lên, thiếu VRAM, Package hỏng, hết đĩa) hiện thông báo rõ trên web thay vì treo.
- [x] Lệnh sao lưu và khôi phục volume dữ liệu có trong README và đã chạy thử.
- [x] Thời gian nạp scene0000_00 theo từng stage và tổng cộng được đo và ghi vào tài liệu.
- [x] README nêu giấy phép của các thành phần (YOLOE AGPL-3.0, MobileCLIP2, Mask3D, ScanNet Terms of Use).

**Verification:** See [implementation evidence](../../../docs/verification.md) and [review](../../../docs/code-review.md).
