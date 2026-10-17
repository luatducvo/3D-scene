# Đánh giá SOLID và dọn mã legacy — 17/10/2026

Bản tiếng Việt của [solid-review.md](solid-review.md). Các tên miền nghiệp vụ và định danh trong
code được giữ nguyên để thuận tiện đối chiếu.

Phạm vi rà soát gồm các package và service của backend, entry point của Algorithm/Relation, cấu
hình, test và mã triển khai; đồng thời kiểm tra các nơi gọi từ frontend, bản dịch, tài nguyên và
kiểu dữ liệu để tìm mã lỗi thời. Đây là đánh giá mã nguồn tại thời điểm rà soát, không phải khẳng
định rằng linter có thể kiểm chứng đầy đủ SOLID. Các comment có nhãn `SOLID review` trong code
đánh dấu toàn bộ điểm cần cải thiện được liệt kê bên dưới.

## Đánh giá tổng thể

Backend đã áp dụng đáng kể các nguyên tắc SOLID. Một số interface được khai báo rõ ràng, một số
được xác lập qua cấu trúc và cách sử dụng. Tuy nhiên, cả năm nguyên tắc chưa được tuân thủ nhất quán.

| Nguyên tắc | Bằng chứng trong code | Hạn chế còn lại |
|---|---|---|
| Trách nhiệm đơn nhất (SRP) | Algorithm biến đổi Workspace; SceneResults kiểm tra tính hợp lệ của các tệp publication; SceneStore quản lý việc ghi trạng thái và sự kiện trong transaction. | Các hàm tạo ứng dụng API và compute còn chứa cả hành vi ứng dụng và logic điều phối. |
| Đóng/mở (OCP) | Algorithm và các quy tắc Relation được đăng ký qua entry point của package, chỉ nạp khi cần và được chọn bằng cấu hình. | Vòng lặp xây dựng Scene Graph vẫn nhận diện riêng `against_wall` theo tên. |
| Thay thế Liskov (LSP) | Algorithm thật và giả cùng dùng StageAlgorithm và các Manifest; bộ test hợp đồng của Target kiểm tra cả adapter chạy trong tiến trình lẫn adapter HTTP. | Quy tắc Relation với căn phòng bỏ qua Object thứ hai và cần cách điều phối riêng. Test hợp đồng cung cấp bằng chứng về khả năng thay thế, nhưng không chứng minh mọi triển khai GPU đều tuân thủ. |
| Phân tách interface (ISP) | RelationRule chỉ có một thao tác. Các hook khởi tạo và tải weights của Algorithm có triển khai mặc định không làm gì, nên Algorithm chạy CPU không cần ghi đè. | Việc embedding câu truy vấn phụ thuộc vào một khả năng nằm ngoài StageAlgorithm; nên có một interface riêng, chỉ mô tả khả năng đó. |
| Đảo ngược phụ thuộc (DIP) | Core không import FastAPI, driver database hay Torch. Executor tra cứu Algorithm đã đăng ký; QAAgent nhận LLM thật hoặc theo kịch bản và không tự quản lý HTTP client. | Interface của Target adapter còn ngầm định; Worker tự khởi tạo SceneStore bên trong. |

## Các nhận xét đã thêm trực tiếp vào code

| Vị trí | Nhận xét và hướng cải thiện |
|---|---|
| `scene_api/main.py:create_app` | SRP: khi các trách nhiệm này tiếp tục phát triển, tách các ca sử dụng upload/search/QA khỏi phần lắp ghép HTTP và truy vấn SQL đọc dữ liệu. Giữ việc ghi dữ liệu có transaction trong SceneStore. |
| `scene_compute/server.py:create_app` | SRP: việc lập lịch/lưu bản ghi Compute Run và truyền tệp Workspace có thể thay đổi độc lập. Tách hành vi của chúng thành các module phía sau hợp đồng compute hiện có. |
| `scene_stages/graph.py:GeometricGraph.run` | OCP/LSP: khai báo phạm vi đánh giá giữa các Object hoặc giữa Object với căn phòng ngay trên RelationRule, để thêm Relation với căn phòng mà không cần xử lý riêng hay truyền Object thứ hai giả. |
| `scene_core/executor.py:Executor.invoke` | ISP/DIP: mô tả khả năng embedding văn bản tùy chọn bằng interface riêng; tránh bắt mọi Stage phải cung cấp khả năng này. Danh sách cho phép của invoke vẫn là giới hạn có chủ đích. |
| `scene_target/__init__.py:TargetWorkspace.__init__` | DIP, cải thiện khả năng bảo trì: khai báo Protocol có kiểu dữ liệu cho hai adapter hiện có. Duck typing hiện tại đã cho phép thay thế adapter khi chạy. |
| `scene_worker/runner.py:Worker.__init__` | DIP, cải thiện khi phát sinh nhu cầu: việc khởi tạo phần lưu trữ còn gắn với điều phối. Truyền SceneStore từ main nếu cần thêm adapter lưu trữ khác; hiện chưa cần tạo hệ phân cấp repository cho nhu cầu giả định. |

Đây là các nhận xét rà soát, chưa phải những đợt refactor đã hoàn thành. Các hook vòng đời,
Algorithm giả, ScriptedLLM, provider đã cấu hình và `attributes.vlm_api` đã đăng ký vẫn là những
điểm thay thế đang được hỗ trợ.

## Mã đã loại bỏ

- Phiên bản publication tổng hợp `legacy` của API và nhánh phục vụ tệp publication lưu trực tiếp
  dưới thư mục Scene ([ADR-0007](../adr/0007-retire-unversioned-results.md)); Scene chưa có
  publication không trả về URL tài nguyên.
- Alias `Registry.get`, hàm bọc `dominant_yaw`, các model ErrorDetail/ErrorResponse, thuộc tính
  Worker.data_dir và import SceneError không được sử dụng.
- Alias backend `cpu`; `cpu` vẫn là tên Target hợp lệ khi dùng `backend: inprocess`.
- Định dạng bọc cũ `{instances: [...]}` trong phần đọc dữ liệu của Scene Graph; cả hai Algorithm
  lift hiện tại đều ghi danh sách JSON, đúng với định dạng mà phần đọc embedding và attributes
  đã yêu cầu.
- Logic dò đường dẫn cấu hình tải model bị trùng lặp. Hiện sử dụng MODELS_PIPELINE_CONFIG hoặc
  bộ tìm đường dẫn chung dựa trên CONFIG_DIR/cấu trúc mã nguồn; đường dẫn ghi đè tường minh bị
  sai sẽ báo lỗi rõ ràng.
- Bảy khóa dịch không được sử dụng trong cả hai ngôn ngữ: title, create, delete, open, noObjects,
  clear, measureHint. Các chuỗi giao diện hiện tại, dữ liệu ảnh bằng chứng và Algorithm được hỗ
  trợ vẫn được giữ lại.
- Import bằng ký tự đại diện và các lỗi lint tồn đọng. Các cell Colab hiện dùng chung cấu hình
  bộ nhớ đệm model, thống nhất cổng 9000 và không in compute token; kết quả thực thi đã lưu trong
  notebook được xóa.

Các tệp migration lịch sử được giữ nguyên theo quy định của repository. Chúng cần thiết để tạo
schema hiện tại từ đầu; những mô tả lịch sử về hành vi đã loại bỏ không phải là mã thực thi.

## Kết quả kiểm tra

- `uv run tasks.py lint`: đạt, xử lý toàn bộ 60 lỗi được ghi nhận trước thay đổi.
- `uv run tasks.py test`: 86 test đạt, chạy với Postgres dành cho kiểm thử, Algorithm giả và
  ScriptedLLM. Còn một cảnh báo ngừng hỗ trợ từ thư viện phụ thuộc trong TestClient của
  FastAPI/Starlette.
- `uv run tasks.py openapi`, sau đó `npm run api:sync`: đạt; nội dung các hợp đồng sinh tự động
  không thay đổi.
- Frontend `npm run typecheck`, `npm test`, `npm run build`: đạt; 19 test frontend đạt.
  TypeScript cũng đạt khi bật `--noUnusedLocals --noUnusedParameters`.
- Đã kiểm tra các import của scene-core để tìm phụ thuộc framework/GPU/database bị cấm; không
  phát hiện vi phạm. Đã chạy thử việc tìm CONFIG_DIR và báo lỗi khi đường dẫn ghi đè tường minh
  không tồn tại từ thư mục ngoài repository, sử dụng cả chín Algorithm giả mà không tải model
  weights.
- JSON của notebook Colab phân tích được và không chứa kết quả thực thi đã lưu. Chưa thực hiện
  suy luận GPU thực tế, chạy phiên tunnel hay triển khai lên provider; các kiểm tra đó vẫn được
  theo dõi trong GPU-INTEGRATION.md.

## Dọn dữ liệu cục bộ

Đã xóa 238 Scene hiện có cùng các Job, Stage Run, Object, Relation, tin nhắn và sự kiện liên quan
khỏi `scene-test-db` của dự án, giữ lại schema và sổ theo dõi migration. Các bản ghi tổng hợp do
quá trình kiểm tra tạo ra và Workspace tạm tương ứng cũng đã được xóa. Số bản ghi cuối cùng bằng
không trên cả bảy bảng Scene/trạng thái; cả bốn bản ghi migration schema vẫn được giữ lại.

Không có thư mục `data/` hoặc `backend/data/` cục bộ và không có volume Compose của ứng dụng cần
xóa. Model weights và các tệp môi trường không bị thay đổi. Chưa truy cập Target Colab đã cấu
hình; dữ liệu từ xa chưa được xóa và chưa được xác nhận là rỗng. Notebook đã cập nhật sẽ xóa dữ
liệu Scene tạm trong lần khởi động server tiếp theo, như mô tả trong hướng dẫn Colab.
