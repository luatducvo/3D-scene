# 20: Session và Clarify

**What to build:** Người dùng hỏi nhiều lượt trên một Scene: "it", "this one" trỏ về Object vừa được nhắc hoặc Object vừa click trên viewer. Khi còn nhiều Solution, hệ thống Clarify: tô mỗi Candidate một màu, nêu điểm khác nhau giữa chúng và hiện nút chọn; lựa chọn được gửi lại cùng `session_id`. Khi đã Relaxation, câu trả lời nói rõ constraint nào đã bị nới. Xem `docs/implement_plan.md` mục 6 (bước 1 và 7), 8 (khung hội thoại).

**Blocked by:** 19

**Status:** complete

- [x] `/ask` nhận `session_id` tuỳ chọn; Session lưu trong SQLite cùng các ID vừa nhắc.
- [x] "it", "that", "this" được thay bằng Object gần nhất trong Session, hoặc Object người dùng vừa click nếu việc click mới hơn.
- [x] Nhiều Solution không phân xử được thì phát `clarify` gồm các Candidate và điểm khác nhau (Label, màu, vị trí, kích thước); web tô mỗi Candidate một màu kèm nút chọn.
- [x] Chọn một Candidate thì gửi lại cùng `session_id` và nhận `final` đúng Object đã chọn.
- [x] Relaxation được nói rõ trong câu trả lời.
- [x] Bước giải tham chiếu và luồng Clarify có test.

**Verification:** See [implementation evidence](../../../docs/verification.md) and [review](../../../docs/code-review.md).
