# S3D – Hỏi đáp từ vựng mở trên scene 3D

Hệ thống chạy local cho một người dùng: nạp scene 3D trong nhà đã quét sẵn, rồi tìm, tô sáng và hỏi đáp về đồ vật trong scene bằng ngôn ngữ tự nhiên.

## Language

### Dữ liệu vào

**Scan**:
Một lần quét RGB-D của ScanNet, định danh bằng mã dạng `scene0011_00`; cùng một phòng có thể có nhiều scan (`_00`, `_01`).
_Avoid_: recording, capture

**Preprocessing**:
Chuẩn hoá Scan và căn chỉnh hệ toạ độ hoàn toàn bên ngoài hệ thống; tạo Package để người dùng upload. Xem [glossary](GLOSSARY.md) và ADR 0009.
_Avoid_: Import, xử lý Scene

**Package**:
File `.s3dpkg` đã được căn chỉnh do script độc lập tạo từ một Scan, tuân theo `s3dpkg/2`; là thứ duy nhất hệ thống nhận qua upload.
_Avoid_: gói raw, bundle, archive

**Scene**:
Bản thể của một scan bên trong hệ thống, có định danh trùng mã scan; mỗi scan có nhiều nhất một scene.
_Avoid_: room (phòng là một mức trong scene graph), scan (khi nói về dữ liệu đã nạp)

**Import**:
Việc đưa một package vào hệ thống: kiểm tra theo đặc tả, chép vào kho dữ liệu, tạo hoặc thay thế scene.
_Avoid_: upload (upload là cách gửi Package; Import là việc kiểm tra và tạo Scene)

**Replace**:
Import một package khác cho scan đã có scene, do người dùng chủ động chọn; scene cũ bị xoá và xử lý lại từ đầu.
_Avoid_: overwrite, re-upload

**Keyframe**:
Một ảnh màu + depth + pose được giữ lại trong package (1 trên 10 khung của scan).
_Avoid_: frame, khung

### Scene graph

**Instance**:
Một mask 3D (tập đỉnh của mesh) được đề xuất như một vật riêng, chưa có nhãn.
_Avoid_: proposal, segment

**Object**:
Một instance đã được gán label; là node mức đồ vật trong scene graph.
_Avoid_: vật thể, item, entity

**Structure**:
Sàn hoặc một bức tường của scene; là node mức giữa trong scene graph.
_Avoid_: plane, mặt phẳng

**Room**:
Node gốc của scene graph; mỗi scene có đúng một room.

**Label**:
Tên lớp từ vựng mở của một object, kèm độ tin cậy và tối đa ba alt label thay thế.
_Avoid_: class, category

**Predicate**:
Một điều kiện hình học có tên giữa các node (ví dụ `ON`, `NEAR`, `LEFT`), thuộc thư viện vị từ cố định.
_Avoid_: relation (khi nói về điều kiện)

**Relation**:
Một predicate đã được tính sẵn giữa hai node cụ thể và lưu cùng scene graph.
_Avoid_: edge, link

### Hỏi đáp

**Session**:
Chuỗi câu hỏi nhiều lượt trên một scene, giữ được tham chiếu như "nó", "cái này".
_Avoid_: conversation, chat

**Lookup**:
Câu hỏi chỉ là một cụm danh từ, được trả lời bằng label và embedding mà không cần program.
_Avoid_: search, simple query

**Program**:
Chương trình ràng buộc ngắn dịch từ câu hỏi, gồm các variable, constraint, phép chọn và target.
_Avoid_: query plan

**Target**:
Variable mà câu hỏi muốn tìm.

**Anchor**:
Object được dùng làm mốc trong một constraint, không phải target.
_Avoid_: reference object

**Candidate**:
Một object có thể gán cho một variable.
_Avoid_: match

**Solution**:
Một phép gán object cho mọi variable thoả mọi constraint của program.
_Avoid_: result, answer

**Relaxation**:
Việc bỏ hoặc nới constraint yếu nhất khi program không có solution nào.
_Avoid_: fallback

**Tiebreak**:
Bước model thị giác chọn một trong nhiều solution bằng keyframe có đánh số các candidate.
_Avoid_: arbitration, rerank

**Clarify**:
Việc hỏi lại người dùng khi vẫn còn nhiều solution, kèm điểm khác nhau giữa chúng.

**Viewpoint**:
Gốc và hướng nhìn dùng để hiểu các predicate trái, phải, trước, sau.
_Avoid_: góc nhìn camera

**Evidence**:
Keyframe và số liệu từ solver đính kèm một câu trả lời.
_Avoid_: proof
