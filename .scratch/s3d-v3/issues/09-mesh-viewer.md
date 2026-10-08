# 09: S6 mesh.bin và viewer 3D

**What to build:** Người dùng mở một Scene đã xử lý và xoay quanh mesh có màu ngay trong trình duyệt. S6 xuất `mesh.bin` (header nhỏ, vị trí Float32, màu Uint8, chỉ số tam giác Uint32, id vật Int32 theo đỉnh, giữ đúng thứ tự đỉnh); viewer React Three Fiber nạp thẳng vào `BufferGeometry`. Lúc này chưa có Instance nên id vật đều là -1. Xem `docs/implement_plan.md` mục 8 (Viewer 3D).

**Blocked by:** 08

**Status:** ready-for-agent

- [ ] S6 ghi `mesh.bin`; `GET /v1/scenes/{id}/mesh` trả về file này.
- [ ] `/scene?id=scene0000_00` hiện mesh có màu, xoay và zoom được; viewer chỉ nạp ở phía client.
- [ ] Thứ tự đỉnh trong `mesh.bin` trùng với mesh trong Package (có test).
- [ ] Hàm giải mã `mesh.bin` phía web có test vitest; định dạng được ghi trong tài liệu.
- [ ] Trang chủ có link mở các Scene đã sẵn sàng.
