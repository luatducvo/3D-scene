# S3D

S3D nhận dữ liệu của Scan đã được tiền xử lý để tạo Scene và hỗ trợ hỏi đáp
về các đồ vật trong Scene.

## Language

**Scan**:
Một lần quét RGB-D của ScanNet, định danh bằng mã scan; cùng một phòng có thể có nhiều Scan.
_Avoid_: recording, capture

**Preprocessing**:
Việc chuẩn hoá dữ liệu và căn chỉnh hệ toạ độ của một Scan bên ngoài hệ thống để tạo một Package dùng được cho Import.
_Avoid_: Import, xử lý Scene

**Package**:
Dữ liệu của một Scan đã được tiền xử lý và căn chỉnh hệ toạ độ, là đơn vị đầu vào để Import thành một Scene.
_Avoid_: gói raw, bundle, archive

**Scene**:
Bản thể của một Scan bên trong hệ thống; mỗi Scan có nhiều nhất một Scene.
_Avoid_: Scan (khi nói về dữ liệu đã nạp), Room

**Import**:
Việc đưa một Package vào hệ thống để tạo hoặc thay thế Scene.
_Avoid_: Preprocessing, upload (chỉ là cách gửi Package)
