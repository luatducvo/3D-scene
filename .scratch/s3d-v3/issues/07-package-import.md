# 07: Import Package

**What to build:** Người dùng kéo thả một Package lên trang chủ, hoặc chọn một Package có trong inbox, và thấy Scene mới trong danh sách. S0 kiểm Package theo đặc tả `s3dpkg/1` và từ chối kèm lý do khi sai. Scene có id chính là mã scan; import lại cùng Package thì không làm gì; Package khác cho cùng scan bị từ chối, trừ khi người dùng chọn Replace. Xem `docs/implement_plan.md` mục 3, 7, 9 và các thuật ngữ Import, Replace trong `CONTEXT.md`.

**Blocked by:** 01, 04

**Status:** complete

**Input revision 2026-10-09:** The v1, inbox and in-app alignment requirements below are historical; [ticket 25](25-external-preprocessing-upload-only.md) and ADR 0009 supersede them.

- [x] `POST /v1/imports` nhận file upload hoặc tên file trong inbox; Package nhiều GB upload được mà không nạp cả file vào RAM.
- [x] S0 từ chối khi sai đuôi, `format_version` không được hỗ trợ, `status` khác `complete`, thiếu file hoặc sha256 lệch; lỗi nói rõ điều kiện nào sai và hiện trên web.
- [x] Import thành công: Package được chép vào kho dữ liệu, Scene được tạo với id = mã scan, hiện trong `GET /v1/scenes` và `GET /v1/scenes/{id}`.
- [x] Package trùng sha256 với Scene đang có thì không tạo gì mới; Package khác cho cùng scan thì bị từ chối, hoặc Replace nếu người dùng chọn (Scene cũ và artifact bị xoá).
- [x] Trang chủ liệt kê các Package có trong inbox để chọn.
- [x] Contract test S0 chạy trên Package tổng hợp sinh ngay trong test (một bản hợp lệ và từng kiểu lỗi); có test cho no-op, từ chối và Replace.
- [x] Import được Package thật của scene0000_00 và scene0000_01.

**Verification:** See [implementation evidence](../../../docs/verification.md) and [review](../../../docs/code-review.md).
