# 16: Solver và schema Program

**What to build:** Hệ thống trả lời được câu tham chiếu, câu đếm và câu tồn tại khi có sẵn một Program, chưa cần LLM. Program là JSON phẳng kiểm bằng Pydantic (intent, vars, constraints, select, target, appearance; enum cho tên Predicate và tên biến). Solver gán Candidate cho từng biến, backtracking tìm mọi Solution, xếp hạng bằng độ tin cậy Label và heuristic khoảng cách trung bình nhỏ nhất của CSVG; không có Solution thì Relaxation. Ở chế độ debug, người dùng dán một Program vào khung hội thoại và thấy Target được tô sáng. Xem `docs/implement_plan.md` mục 6 (bước 6–8).

**Blocked by:** 14, 15

**Status:** ready-for-agent

- [ ] Schema Program là nguồn duy nhất cho cả bước validate bằng Pydantic lẫn JSON schema sẽ gửi cho LLM; schema giữ phẳng.
- [ ] Candidate của mỗi biến lấy từ Label, alt label và độ giống MobileCLIP; Solver trả mọi Solution thoả các Predicate tính sẵn cùng `COUNT`, `EXISTS`, `NOT`.
- [ ] 0 Solution thì Relaxation bỏ constraint yếu nhất và báo đã nới cái nào; 1 Solution thì trả lời; nhiều Solution thì trả danh sách đã xếp hạng.
- [ ] `/ask` nhận Program viết tay ở chế độ debug (bật bằng config) và phát các sự kiện `program`, `candidates`, `final`.
- [ ] Mọi ID trả về đều có trong Scene và mọi con số đều đến từ Solver (kiểm trong code, có test).
- [ ] Khoảng 10 Program viết tay cho scene0000_00 trả đúng Object mong đợi; chạy như test local-only.
