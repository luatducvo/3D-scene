# 10: Khoá GPU và S2 Geometry

**What to build:** Pipeline có hạ tầng để chạy stage nặng an toàn trong ~3,8 GB VRAM: mỗi stage GPU hoặc CPU nặng chạy trong một tiến trình con và thoát khi xong; khoá GPU chỉ cho chạy khi NVML báo đủ VRAM trống, nếu không thì báo người dùng đóng bớt app; VRAM đỉnh được ghi lại. S2 Geometry là stage đầu tiên dùng hạ tầng này: điểm, superpoint, sàn và tường bằng RANSAC, visibility cache trên GPU. Người dùng thấy các Structure (sàn, tường) trên viewer. Xem `docs/implement_plan.md` mục 4 (S2), mục 10 (giao thức khoá GPU) và ADR 0002, 0003.

**Blocked by:** 09

**Status:** ready-for-agent

- [ ] torch bản CUDA cài được native trên Windows và trong image Linux từ cùng `uv.lock`.
- [ ] Mỗi stage chạy trong tiến trình con riêng; sau khi một stage GPU kết thúc, VRAM trở về mức trước khi chạy (đo bằng NVML).
- [ ] Khoá GPU: mỗi lúc chỉ một việc dùng GPU; chờ NVML đạt ngưỡng của stage; hết thời gian chờ thì job dừng, web hiện thông báo gợi ý đóng bớt app.
- [ ] VRAM đỉnh và thời gian từng stage được ghi vào `stage_runs`.
- [ ] S2 tạo điểm đúng thứ tự đỉnh, superpoint, mặt sàn và các mặt tường (RANSAC theo trục Z đã căn), và visibility (điểm nhìn thấy trên mỗi Keyframe, lệch depth < 0,1 m) tính theo lô trên GPU.
- [ ] Viewer bật/tắt được việc tô màu Structure.
- [ ] Scan có `aligned: false` đi qua S2 không lỗi.
- [ ] RANSAC và phép chiếu visibility có test trên scene tổng hợp.
