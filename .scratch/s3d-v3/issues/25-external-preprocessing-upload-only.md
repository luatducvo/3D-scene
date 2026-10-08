# 25: Chuẩn hoá hoàn toàn bên ngoài và chỉ upload Package

**What to build:** Theo ADR 0009, thay luồng input hiện tại bằng
`dataset/scans/<scan> → tools/scannet_prep.py → dataset/preprocessing/<scan>.s3dpkg
→ upload → Import/Scene`. Ticket này thay thế các yêu cầu format v1, inbox và
căn chỉnh tại S1 trong các ticket 04, 07, 08 và tài liệu kế hoạch cũ.

**Status:** in-progress

## Acceptance criteria

- [ ] Prep chạy độc lập, chỉ dùng CPU, không import backend và không cần hệ thống chạy.
- [ ] Prep áp `axisAlignment` cho mesh và camera pose trước khi đóng Package;
      thứ tự đỉnh, faces, RGB và superpoint vẫn tương ứng.
- [ ] Thiếu hoặc sai ma trận căn chỉnh thì báo lỗi bước alignment và không xuất
      Package hoàn chỉnh. Ma trận identity được khai báo hợp lệ vẫn được chấp nhận.
- [ ] Package mới dùng `format_version: s3dpkg/2`; hợp đồng mô tả rõ toạ độ đã căn
      chỉnh và ma trận nguồn để truy nguyên, tránh áp phép biến đổi hai lần.
- [ ] Ví dụ pack/batch lưu kết quả vào `dataset/preprocessing/`; giữ ghi `.partial`,
      verify và rename nguyên tử. Kết quả preprocessing được Git/Docker build bỏ qua.
- [ ] UI chỉ cho chọn/kéo thả file `.s3dpkg`; bỏ danh sách/nút nhập inbox.
- [ ] API Import chỉ nhận upload file và tuỳ chọn Replace; bỏ `/v1/inbox`,
      `inbox_name`, cấu hình và bind mount inbox.
- [ ] API tự verify hợp đồng v2, checksum và cấu trúc; từ chối v1 với hướng dẫn
      chạy lại prep, không nhận raw scan/.sens/thư mục dữ liệu.
- [ ] S1 chỉ giải nén/đọc Package đã căn chỉnh, không biến đổi mesh/pose.
- [ ] Upload stream tạo bản sao trong kho dữ liệu ứng dụng; không sửa hay xoá file
      người dùng trong preprocessing. No-op, Replace, jobs và progress vẫn chạy.
- [ ] Bảo toàn các Scene/artifact đã căn chỉnh đang có; nếu cần nạp lại source v1
      thì báo yêu cầu chuẩn hoá và upload v2.
- [ ] Cập nhật README, CONTEXT/glossary, implementation plan, Package spec và types
      OpenAPI/TypeScript theo luồng mới; giữ số đo lịch sử v1 được ghi rõ phiên bản.
- [ ] Test độc lập chứng minh mesh và pose được căn chỉnh đúng, test S1 chứng minh
      không căn chỉnh lại, test thiếu ma trận/v1 rejection/upload/no-op/Replace.
- [ ] Tạo và verify Package v2 cho hai scan mẫu trong preprocessing; người dùng tự
      upload các file này theo luồng đã chọn.
