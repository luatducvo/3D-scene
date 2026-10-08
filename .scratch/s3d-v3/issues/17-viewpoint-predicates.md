# 17: Viewpoint và các Predicate tính lúc truy vấn

**What to build:** Solver hiểu các Predicate phụ thuộc góc nhìn và các phép cực trị: "the chair to the left of the bed" được hiểu đúng như người dùng đang thấy trên viewer. Web gửi pose camera hiện tại kèm mỗi câu hỏi làm Viewpoint; không có camera thì người nhìn đứng ở tâm Room nhìn về Anchor; Program nêu rõ góc nhìn thì ghi đè cả hai. Xem `docs/implement_plan.md` mục 5 và ADR 0005.

**Blocked by:** 16

**Status:** complete

- [x] `LEFT`, `RIGHT`, `FRONT`, `BEHIND`, `BETWEEN` được tính lúc truy vấn trong hệ toạ độ của Viewpoint.
- [x] `CLOSEST`, `FARTHEST`, `LARGEST`, `SMALLEST`, `HIGHEST`, `LOWEST` chạy trên tập Candidate; `COLOR` dùng màu chủ đạo của Object.
- [x] `/ask` nhận Viewpoint tuỳ chọn; ChatPanel gửi pose camera của viewer; bảng `queries` lưu Viewpoint đã dùng.
- [x] Cùng một Program cho đáp án `LEFT`/`RIGHT` ngược nhau khi camera xoay 180° (có test).
- [x] Viewpoint suy biến (camera nằm trong bbox của Anchor) lùi về tâm Room, có test.

**Verification:** See [implementation evidence](../../../docs/verification.md) and [review](../../../docs/code-review.md).
