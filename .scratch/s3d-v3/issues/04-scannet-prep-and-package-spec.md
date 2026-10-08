# 04: scannet_prep và đặc tả s3dpkg/1

**What to build:** Người dùng chạy một script độc lập trên raw ScanNet và nhận một Package hợp lệ để import. Gồm đặc tả `s3dpkg/1`, hợp đồng duy nhất giữa script và hệ thống, và script `pack` / `verify` / `batch` chạy bằng `uv run` (khai báo phụ thuộc kiểu PEP 723), chỉ dùng CPU, không import gì từ hệ thống. Xem `docs/implement_plan.md` mục 3.

**Blocked by:** None (can start immediately)

**Status:** complete

**Input revision 2026-10-09:** The v1, inbox and in-app alignment requirements below are historical; [ticket 25](25-external-preprocessing-upload-only.md) and ADR 0009 supersede them.

- [x] Đặc tả `s3dpkg/1` được viết thành tài liệu: cấu trúc file, manifest (format_version, status, phiên bản script, tham số, sha256 từng file, sha256 của `.sens`, aligned) và kiểu dữ liệu từng file.
- [x] `pack` tạo Package cho scene0000_00 và scene0000_01: giải mã `.sens` dạng stream, giữ 1/10 khung, bỏ pose không hữu hạn, ghi điểm mờ, ảnh màu cạnh dài 960 px, depth uint16, intrinsics đã hiệu chỉnh, mesh giữ thứ tự đỉnh, superpoint lấy từ `segs.json`; không chứa nhãn GT.
- [x] Package được ghi ra file `.partial`, tự `verify` rồi mới đổi tên; ngắt giữa chừng không để lại file mang đuôi `.s3dpkg`.
- [x] `verify` trả mã thoát khác 0 kèm tên bước lỗi khi một byte trong Package bị sửa hoặc thiếu file.
- [x] Scan thiếu `axisAlignment` (bản sao scene0000_00 đã xoá dòng đó) cho Package dùng ma trận đơn vị và `aligned: false`.
- [x] `batch` ghi `prep_report.csv` và bỏ qua scan đã có Package hợp lệ khi chạy lại.
- [x] Có test tự động cho phần không cần raw (ví dụ `verify` trên một Package tổng hợp nhỏ).

**Verification:** See [implementation evidence](../../../docs/verification.md) and [review](../../../docs/code-review.md).
