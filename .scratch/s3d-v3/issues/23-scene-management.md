# 23: Quản lý Scene

**What to build:** Người dùng quản lý Scene ngay trên web: chạy lại từ một stage (ví dụ sau khi đổi config của S4a), xoá Scene, và xác nhận Replace khi import một Package khác cho scan đã có. Xem `docs/implement_plan.md` mục 7 và thuật ngữ Replace trong `CONTEXT.md`.

**Blocked by:** 10

**Status:** ready-for-agent

- [ ] `POST /v1/scenes/{id}/reprocess` nhận stage bắt đầu; artifact của các stage trước được giữ nhờ config hash, các stage sau chạy lại.
- [ ] `DELETE /v1/scenes/{id}` xoá Scene, dữ liệu trong SQLite và artifact; có lựa chọn xoá cả Package gốc.
- [ ] Import một Package khác cho scan đã có Scene thì web hỏi xác nhận Replace trước khi gửi.
- [ ] Scene đang có job chạy thì không xoá hay reprocess được cho tới khi job xong hoặc bị huỷ; web báo rõ lý do.
