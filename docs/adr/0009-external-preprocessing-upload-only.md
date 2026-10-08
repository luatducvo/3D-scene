# Chuẩn hoá Scan bên ngoài hệ thống và chỉ nhập qua upload

Ngày 2026-10-09, chốt luồng `dataset/scans → script độc lập → dataset/preprocessing
→ upload → Scene`: script thực hiện cả căn chỉnh mesh và camera pose; hệ thống
chỉ nhận Package đã căn chỉnh, kiểm tra và giải nén ở S0/S1 rồi phân tích Scene.
Package mới dùng `s3dpkg/2`, vẫn có đuôi `.s3dpkg`; bỏ inbox và từ chối upload v1
với hướng dẫn chạy lại prep. Scan thiếu hoặc có `axisAlignment` không hợp lệ sẽ
dừng ở prep, nhằm tránh nhận dữ liệu chưa căn chỉnh hoặc áp phép căn chỉnh hai lần.

## Hệ quả

- Định dạng phải xác định rõ hệ toạ độ đã được căn chỉnh; ma trận nguồn chỉ là
  thông tin truy nguyên, hệ thống không áp lại ma trận đó.
- Mesh và pose dùng cùng phép biến đổi, giữ nguyên thứ tự đỉnh và liên kết superpoint.
- Script không phụ thuộc backend, Docker hay GPU. Thư mục preprocessing là kho
  kết quả ngoài hệ thống; upload tạo bản sao trong kho dữ liệu của ứng dụng.
- Không chuyển v1 sang v2 bằng đổi tên hoặc chuyển thư mục: phải chạy lại prep.
- Các Scene đã có dữ liệu căn chỉnh được giữ; thay đổi này áp dụng cho input mới.
- Không giữ nhánh căn chỉnh v1 trong ứng dụng hoặc thêm công cụ chuyển đổi v1.

## Triển khai

Các quyết định qua Q1–Q4 và thiết kế tổng hợp đã được người dùng xác nhận;
ticket 25 ghi các tiêu chí triển khai và kiểm chứng.
