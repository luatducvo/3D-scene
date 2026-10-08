# 14: Lookup end-to-end

**What to build:** Người dùng gõ một cụm danh từ tiếng Anh ("chairs", "something to sit on") vào khung hội thoại và các Object khớp được tô sáng trên viewer, không cần LLM. Đây là đường đầu tiên của `/ask`: SSE qua POST, router luật nhận ra Lookup, encoder text MobileCLIP2 chạy trên CPU, số kết quả chọn tại điểm rơi lớn nhất của độ giống (cách của ReLaGS). Xem `docs/implement_plan.md` mục 6 (bước 2), 7, 8 (khung hội thoại) và ADR 0006.

**Blocked by:** 13

**Status:** ready-for-agent

- [ ] `POST /v1/scenes/{id}/ask` trả SSE; một câu Lookup phát sự kiện `candidates` và `final` kèm `targets`.
- [ ] Router luật: cụm danh từ không có từ quan hệ hay từ hỏi thì là Lookup; câu khác nhận câu trả lời "not supported yet" rõ ràng cho tới khi các ticket Solver và LLM xong.
- [ ] Kết hợp Label, alt label và độ giống text MobileCLIP; chọn số kết quả tại điểm rơi lớn nhất.
- [ ] Khi mở Scene, vector của các Object được nạp thành một ma trận NumPy và tìm vét cạn.
- [ ] ChatPanel đọc SSE bằng `fetch` + `ReadableStream` + `eventsource-parser`; sự kiện `final` tô sáng `targets` trên viewer.
- [ ] Router và bước chọn điểm rơi có test; parser SSE phía web có test vitest.
- [ ] Đường Lookup không gọi LLM và không lấy khoá GPU.
