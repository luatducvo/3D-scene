# 12: S4a Label

**What to build:** Mỗi Instance trở thành một Object có Label từ vựng mở. Người dùng click một vật thấy Label và độ tin cậy, và lọc được danh sách Object theo Label. Nguồn chính là YOLOE-26-L-seg ở chế độ text-prompt với 200 lớp ScanNet200; chế độ prompt-free là nguồn phụ, trọng số thấp hơn; nhãn được bỏ phiếu đa view trên các Keyframe mà Instance hiện rõ nhất (cách của Open-YOLO 3D). Xem `docs/implement_plan.md` mục 4 (S4a).

**Blocked by:** 11

**Status:** ready-for-agent

- [ ] S4a chạy trong tiến trình con dưới khoá GPU; mỗi Object có Label, độ tin cậy, phân bố nhãn, tối đa 3 alt label và danh sách Keyframe tốt nhất.
- [ ] `GET /v1/scenes/{id}/objects` và `GET /v1/scenes/{id}/objects/{oid}/mask` trả dữ liệu từ SQLite.
- [ ] Click lên mesh hiện Label và độ tin cậy; danh sách Object lọc được theo Label; click một mục trong danh sách thì tô sáng vật đó.
- [ ] Bước bỏ phiếu đa view có test trên dữ liệu tổng hợp, gồm cả trọng số của nguồn phụ.
- [ ] Trên scene0000_00, các vật lớn rõ ràng (giường, bàn, ghế, tủ…) có Label đúng khi kiểm bằng mắt.
