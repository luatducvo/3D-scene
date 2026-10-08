# 08: Job, S1 Load và tiến độ

**What to build:** Sau khi import, Scene được xếp job và người dùng thấy tiến độ từng stage trên trang chủ cập nhật trực tiếp. Ticket này dựng job runner (một thread điều phối, các stage chạy tuần tự, artifact cache theo config hash) với S1 Load là stage thật đầu tiên. Xem `docs/implement_plan.md` mục 4, 9.

**Blocked by:** 07

**Status:** complete

**Input revision 2026-10-09:** The v1, inbox and in-app alignment requirements below are historical; [ticket 25](25-external-preprocessing-upload-only.md) and ADR 0009 supersede them.

- [x] Import thành công tạo job; worker lấy job từ bảng `jobs`, chạy các stage tuần tự và cập nhật trạng thái job và Scene trong SQLite (WAL).
- [x] S1 giải nén Package, áp `T_align` cho đỉnh và pose, ghi artifact vào thư mục theo stage và config hash; chạy lại với cùng config thì bỏ qua.
- [x] `GET /v1/scenes/{id}/events` (SSE) phát tiến độ; trang chủ hiện bằng `EventSource`.
- [x] `stage_runs` ghi trạng thái và thời gian từng stage; một stage lỗi làm job lỗi, kèm thông báo hiện trên web.
- [x] Khởi động lại `api` giữa chừng không làm job treo mãi: job đang chạy được đánh dấu lỗi hoặc chạy lại.
- [x] Job runner có test với stage giả.

**Verification:** See [implementation evidence](../../../docs/verification.md) and [review](../../../docs/code-review.md).
