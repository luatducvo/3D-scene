# 15: S5 Scene graph

**What to build:** Scene có scene graph ba mức Room → Structure → Object, với các Relation tính bằng hình học từ bbox và điểm, không nhờ LLM. Người dùng chọn một Object thấy các Relation của nó (on floor, near desk…). Xem `docs/implement_plan.md` mục 5.

**Blocked by:** 12

**Status:** ready-for-agent

- [ ] S5 chạy trong tiến trình con (CPU), tạo đúng một Room, các Structure lấy từ S2 và các Object lấy từ S4a.
- [ ] Các Relation tính sẵn và lưu kèm score: `ON`, `UNDER`, `SUPPORTS`, `IN`, `CONTAINS`, `NEAR`, `FAR`, `NEXT_TO`, `AGAINST_WALL`, `ON_FLOOR`, `IN_CORNER`; ngưỡng theo hướng của CSVG và cấu hình được.
- [ ] `GET /v1/scenes/{id}/graph` trả node và Relation.
- [ ] Panel Object hiện danh sách Relation; click một Relation thì tô sáng vật liên quan.
- [ ] Mỗi Predicate tính sẵn có test trên scene tổng hợp (hộp đặt trên bàn, ghế sát tường, vật nằm trong tủ…).
- [ ] Có hàm tuần tự hoá mỗi node thành một dòng ngắn theo mẫu ở mục 5 (để đưa cho LLM về sau), có test.
