# 11: S3 Instance theo kết quả spike

**What to build:** Scene có Instance: các vật riêng biệt được tách ra khỏi mesh, người dùng click lên mesh thì Instance đó được tô sáng. Nhánh cài đặt theo ADR do spike Mask3D (ticket 02) ghi: Mask3D trong container `mask3d` gọi qua HTTP nội bộ, hoặc nhánh 2D-only (mask YOLOE-seg trên Keyframe được nâng lên superpoint). Hai nhánh nằm sau cùng một interface đề xuất Instance để có thể đổi về sau. Xem `docs/implement_plan.md` mục 4 (S3), mục 10 (giao tiếp với mask3d).

**Blocked by:** 02, 06, 10

**Status:** ready-for-agent

- [ ] S3 ghi `masks.npz` (chỉ số đỉnh theo Instance) cho scene0000_00 và scene0000_01; lọc trùng bằng NMS; bỏ Instance dưới 100 đỉnh.
- [ ] Nếu là nhánh Mask3D: service `mask3d` có trong Compose, nhận `POST /run` với đường dẫn trong volume dữ liệu, chạy trong tiến trình con và trả hết VRAM khi xong; `api` giữ khoá GPU trong suốt lần gọi.
- [ ] Nếu là nhánh 2D-only: không cần MinkowskiEngine; dùng YOLOE-seg và visibility của S2.
- [ ] Gặp CUDA OOM thì hạ cấu hình (voxel thô hơn hoặc ảnh nhỏ hơn) và ghi lại vào `stage_runs`.
- [ ] `mesh.bin` chứa id Instance theo đỉnh; viewer tô sáng bằng shader (texture trạng thái theo id), click lên mesh hiện id Instance.
- [ ] Interface đề xuất Instance có test với một bộ đề xuất giả.
