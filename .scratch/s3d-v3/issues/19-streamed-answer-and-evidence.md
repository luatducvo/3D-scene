# 19: Câu trả lời stream, Evidence và nhật ký câu hỏi

**What to build:** Câu trả lời hiện dần bằng câu chữ tự nhiên, kèm Evidence: Keyframe tốt nhất của Target và số liệu từ Solver. LLM chỉ diễn đạt lại kết quả Solver; mọi ID và con số được kiểm trước khi gửi đi. Mọi câu hỏi được ghi vào bảng `queries` để xem lại và gỡ lỗi. Xem `docs/implement_plan.md` mục 6 (bước 8), 7, 9.

**Blocked by:** 18

**Status:** ready-for-agent

- [ ] SSE phát `token` trong lúc LLM diễn đạt câu trả lời; `final` có answer, targets, related, program, evidence và latency_ms theo mẫu ở mục 7.
- [ ] Câu trả lời chứa ID hoặc con số không có trong kết quả Solver bị chặn và thay bằng câu trả lời mẫu (có test).
- [ ] `GET /v1/scenes/{id}/frames/{fid}.jpg` trả Keyframe; khung hội thoại hiện Keyframe Evidence; viewer tô Target và vật liên quan, vẽ bbox và đưa camera tới Target.
- [ ] Bảng `queries` lưu text, program, viewpoint, result, n_solutions, used_tiebreak, json_retry và latency_ms.
- [ ] Câu Lookup cũng có câu trả lời bằng chữ và được ghi nhật ký.
