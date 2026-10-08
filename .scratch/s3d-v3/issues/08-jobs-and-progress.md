# 08: Job, S1 Load và tiến độ

**What to build:** Sau khi import, Scene được xếp job và người dùng thấy tiến độ từng stage trên trang chủ cập nhật trực tiếp. Ticket này dựng job runner (một thread điều phối, các stage chạy tuần tự, artifact cache theo config hash) với S1 Load là stage thật đầu tiên. Xem `docs/implement_plan.md` mục 4, 9.

**Blocked by:** 07

**Status:** ready-for-agent

- [ ] Import thành công tạo job; worker lấy job từ bảng `jobs`, chạy các stage tuần tự và cập nhật trạng thái job và Scene trong SQLite (WAL).
- [ ] S1 giải nén Package, áp `T_align` cho đỉnh và pose, ghi artifact vào thư mục theo stage và config hash; chạy lại với cùng config thì bỏ qua.
- [ ] `GET /v1/scenes/{id}/events` (SSE) phát tiến độ; trang chủ hiện bằng `EventSource`.
- [ ] `stage_runs` ghi trạng thái và thời gian từng stage; một stage lỗi làm job lỗi, kèm thông báo hiện trên web.
- [ ] Khởi động lại `api` giữa chừng không làm job treo mãi: job đang chạy được đánh dấu lỗi hoặc chạy lại.
- [ ] Job runner có test với stage giả.
