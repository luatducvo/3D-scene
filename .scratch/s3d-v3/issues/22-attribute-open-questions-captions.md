# 22: Câu hỏi thuộc tính, câu hỏi mở và caption lười

**What to build:** Người dùng hỏi về thuộc tính ("what color is the table near the door?") và câu hỏi mở ("what is this room used for?"). Với câu thuộc tính, Solver tìm Object rồi model thị giác đọc thuộc tính trên Keyframe tốt nhất. Với câu mở, LLM trả lời dựa trên scene graph đã tuần tự hoá, có thể kèm 1–2 Keyframe. Caption của Object chỉ được sinh khi câu hỏi cần tới và được cache lại. Xem `docs/implement_plan.md` mục 4 (S4c), 6.

**Blocked by:** 21

**Status:** ready-for-agent

- [ ] Intent thuộc tính: Solver tìm Target, preset `vision` đọc thuộc tính trên Keyframe tốt nhất, câu trả lời kèm Evidence.
- [ ] Intent câu mở: scene graph được lọc theo câu hỏi và tuần tự hoá vừa ngữ cảnh 4k, rồi đưa cho LLM trả lời.
- [ ] Caption sinh lười và cache cùng node; hỏi lại lần sau không gọi model nữa.
- [ ] Tuỳ chọn tạo trước caption cho N Object lớn nhất khi xử lý Scene (mặc định tắt).
- [ ] Không đủ VRAM cho preset `vision` thì câu trả lời nói rõ không đọc được ảnh, không treo.
