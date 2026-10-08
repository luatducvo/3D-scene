# 18: LLM sinh Program

**What to build:** Người dùng gõ câu hỏi tiếng Anh tự nhiên ("the chair next to the window, closest to the desk") và hệ thống tự dịch thành Program rồi giải bằng Solver. Preset `text` của `llm` nhận câu hỏi, danh sách Label có trong Scene và 5–8 ví dụ tiếng Anh, xuất JSON theo `response_format`; `api` luôn validate lại bằng Pydantic, sai thì thử lại một lần, sai tiếp thì xin người dùng nói lại. Mỗi danh từ được chuẩn hoá về Label có trong Scene. Khoá GPU điều phối việc nạp và gỡ preset. Xem `docs/implement_plan.md` mục 6 (bước 3–5), mục 10 (giao thức khoá GPU) và ADR 0004.

**Blocked by:** 03, 10, 17

**Status:** ready-for-agent

- [ ] Câu không phải Lookup thì lấy khoá GPU, nạp preset `text` nếu chưa nạp (gỡ preset khác trước, xác nhận bằng `GET /models` và NVML), rồi gọi chat completions với JSON schema sinh từ schema Program.
- [ ] JSON không hợp lệ, hoặc 200 OK kèm văn bản tự do, thì thử lại một lần; vẫn sai thì phát `clarify` xin người dùng diễn đạt lại; số lần thử ghi vào `json_retry`.
- [ ] Chuẩn hoá danh từ: ánh xạ về Label trong Scene bằng độ giống text MobileCLIP (top-k) và alt label (ví dụ "couch" → sofa).
- [ ] Stage offline cần GPU chờ hoặc gỡ preset `llm` qua cùng một khoá; không bao giờ có hai việc GPU chạy cùng lúc (test với `llm` giả).
- [ ] `llm.base_url` trong config quyết định endpoint; trỏ sang endpoint khác tương thích OpenAI không cần sửa code.
- [ ] SSE phát `program` → `candidates` → `final`, với câu trả lời mẫu dựng từ kết quả Solver.
- [ ] Bộ 30 câu từ spike `llm` chạy lại như test local-only; ghi tỉ lệ Program hợp lệ và tỉ lệ Solution đúng.
