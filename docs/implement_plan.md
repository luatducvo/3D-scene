# Kiến trúc v3 – Hệ thống 3D từ vựng mở chạy local trên RTX 3050 6 GB

Oct 8, 2026 · @BIT

## 1. Tóm tắt

Bản v3 chạy trọn trên một máy có RTX 3050 6 GB và chỉ phục vụ hai việc: người dùng nạp scene và tương tác với scene. Hệ thống không có phần đánh giá hay benchmark. Hệ thống build và chạy bằng Docker Compose (Python trong image do uv quản lý), giao diện web viết bằng Next.js, model ngôn ngữ chạy local bằng llama.cpp. Ba thay đổi chính so với v2:

- **Instance:** đề xuất 3D từ Mask3D đã huấn luyện sẵn, gán nhãn bằng detector 2D YOLOE theo cách của Open-YOLO 3D (24,7 mAP ScanNet200 val, 21,8 giây/scene trên A100). Cách này tốt hơn Any3DIS chỉ 2D (19,1 AP) với chi phí nhỏ hơn nhiều.
- **Grounding và QA:** giải ràng buộc kiểu CSVG trên scene graph tính bằng hình học, thay cho render + VLM kiểu SeeGround. CSVG đạt 59,2% trên Nr3D (khi dùng box và nhãn GT) mà không cần VLM nhìn ảnh.
- **Model và hạ tầng:** một model duy nhất Qwen3-VL-4B-Instruct 4-bit qua llama.cpp cho mọi vai trò ngôn ngữ; MobileCLIP2-B thay CLIP-L; từ 6 container nặng (Celery, Redis, MinIO, PostgreSQL, vLLM) xuống 3 container: api (FastAPI, web Next.js tĩnh, SQLite), mask3d, llm (llama.cpp).

| Thành phần v2 | v3 | Lý do |
| --- | --- | --- |
| Any3DIS (SAM 2-L tracking) | Mask3D pretrained + YOLOE gán nhãn (Open-YOLO 3D) | Any3DIS tốn 488 giây chỉ cho proposal trên một scene ScanNet++; Open-YOLO 3D cao hơn 5,6 AP và nhanh hơn hàng chục lần |
| Open3DIS pointwise CLIP-L | MobileCLIP2-B, một vector mỗi instance | Mất ít độ chính xác (OpenM3D: 4,23 → 4,16 khi L/14 → B/16); encoder ảnh 86,3M thay vì 304M tham số |
| ReLaGS ROFA | Giữ | Chạy trên CPU, vài chục dòng code |
| Sparse3DPR graph + subgraph (all-mpnet, FAISS) | Giữ cấu trúc phòng → mặt phẳng → vật; bỏ truy hồi subgraph | Scene chỉ vài chục đến vài trăm vật, đưa cả graph đã lọc vào ngữ cảnh được |
| SeeGround (render PyTorch3D + VLM lớn) | CSVG: LLM viết chương trình ràng buộc, solver tìm vật; VLM chỉ phân xử trên keyframe thật | SeeGround với VLM 2B chỉ còn 30,2 / 27,2 trên ScanRefer |
| Qwen2.5-VL-7B qua vLLM | Qwen3-VL-4B Q4\_K\_M qua llama.cpp, nạp khi cần | File LLM 2,5 GB, vừa 6 GB cùng mmproj và KV cache; vLLM không hợp với một người dùng trên 6 GB |
| OpenFunGraph (S5b) | **Bỏ** | Phụ thuộc LLM/VLM lớn, không vừa 6 GB |
| FastAPI, Celery, Redis, MinIO, PostgreSQL+pgvector, vLLM | Docker Compose 3 container: api (FastAPI + Next.js tĩnh + SQLite), mask3d, llm (llama.cpp) | Một máy, một người dùng; vài chục nghìn vector tra vét cạn vẫn nhanh |
| `scannet-prep` + gói `.s3dpkg` | Giữ | Tách thành một script độc lập; hệ thống chỉ nhận gói đã xử lý xong |

**Đánh đổi phải nói rõ trong khoá luận:**

- Mask3D được huấn luyện trên ScanNet200 có nhãn, nên đề xuất instance không hoàn toàn zero-shot. Nhãn và truy vấn vẫn là từ vựng mở.
- Truy vấn chỉ dựa vào ngoại hình ("cái ghế màu đỏ") sẽ yếu hơn v2; bù bằng MobileCLIP2 và bước VLM phân xử.
- Chưa có paper nào đo model 4B viết chương trình ràng buộc; nếu chất lượng không đủ, đổi sang LLM cloud bằng một dòng config.
- Chỉ phát triển trên hai scan có sẵn, scene0000_00 và scene0000_01 (cùng một phòng, split train). Mask3D đã thấy các scan này lúc huấn luyện, nên chất lượng instance trên demo sẽ lạc quan hơn thực tế.

**Cập nhật sau grilling (08/10/2026).** Các quyết định sau ghi đè phần tương ứng của bản v3 ở các mục bên dưới; lý do nằm trong `docs/adr/`, thuật ngữ nằm trong `CONTEXT.md`:

- Layout repo `backend/` + `frontend/` + `mask3d/`, Python 3.12 (ADR 0001).
- Ngân sách VRAM là ~3,8 GB trống, vì màn hình và app Windows chạy trên chính RTX 3050 (ADR 0002).
- Dev native trên Windows, `uv.lock` đa nền tảng; `mask3d` và `llm` luôn chạy trong Docker (ADR 0003).
- `llm` có hai preset `text` và `vision` trên cùng một file model (ADR 0004).
- Viewpoint mặc định của vị từ theo góc nhìn là camera của viewer (ADR 0005).
- Chỉ hỗ trợ câu hỏi và giao diện tiếng Anh (ADR 0006).
- Spike Mask3D chạy trước và quyết định nhánh S3 (mục 11).
- Lộ trình không gắn tuần; thứ tự và phụ thuộc nằm trong các ticket ở `.scratch/s3d-v3/issues/`.

## 2. Kiến trúc tổng thể

Hệ thống chạy bằng Docker Compose trên một máy, gồm ba container: `api` (FastAPI, phục vụ luôn giao diện Next.js đã build tĩnh, điều phối job, solver), `mask3d` (chỉ dùng ở S3) và `llm` (`llama-server` của llama.cpp). GPU 6 GB là tài nguyên duy nhất cần giành, và Docker không chia VRAM giữa các container, nên một **khoá GPU** trong `api` là cơ chế bảo vệ duy nhất: mọi việc dùng GPU (stage offline, `mask3d`, nạp model vào `llm`) đều phải lấy khoá. Mỗi stage GPU chạy trong một tiến trình con và thoát khi xong, nên VRAM được trả hết trước khi việc sau bắt đầu.

&#91;embedded content: kiến trúc v3 · client chuẩn hoá, offline từng mô hình trên GPU, online solver\]

Cột trái chạy trên máy người dùng và chỉ gửi gói đã chuẩn hoá. Cột giữa chạy một lần cho mỗi scene, mỗi lúc chỉ một mô hình trên GPU. Cột phải chạy cho mỗi câu hỏi, đọc DB và chỉ gọi LLM/VLM khi luật và solver chưa đủ.

| Thành phần | Công nghệ | Vai trò |
| --- | --- | --- |
| `scannet_prep.py` | Một file script Python (khai báo phụ thuộc kiểu PEP 723), chạy bằng `uv run`, chỉ CPU, ngoài Docker | Raw ScanNet → gói `.s3dpkg`; hoàn toàn độc lập, không chia sẻ mã với hệ thống |
| `api` (container) | FastAPI + Pydantic v2, SSE; image Python 3.12 dựng bằng uv, chứa luôn web đã build tĩnh | API, phục vụ web, điều phối job, query engine, giữ khoá GPU |
| Web | Next.js (App Router, TypeScript, `output: 'export'`), React Three Fiber | Upload gói, xem 3D, tô sáng vật, hội thoại |
| Worker | Thread điều phối trong `api` + tiến trình con cho mỗi stage GPU hoặc CPU nặng | Chạy S0–S6 tuần tự; tiến trình con thoát để trả hết VRAM và không tranh GIL với luồng SSE |
| `mask3d` (container) | Image CUDA 11.3 ghim theo digest (PyTorch 1.12 + MinkowskiEngine), HTTP nội bộ | Chỉ S3; mỗi job chạy trong một tiến trình con |
| Query engine | Python thuần trong `api`: router, thư viện vị từ, solver ràng buộc, kiểm tra JSON bằng Pydantic | Phần lớn câu hỏi trả lời bằng hình học, không cần GPU |
| `llm` (container) | Image llama.cpp `server-cuda-b<build>` (CUDA 12) ghim theo digest, router mode; Qwen3-VL-4B-Instruct Q4\_K\_M với hai preset `text` (không mmproj) và `vision` (mmproj Q8\_0), KV cache q8\_0 | Sinh chương trình ràng buộc, caption, phân xử bằng ảnh; API tương thích OpenAI nên đổi sang cloud bằng config |
| Lưu trữ | SQLite (WAL) trong named volume; vector MobileCLIP2 lưu BLOB, tìm bằng NumPy | Metadata, scene graph, vector; gói, mảng `.npz` và `mesh.bin` trên đĩa |

**Model dùng trong hệ thống**

| Model | Dùng ở | Ghi chú |
| --- | --- | --- |
| Mask3D, checkpoint ScanNet200 | S3 | 27,4 AP closed-vocab trên val (repo); không có số VRAM công bố, phải đo trong spike Mask3D |
| YOLOE-26-L-seg (text-prompt 200 lớp ScanNet200 là chính, prompt-free 4.585 lớp là phụ) | S4a | Cùng API Ultralytics với YOLOE cũ, chính xác hơn; giấy phép AGPL-3.0 |
| MobileCLIP2-B (ảnh + text) | S4b, online | Một không gian embedding cho crop và câu hỏi; encoder text chạy CPU khi online |
| Qwen3-VL-4B-Instruct GGUF Q4\_K\_M (2,5 GB) + mmproj Q8\_0 (454 MB) | S4c, online | Một model cho mọi vai trò ngôn ngữ; chỉ dùng bản Instruct, không dùng bản Thinking |

## 3. Tiền xử lý raw: script độc lập scannet\_prep.py

Tiền xử lý raw ScanNet là **một file script Python duy nhất**, chạy riêng trên máy có dữ liệu raw. Script không import gì từ hệ thống và không cần hệ thống đang chạy. Ngược lại, hệ thống không đọc raw ScanNet, không giải mã `.sens` và không chạy lại bước nào của script: nó **chỉ nhận gói `.s3dpkg` mà script đã tạo thành công**.

File nằm ở `tools/scannet_prep.py`, ngoài project `backend/` và ngoài mọi image Docker; có thể chép riêng file này sang máy khác để chạy. Phụ thuộc được khai báo ngay đầu file theo chuẩn inline script metadata (PEP 723), nên `uv run` tự dựng môi trường tạm khi chạy, không cần cài gói.

```python
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "opencv-python-headless", "plyfile", "pyarrow"]
# ///
```

```bash
# một scene
uv run tools/scannet_prep.py pack dataset/scans/scene0011_00 --out dataset/preprocessing
# nhiều scene theo danh sách
uv run tools/scannet_prep.py batch dataset/scans --list scenes.txt --out dataset/preprocessing --workers 4
# kiểm tra lại một gói đã tạo
uv run tools/scannet_prep.py verify dataset/preprocessing/scene0011_00.s3dpkg
```

Mã thoát 0 khi thành công, khác 0 khi lỗi kèm tên bước lỗi. `batch` ghi báo cáo `prep_report.csv` (scene, trạng thái, thời gian, kích thước gói, lỗi) và bỏ qua scene đã có gói hợp lệ khi chạy lại.

**Các bước của `pack`**

1. Kiểm tra raw: có `.sens`, `_vh_clean_2.ply` và `_vh_clean_2.0.010000.segs.json`; header `.sens` đọc được; độ dài `segIndices` bằng số đỉnh.
2. Giải mã `.sens` bằng reader Python 3 đọc stream (bản gốc của ScanNet là Python 2, nạp cả file); kích thước ảnh và `depth_shift` lấy từ header.
3. Giữ 1 trong 10 khung, bỏ khung có pose không hữu hạn, ghi điểm mờ (Laplacian).
4. Ghi ảnh màu JPEG; mặc định thu cạnh dài về 960 px (`--color-width`); depth PNG 16-bit, pose, intrinsics đã hiệu chỉnh theo kích thước mới.
5. Áp `axisAlignment` cho mesh, normal và pose; giữ thứ tự đỉnh, faces, RGB và superpoint từ `segs.json`. Ghi ma trận nguồn thành `source_axis_alignment` và hệ toạ độ `coordinate_frame: axis_aligned` trong manifest v2. Thiếu hoặc sai `axisAlignment` thì dừng, không tạo Package hoàn chỉnh; identity chỉ được nhận khi đã được khai báo hợp lệ.
6. Ghi gói ra file tạm `scene0011_00.s3dpkg.partial`, tự chạy `verify` trên file đó, rồi mới đổi tên thành `.s3dpkg`. Gói hỏng giữa chừng không bao giờ mang đuôi `.s3dpkg`.

Gói không chứa nhãn GT; `aggregation.json` và file nhãn không được dùng.

```text
scene0011_00.s3dpkg              # tar không nén
  manifest.json                  # format_version "s3dpkg/2", status "complete", phiên bản script,
                                 # tham số, sha256, coordinate_frame, source_axis_alignment
  mesh/vh_clean_2.ply            # đã căn chỉnh, giữ thứ tự đỉnh
  mesh/superpoints.npy           # int32 theo đỉnh
  calib/intrinsics.json          # màu + depth, kích thước, depth_shift
  frames/index.parquet           # frame_id, blur, valid
  frames/color/000120.jpg
  frames/depth/000120.png        # uint16
  frames/pose/000120.txt         # 4×4 camera→aligned world
```

**Ranh giới với hệ thống là đặc tả gói.** Script và hệ thống không chia sẻ mã. Hợp đồng duy nhất là `s3dpkg/2` trong `docs/s3dpkg-spec.md`. S0 tự kiểm tra đuôi, phiên bản, hệ toạ độ đã căn chỉnh, trạng thái complete, file và checksum. V1 bị từ chối với hướng dẫn chạy lại prep; không có nhánh căn chỉnh cũ trong hệ thống. Xem ADR 0009.

Đưa gói vào hệ thống: chọn hoặc kéo thả file từ `dataset/preprocessing/` để upload qua `POST /v1/imports` và S0. Gói được chép vào volume dữ liệu rồi mới xếp hàng; file ngoài hệ thống vẫn được giữ riêng. Không có inbox, bind mount raw hay chức năng tiền xử lý trong ứng dụng.

Mỗi scan có nhiều nhất một scene, định danh bằng chính mã scan (`scene0011_00`). Import lại gói có sha256 trùng gói đang dùng thì không làm gì. Gói khác cho cùng scan bị từ chối, trừ khi người dùng chọn Replace: scene cũ bị xoá cùng artifact, gói mới được xử lý lại từ S0.

## 4. Pipeline offline và lịch VRAM

Worker trong `api` chỉ là một thread điều phối: lấy job từ bảng `jobs`, giữ khoá GPU và chạy từng stage tuần tự. Mỗi stage dùng GPU chạy trong một **tiến trình con** riêng (`python -m s3d_app.stages.<tên>`): nạp model, xử lý xong toàn scene, ghi kết quả ra file rồi thoát. Thoát tiến trình là cách chắc chắn để trả CUDA context của PyTorch; `torch.cuda.empty_cache()` không trả phần này. Stage CPU nặng (RANSAC, scene graph) cũng chạy tiến trình con để không tranh GIL với luồng SSE. Artifact ghi tại `data/scenes/{scan}/{stage}/{config_hash}/`; artifact đã có thì bỏ qua.

| Stage | Làm gì | Model | Chạy ở | VRAM ước tính |
| --- | --- | --- | --- | --- |
| S0 Verify | Schema, checksum của gói | — | Thread `api` | 0 |
| S1 Load | Đọc/giải nén Package đã căn chỉnh; không áp lại ma trận nguồn | — | Thread `api` | 0 |
| S2 Geometry | Điểm, superpoint, sàn/tường bằng RANSAC, visibility cache trên GPU | — (PyTorch tensor) | Tiến trình con | dưới 1 GB |
| S3 Instance | Đề xuất 3D class-agnostic | Mask3D ScanNet200 | Container `mask3d` | Chưa có số, dự kiến 2–5 GB; đo trong spike Mask3D |
| S4a Labels | Nhãn từ vựng mở bằng bỏ phiếu đa view | YOLOE-26-L-seg | Tiến trình con | \~1–2 GB |
| S4b Embeddings | Một vector mỗi instance + màu chủ đạo | MobileCLIP2-B | Tiến trình con | dưới 1 GB |
| S4c Captions | Chỉ khi cần (mặc định tắt offline) | Qwen3-VL-4B Q4 | Container `llm` (preset `vision`) | \~3,9–4,3 GB |
| S5 Scene graph | Phòng → mặt phẳng → vật, vị từ hình học | — | Tiến trình con (CPU) | 0 |
| S6 Publish | Ghi SQLite, vector, mask `.npz`, mesh nhị phân `mesh.bin` cho web | — | Thread `api` | 0 |

Các con số VRAM là ước tính; chưa nguồn nào công bố số đo trên card 6 GB. Bảng `stage_runs` ghi lại VRAM đỉnh thực tế của từng stage. Ngân sách thiết kế là ~3,8 GB trống, vì màn hình và app Windows giữ khoảng 2 GB trên cùng card (ADR 0002); khoá GPU chỉ cho stage chạy khi NVML báo đủ VRAM và báo người dùng đóng bớt app nếu thiếu.

**S2 – Geometry.** Điểm là đỉnh `vh_clean_2.ply`, giữ đúng thứ tự vì mask, viewer và API đều đánh chỉ số theo đỉnh này. Sàn và tường tìm bằng RANSAC trên CPU, nhờ trục +Z đã căn theo `axisAlignment`. Visibility tính trên GPU theo lô khung: chiếu mọi điểm lên mỗi keyframe, giữ điểm lệch depth dưới 0,1 m. Open-YOLO 3D cho thấy vector hoá bước này giảm thời gian gán nhãn từ 376 xuống 18 giây mà không đổi mAP.

**S3 – Instance.**

- Chạy Mask3D checkpoint ScanNet200 ở fp16, giới hạn số query; lọc trùng bằng NMS; bỏ mask dưới 100 đỉnh.
- Nếu hết VRAM: thử voxel 2–3 cm rồi chiếu mask về đỉnh gốc.
- **Phương án dự phòng chỉ 2D:** mask YOLOE-seg trên keyframe → nâng lên superpoint theo tỉ lệ chồng lấn → gộp các ứng viên trùng nhau. Mask kém hơn Mask3D theo số công bố, nhưng không cần MinkowskiEngine.

**S4a – Labels (Open-YOLO 3D).** Dùng YOLOE-26-L-seg; theo Ultralytics, YOLOE-26 chính xác hơn YOLOE-v8 0,8–1,7 AP trên LVIS và dùng cùng API. Nguồn nhãn chính là chế độ **text-prompt** với 200 tên lớp ScanNet200. Chế độ prompt-free (\~4.585 lớp) chỉ là nguồn phụ để bổ sung nhãn đuôi dài, với trọng số thấp hơn khi bỏ phiếu, vì nó kém rõ rệt: bản prompt-free lớn nhất chỉ đạt 31,1 AP LVIS, so với 40,6 AP của bản text-prompt cùng cỡ. Mỗi box tạo một bản đồ nhãn trên ảnh. Với mỗi instance, chiếu các điểm nhìn thấy lên những khung nó hiện rõ nhất, đếm nhãn mà các điểm rơi vào, rồi bỏ phiếu qua các view. Node lưu nhãn chính, độ tin cậy và **top-3 nhãn thay thế** để router và solver dùng khi từ người dùng hỏi lệch nhãn. Open-YOLO 3D cho thấy thêm SAM vào bước này còn làm mAP giảm nhẹ và chậm hơn khoảng 5 lần.

**S4b – Embeddings và màu.** Lấy 3–5 crop có nhiều điểm nhìn thấy nhất, encode bằng MobileCLIP2-B, bỏ crop có z-score độ giống dưới −3 (ROFA của ReLaGS), lấy trung bình chuẩn hoá. Vector này phục vụ truy vấn tự do như "thứ để ngồi". Vì họ CLIP yếu ở màu chi tiết, stage này còn tính **màu chủ đạo** của instance bằng histogram HSV trên màu đỉnh mesh, lưu thành tên màu (đỏ, xanh lá, trắng…) để solver dùng vị từ `COLOR` xác định. Đây là bổ sung thiết kế, chưa có số đo.

**S4c – Captions (lười).** Không chạy mặc định. Caption của một instance chỉ được sinh khi câu hỏi cần nó, rồi cache trong SQLite. Cờ `--captions top-N` tạo trước caption cho N vật lớn nhất nếu muốn.

## 5. Scene graph và thư viện vị từ

Scene graph có 3 mức theo Sparse3DPR: phòng → sàn/tường → đồ vật. Mọi quan hệ được tính bằng hình học từ bbox và điểm, không nhờ LLM suy ra. FreeQ-Graph ghi nhận các phương pháp dựa nhiều vào LLM để suy quan hệ (ConceptGraphs, BBQ) hay sai với vật nhỏ hoặc mỏng.

**Nút:** `id`, mức, nhãn chính + độ tin cậy + top-3 nhãn thay thế, tâm, kích thước bbox (đã căn trục), số điểm, màu chủ đạo (HSV), vector MobileCLIP2, top keyframe, caption (nếu đã sinh).

**Thư viện vị từ** (theo bộ khoảng 20 vị từ của CSVG; ngưỡng lớn cho kết quả tốt nhất theo ablation của paper):

| Nhóm | Vị từ | Cách tính |
| --- | --- | --- |
| Tiếp xúc theo chiều đứng | `ON`, `UNDER`, `SUPPORTS` | Đáy A gần mặt trên B theo z, chồng lấn mặt phẳng xy |
| Vị trí đứng | `ABOVE`, `BELOW` | Chênh z của tâm, có chồng lấn xy một phần |
| Chứa | `IN`, `CONTAINS` | Tỉ lệ điểm của A nằm trong bbox B |
| Khoảng cách | `NEAR`, `FAR`, `NEXT_TO` | Khoảng cách gần nhất giữa hai đám điểm |
| Theo góc nhìn | `LEFT`, `RIGHT`, `FRONT`, `BEHIND`, `BETWEEN` | Trong hệ toạ độ của Viewpoint: mặc định là camera viewer gửi kèm câu hỏi; không có camera thì người nhìn đứng ở tâm phòng nhìn về anchor; câu nêu rõ góc nhìn ("from the door") ghi đè cả hai (ADR 0005) |
| Với cấu trúc | `AGAINST_WALL`, `ON_FLOOR`, `IN_CORNER` | Khoảng cách tới mặt phẳng sàn/tường |
| Thuộc tính | `COLOR` | Màu chủ đạo HSV của instance khớp tên màu trong câu |
| Cực trị và đếm | `CLOSEST`, `FARTHEST`, `LARGEST`, `SMALLEST`, `HIGHEST`, `LOWEST`, `COUNT`, `NOT` | Trên tập ứng viên sau khi lọc |

Các quan hệ tiếp xúc, chứa, gần và với cấu trúc được tính trước và lưu làm cạnh; vị từ theo góc nhìn và cực trị tính lúc truy vấn vì phụ thuộc anchor và góc nhìn.

Khi đưa cho LLM, mỗi nút là một dòng ngắn; scene thường chỉ vài chục đến vài trăm vật nên đưa cả danh sách nhãn đã lọc theo câu hỏi là đủ, không cần truy hồi subgraph bằng embedding:

```text
[42] office chair (0.81) | c=(1.21,0.43,0.52) s=(0.61,0.60,1.02) | on: floor; near: desk[7], window[9]
```

## 6. Suy luận online

LLM chỉ làm một việc khó: dịch câu hỏi thành một chương trình ràng buộc ngắn. Tìm vật, đếm, so sánh do solver hình học làm. VLM chỉ được gọi khi solver còn nhiều lời giải và câu hỏi có từ chỉ ngoại hình. Cách làm này theo CSVG; trong ablation của paper, riêng phần giải toàn cục và heuristic khoảng cách đã nâng Acc@0.5 trên ScanRefer từ 28,9 lên 37,3, và các phần này không tốn GPU.

1. **Ngữ cảnh phiên:** thay "nó", "cái đó" bằng ID vừa nhắc (lưu trong SQLite) hoặc vật người dùng vừa click trên viewer.
2. **Router luật:** cụm danh từ không có từ quan hệ hay từ hỏi → tra theo nhãn + MobileCLIP text (CPU), chọn nhiều kết quả tại điểm rơi lớn nhất (ReLaGS). Không gọi LLM.
3. **Sinh chương trình:** Qwen3-VL-4B-Instruct nhận câu hỏi, danh sách nhãn có trong scene và 5–8 ví dụ ngắn tiếng Anh (ADR 0006), chạy trên preset `text`; xuất JSON theo `response_format` JSON schema. Schema giữ phẳng và dùng `enum` cho tên vị từ và tên biến, nên model không thể sinh vị từ không tồn tại. Không dùng bản Thinking vì llama.cpp bỏ qua grammar khi bật thinking.
4. **Kiểm tra JSON:** `api` luôn validate lại bằng Pydantic, vì llama.cpp có lỗi đã biết trả 200 OK kèm văn bản tự do khi grammar không áp dụng được. Sai thì thử lại một lần; sai tiếp thì chuyển sang hỏi lại người dùng.
5. **Chuẩn hoá danh từ:** mỗi danh từ trong chương trình được ánh xạ về các nhãn có trong scene bằng độ giống text MobileCLIP (top-k) và top-3 nhãn thay thế của node, tránh "0 lời giải" chỉ vì lệch từ (ví dụ "couch" → sofa, armchair).
6. **Solver:** mỗi biến có tập ứng viên theo nhãn (phân bố nhãn S4a + độ giống MobileCLIP); backtracking tìm mọi gán thỏa mãn ràng buộc; xếp hạng bằng độ tin cậy nhãn và heuristic khoảng cách trung bình nhỏ nhất của CSVG.
7. **Xử lý kết quả:**
   - 0 lời giải → nới lỏng ràng buộc yếu nhất, báo cho người dùng đã nới cái nào.
   - 1 lời giải → trả lời.
   - Nhiều lời giải và câu có từ ngoại hình → áp `COLOR` trước nếu là màu; còn nhiều thì **VLM phân xử** (Tiebreak, preset `vision`): Qwen3-VL-4B xem tối đa 2 keyframe thật (cạnh dài tối đa 768 px), mỗi ứng viên được vẽ viền màu và đánh số trên ảnh, model chọn một số. Nếu NVML báo không đủ VRAM để nạp preset `vision` thì bỏ bước này.
   - Vẫn còn nhiều → **hỏi lại** người dùng, kèm đặc điểm khác nhau giữa các ứng viên và tô sáng chúng.
8. **Kiểm chứng và trả lời qua SSE:** mọi ID phải có trong scene, mọi con số đến từ solver; câu chữ do LLM diễn đạt từ kết quả solver.

**Ví dụ chương trình** cho "the chair next to the window, closest to the desk":

```json
{
  "intent": "ground",
  "vars": {"t": "chair", "w": "window", "d": "desk"},
  "constraints": [["NEAR", "t", "w"]],
  "select": ["CLOSEST", "t", "d"],
  "target": "t",
  "appearance": []
}
```

| Loại câu | Ví dụ | Xử lý |
| --- | --- | --- |
| Tìm/tô sáng | "Highlight everything you can sit on" | Router luật + MobileCLIP, không gọi LLM |
| Tham chiếu | "The chair next to the window, closest to the desk" | Chương trình + solver, VLM phân xử nếu cần |
| Đếm / tồn tại / quan hệ | "How many pillows are on the sofa?" | Chương trình với `COUNT` / `EXISTS`, trả số chính xác khi segmentation đúng |
| Thuộc tính | "What color is the table near the door?" | Solver tìm vật → VLM đọc thuộc tính trên keyframe tốt nhất |
| Mở | "What is this room used for?" | LLM trên graph đã tuần tự hoá, có thể kèm 1–2 keyframe |

**Công tắc LLM cloud.** `llm.base_url` trong config trỏ tới `llama-server` local mặc định; đổi sang một endpoint tương thích OpenAI là dùng LLM lớn mà không sửa code. Dùng khi model 4B trả lời chưa đủ tốt; dữ liệu scene vẫn ở trên máy, chỉ câu hỏi, danh sách nhãn và (khi phân xử) tối đa 2 keyframe được gửi đi.

## 7. API

REST `/v1` chạy trên `localhost`, SSE cho hỏi đáp và tiến độ. Cùng tiến trình FastAPI phục vụ giao diện web tĩnh (Next.js static export) ở `/`, nên web và API cùng origin, không cần CORS. Chỉ một người dùng nên không cần JWT; cổng chỉ bind vào `127.0.0.1`.

| Method và path | Mục đích |
| --- | --- |
| `GET /` | Giao diện web (file tĩnh của Next.js) |
| `POST /v1/imports` | Nhận upload `.s3dpkg` v2 từ web, chạy `verify`, chép vào volume dữ liệu, xếp job |
| `GET /v1/scenes` · `GET /v1/scenes/{id}` · `DELETE /v1/scenes/{id}` | Danh sách, trạng thái, xoá |
| `GET /v1/scenes/{id}/events` (SSE) | Tiến độ từng stage |
| `POST /v1/scenes/{id}/reprocess` | Chạy lại từ một stage |
| `GET /v1/scenes/{id}/mesh` | Mesh nhị phân `mesh.bin` cho viewer: vị trí, màu, chỉ số tam giác và id vật theo từng đỉnh |
| `GET /v1/scenes/{id}/objects` · `GET /v1/scenes/{id}/graph` | Danh sách vật, scene graph |
| `GET /v1/scenes/{id}/objects/{oid}/mask` | Chỉ số đỉnh của một vật |
| `GET /v1/scenes/{id}/frames/{fid}.jpg` | Keyframe làm bằng chứng cho câu trả lời |
| `POST /v1/scenes/{id}/ask` (SSE) | Một câu hỏi tiếng Anh, kèm `session_id` tuỳ chọn để hỏi nhiều lượt và `viewpoint` tuỳ chọn (pose camera của viewer) |

Sự kiện SSE của `/ask`: `program` (chương trình đã sinh) → `candidates` → `tiebreak` (nếu có) → `token` → `final` hoặc `clarify`.

```json
{
  "session_id": "s_01", "intent": "ground",
  "answer": "The office chair next to the window, closest to the desk.",
  "targets": [{"id": 42, "label": "office chair", "confidence": 0.81,
               "bbox": {"center": [1.21, 0.43, 0.52], "size": [0.61, 0.60, 1.02]}}],
  "related": [{"id": 9, "label": "window"}, {"id": 7, "label": "desk"}],
  "program": {"constraints": [["NEAR", "t", "w"]], "select": ["CLOSEST", "t", "d"]},
  "evidence": {"n_solutions": 1, "tiebreak": false, "viewpoint": "camera", "keyframe": "/v1/scenes/scene0011_00/frames/000430.jpg"},
  "latency_ms": 1840
}
```

## 8. Frontend Next.js

Giao diện tiếng Anh là ứng dụng Next.js (App Router, TypeScript, Tailwind CSS, shadcn/ui) build dạng **static export** (`output: 'export'`). Thư mục `out/` được chép vào image `api` và FastAPI phục vụ bằng `StaticFiles` ở `/`. Web và API cùng origin nên không cần CORS hay proxy; upload gói lớn và luồng SSE đi thẳng tới FastAPI. Hệ thống không dùng tính năng server của Next.js (SSR, middleware, rewrites, route handler động), nên static export không mất gì và bớt được một container Node.

| Trang | Nội dung |
| --- | --- |
| `/` | Danh sách scene và trạng thái; chọn/kéo thả `.s3dpkg` v2 để upload; tiến độ từng stage qua `GET /events` (`EventSource`) |
| `/scene?id=scene0011_00` | Viewer 3D bên trái, khung hội thoại bên phải; danh sách vật lọc được theo nhãn |

Trang scene dùng tham số query thay cho route động `/scenes/[id]`, vì static export chỉ sinh được route động có sẵn lúc build, còn scene thì người dùng thêm sau.

**Viewer 3D.** Dùng three.js qua React Three Fiber và drei, nạp trong client component bằng `next/dynamic` với `ssr: false`.

- Mesh dùng định dạng nhị phân riêng `mesh.bin`, xuất ở S6: header nhỏ, rồi `Float32` vị trí, `Uint8` màu, `Uint32` chỉ số tam giác, `Int32` id vật theo đỉnh. Web nạp bằng `fetch` + `ArrayBuffer` thẳng vào `BufferGeometry`, không cần parser. Thứ tự đỉnh giữ đúng như `vh_clean_2.ply`.
- Không nén Draco: chế độ edgebreaker của Draco đổi thứ tự đỉnh, làm lệch id vật theo đỉnh. Mesh truyền qua localhost nên vài chục MB không phải nút thắt.
- Tô sáng trong shader: thuộc tính đỉnh `instance` cùng một texture nhỏ chứa trạng thái tô sáng theo id (sửa shader qua `onBeforeCompile`). Đổi trạng thái chỉ cập nhật texture, không ghi lại mảng màu.
- Click lên mesh: raycast lấy `face.a` → `instance[a]` → id vật, hiện nhãn và cho hỏi tiếp về "cái này".
- Khi có kết quả: tô màu vật đích và vật liên quan, vẽ bbox, camera bay tới vật.

**Khung hội thoại.** `/ask` trả SSE qua phương thức POST nên không dùng được `EventSource`; client đọc `fetch` + `ReadableStream` và tách sự kiện bằng thư viện `eventsource-parser`. Mỗi câu hỏi gửi kèm pose camera hiện tại của viewer làm Viewpoint (ADR 0005).

- `program`, `candidates`: hiện dạng thu gọn để người dùng thấy hệ thống hiểu câu hỏi thế nào.
- `token`: hiện câu trả lời dần.
- `final`: tô sáng `targets`, hiện keyframe bằng chứng.
- `clarify`: tô các ứng viên bằng màu khác nhau kèm nút chọn; lựa chọn gửi lại cùng `session_id`.

Dữ liệu REST quản lý bằng TanStack Query; kiểu TypeScript sinh từ `/openapi.json` của FastAPI bằng `openapi-typescript`, nên đổi API là lỗi hiện ngay khi build web. Web gọi API bằng đường dẫn tương đối `/v1/...`.

```text
frontend/
  app/page.tsx                  # danh sách scene + upload
  app/scene/page.tsx            # đọc ?id=, viewer + hội thoại
  components/SceneViewer.tsx    # R3F, nạp mesh.bin, shader tô sáng, raycast
  components/ChatPanel.tsx      # SSE qua fetch
  lib/api.ts                    # client REST + kiểu sinh từ OpenAPI
  next.config.ts                # output: "export"
```

## 9. Lưu trữ: SQLite + filesystem

Một file SQLite (chế độ WAL) giữ metadata, job, scene graph và vector; mảng lớn nằm trên đĩa. Tất cả nằm trong **named volume** của Docker (trên ext4 của máy ảo WSL2), không đặt trên ổ `D:` qua bind mount: SQLite WAL không chạy an toàn trên filesystem mạng, còn I/O qua ranh giới Windows–WSL2 chậm hơn nhiều. Package được upload từ Windows; ứng dụng không mount thư mục preprocessing hoặc raw scan. Khi dev native trên Windows (ADR 0003), `api` dùng một thư mục dữ liệu local trên ổ Windows, truy cập trực tiếp chứ không qua bind mount.

Vector MobileCLIP2 lưu dạng BLOB float32 trong bảng `nodes`. Mỗi scene chỉ vài trăm vật, nên khi mở scene `api` nạp các vector vào một ma trận NumPy và tìm vét cạn gần như tức thời. Không cần sqlite-vec (vẫn ở giai đoạn pre-v1).

```text
volume s3d-data   → /data
  s3d.sqlite
  packages/scene0011_00.s3dpkg
  scenes/scene0011_00/{stage}/{config_hash}/
    s1_load/       color/ depth/ pose/ intrinsics.json frames.parquet
    s2_geometry/   points.npz superpoints.npy planes.json visibility.npz
    s3_instances/  masks.npz                 # chỉ số đỉnh theo instance
    s4_semantics/  labels.json embeddings.f16.npy colors.json crops/
    s6_publish/    mesh.bin                  # mesh nhị phân cho web
volume s3d-models → /models
  mask3d/  yoloe/  mobileclip2/
  llm/     Qwen3VL-4B-Instruct-Q4_K_M.gguf  mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf  presets.ini
dataset/preprocessing/*.s3dpkg             # ngoài hệ thống; người dùng upload file
```

```sql
CREATE TABLE scenes (id TEXT PRIMARY KEY,          -- chính là mã scan, ví dụ scene0011_00
  status TEXT, version TEXT, package_sha256 TEXT, manifest JSON, created_at TEXT);
CREATE TABLE jobs (id INTEGER PRIMARY KEY, scene_id TEXT, from_stage TEXT, status TEXT,
  created_at TEXT, started_at TEXT, finished_at TEXT, error TEXT);
CREATE TABLE stage_runs (job_id INTEGER, stage TEXT, status TEXT, duration_s REAL,
  peak_vram_mb INTEGER, artifact TEXT, PRIMARY KEY (job_id, stage));
CREATE TABLE nodes (scene_id TEXT, id INTEGER, level INTEGER, label TEXT, label_dist JSON,
  label_alt JSON, confidence REAL, cx REAL, cy REAL, cz REAL, sx REAL, sy REAL, sz REAL,
  n_points INTEGER, color TEXT, rgb JSON, top_frames JSON, caption TEXT,
  embedding BLOB,                     -- float32, số chiều theo MobileCLIP2-B
  PRIMARY KEY (scene_id, id));
CREATE TABLE edges (scene_id TEXT, src INTEGER, dst INTEGER, predicate TEXT, score REAL,
  PRIMARY KEY (scene_id, src, dst, predicate));
CREATE TABLE sessions (id TEXT PRIMARY KEY, scene_id TEXT, memory JSON, created_at TEXT);
CREATE TABLE queries (id INTEGER PRIMARY KEY, session_id TEXT, text TEXT, program JSON,
  viewpoint JSON, result JSON, n_solutions INTEGER, used_tiebreak INTEGER, json_retry INTEGER,
  latency_ms INTEGER);
```

Bảng `queries` lưu chương trình LLM sinh ra, số lần phải sinh lại JSON và kết quả solver, dùng để xem lại lịch sử hội thoại và gỡ lỗi khi một câu trả lời sai. Sao lưu toàn bộ dữ liệu bằng: `docker run --rm -v s3d-data:/d -v ${PWD}:/b alpine tar czf /b/s3d-data.tgz -C /d .`

## 10. Cài đặt và triển khai bằng Docker

Toàn bộ hệ thống build và chạy bằng Docker Compose. Bên trong các image Python, **uv** quản lý phiên bản Python, môi trường ảo và khoá phiên bản bằng `uv.lock`; không dùng conda hay pip. Model ngôn ngữ chạy bằng image chính thức của llama.cpp. Mọi image và model đều ghim phiên bản; sau khi tải model lần đầu, hệ thống chạy hoàn toàn offline.

**Yêu cầu máy**

- Windows: Docker Desktop dùng backend WSL2 (GPU trong container chỉ có trên backend này) và driver NVIDIA mới. Linux: Docker Engine + NVIDIA Container Toolkit.
- Chạy hệ thống không cần cài Python, Node hay CUDA toolkit: mọi thứ nằm trong image. Dev native cần thêm uv và Node 24.
- Repo có thể nằm trên ổ Windows (ADR 0003); khi chạy bằng Compose, dữ liệu và model nằm trong named volume (mục 9).
- Các container cùng thấy GPU nhưng Docker không chia VRAM giữa chúng, nên khoá GPU trong `api` là bắt buộc.
- Riêng tiền xử lý raw chỉ cần uv trên máy có raw ScanNet để chạy `tools/scannet_prep.py` (mục 3); không cần Docker hay GPU.

**Cấu trúc repo**

```text
3D-scene/
  compose.yaml
  compose.dev.yaml       # dev native: mở cổng llm, mask3d trên 127.0.0.1
  CONTEXT.md             # glossary của dự án
  backend/               # uv project của hệ thống, Python 3.12, package s3d_app:
                         # FastAPI, worker, stages, solver, YOLOE, MobileCLIP2
  mask3d/                # project uv riêng: Python 3.10, PyTorch 1.12 + cu113, server nội bộ
  frontend/              # Next.js (mục 8), build tĩnh vào image api
  docker/
    api.Dockerfile
    mask3d.Dockerfile
  tools/
    scannet_prep.py      # script tiền xử lý độc lập (mục 3), không thuộc project backend
  docs/
    adr/                 # quyết định kiến trúc
    s3dpkg-spec.md       # đặc tả gói: hợp đồng duy nhất giữa script và hệ thống
  models.lock            # tên file, nguồn và sha256 của mọi model cần tải
```

| Service | Image | GPU | Cổng | Vai trò |
| --- | --- | --- | --- | --- |
| `api` | Build từ `docker/api.Dockerfile`: node:24-alpine build web → python:3.12-slim + uv | Có | `127.0.0.1:8000` | Web, API, worker, solver |
| `mask3d` | Build từ `docker/mask3d.Dockerfile` trên CUDA 11.3.1 ghim digest; lưu tar dự phòng | Có | nội bộ 9000 | Chỉ S3 |
| `llm` | `ghcr.io/ggml-org/llama.cpp:server-cuda-b<build>` (CUDA 12) ghim digest | Có | nội bộ 8080 | LLM/VLM |

Chỉ `api` mở cổng ra máy, và chỉ trên `127.0.0.1`. `llm` không mở cổng ra ngoài mạng Compose.

**compose.yaml** (rút gọn)

```yaml
x-gpu: &gpu
  deploy:
    resources:
      reservations:
        devices: [{ driver: nvidia, count: 1, capabilities: [gpu] }]

services:
  api:
    <<: *gpu
    build: { context: ., dockerfile: docker/api.Dockerfile }
    ports: ["127.0.0.1:8000:8000"]
    environment:
      S3D_DATA: /data
      S3D_MODELS: /models
      LLM_BASE_URL: http://llm:8080
      MASK3D_URL: http://mask3d:9000
    volumes:
      - s3d-data:/data
      - s3d-models:/models
    depends_on: [llm, mask3d]

  mask3d:
    <<: *gpu
    image: s3d-mask3d:1
    build: { context: ., dockerfile: docker/mask3d.Dockerfile }
    volumes: ["s3d-data:/data", "s3d-models:/models:ro"]

  llm:
    <<: *gpu
    image: ghcr.io/ggml-org/llama.cpp:server-cuda-b<build>@sha256:<digest>
    command: ["--models-preset", "/models/llm/presets.ini",
              "--models-max", "1", "--no-models-autoload",
              "--sleep-idle-seconds", "600",
              "--host", "0.0.0.0", "--port", "8080"]
    volumes: ["s3d-models:/models:ro"]

volumes:
  s3d-data:
  s3d-models:
```

**docker/api.Dockerfile** (rút gọn). Giai đoạn đầu build web tĩnh; giai đoạn sau dựng môi trường Python bằng uv và chép web vào. Wheel PyTorch CUDA đã kèm thư viện CUDA runtime, nên nền chỉ cần Python slim.

```dockerfile
FROM node:24-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build                        # output: "export" → /web/out

FROM python:3.12-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
# lớp phụ thuộc: chỉ build lại khi uv.lock đổi
COPY backend/pyproject.toml backend/uv.lock backend/.python-version ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project
# lớp mã nguồn
COPY backend/ ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev
COPY --from=web /web/out /app/static
ENV PATH="/app/.venv/bin:$PATH"
CMD ["s3d", "serve", "--host", "0.0.0.0", "--port", "8000", "--static", "/app/static"]
```

`backend/pyproject.toml` lấy torch, torchvision từ index `https://download.pytorch.org/whl/cu128` với `explicit = true`; `uv.lock` resolve cho cả Windows lẫn Linux x86\_64 để dev native được (ADR 0003), còn image chỉ cài wheel Linux. Dùng `opencv-python-headless` và `nvidia-ml-py` (đọc VRAM trống cho khoá GPU).

**docker/mask3d.Dockerfile** (rút gọn). Tag CUDA 11.3.1 đã nằm trong danh sách tag không còn hỗ trợ của NVIDIA và có thể bị xoá, nên ghim theo digest và lưu image đã build ra file tar.

```dockerfile
FROM nvidia/cuda:11.3.1-cudnn8-devel-ubuntu20.04@sha256:<digest> AS build
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /bin/
# docker build không thấy GPU: thiếu FORCE_CUDA sẽ ra bản chỉ CPU mà không báo lỗi
ENV UV_PYTHON_INSTALL_DIR=/opt/python UV_LINK_MODE=copy \
    TORCH_CUDA_ARCH_LIST="8.6" FORCE_CUDA=1 MAX_JOBS=2
RUN apt-get update && apt-get install -y --no-install-recommends \
    git build-essential libopenblas-dev
WORKDIR /app
COPY mask3d/ ./
RUN uv python install 3.10 \
 && uv sync --frozen \
 && uv sync --frozen --extra compile      # biên dịch MinkowskiEngine với torch đã cài

FROM nvidia/cuda:11.3.1-cudnn8-runtime-ubuntu20.04@sha256:<digest>
RUN apt-get update && apt-get install -y --no-install-recommends libopenblas0 \
 && rm -rf /var/lib/apt/lists/*
COPY --from=build /opt/python /opt/python
COPY --from=build /app /app
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"
CMD ["python", "-m", "mask3d_runner.server", "--port", "9000"]
```

- `mask3d/pyproject.toml` ghim `torch==1.12.1+cu113` từ index `cu113`, khai báo MinkowskiEngine trong extra `compile` với `no-build-isolation-package` và nguồn git ở commit Mask3D chỉ định.
- `TORCH_CUDA_ARCH_LIST="8.6"` chỉ biên dịch cho RTX 3050; `MAX_JOBS=2` tránh nvcc dùng hết RAM của máy ảo WSL2.
- Sau khi build, kiểm tra trong container đang chạy rằng MinkowskiEngine báo có hỗ trợ CUDA (`ME.print_diagnostics()`), rồi lưu bản dự phòng: `docker save s3d-mask3d:1 -o D:/s3d/images/s3d-mask3d.tar` (nạp lại bằng `docker load`).
- Phương án B nếu không dùng được CUDA 11.3: CUDA 12.1 và vá header thrust cho MinkowskiEngine; với CUDA 12.8 vẫn còn báo lỗi build.

**Giao tiếp với mask3d.** Container `mask3d` chạy một server HTTP nội bộ rất nhỏ. Worker gọi `POST http://mask3d:9000/run` với đường dẫn scene và thư mục ra trong volume `/data`; server chạy Mask3D trong một tiến trình con, ghi `masks.npz`, rồi tiến trình con thoát để trả hết VRAM. Không truyền dữ liệu lớn qua HTTP.

**llama.cpp (`llm`)**

`llama-server` chạy ở router mode. File preset là INI: mỗi section là một model, khoá là tên đối số dòng lệnh bỏ dấu `--`, section `[*]` là mặc định chung.

```ini
[*]
n-gpu-layers = 99
flash-attn = on
ctx-size = 4096
cache-type-k = q8_0
cache-type-v = q8_0

# sinh Program, diễn đạt câu trả lời
[qwen3-vl-4b-text]
model = /models/llm/Qwen3VL-4B-Instruct-Q4_K_M.gguf
load-on-startup = false

# Tiebreak, câu hỏi thuộc tính, caption
[qwen3-vl-4b-vision]
model = /models/llm/Qwen3VL-4B-Instruct-Q4_K_M.gguf
mmproj = /models/llm/mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf
load-on-startup = false
```

- `--models-max 1` phải đặt trên dòng lệnh; đặt trong INI không có tác dụng. `--no-models-autoload` chặn một request lạc tự nạp lại model khi worker đang giữ GPU. `--sleep-idle-seconds 600` là lưới an toàn tự gỡ model khi rảnh.
- KV cache lượng tử hoá cần flash attention. Giới hạn tối đa 2 ảnh mỗi lần phân xử, cạnh dài tối đa 768 px, để kiểm soát số token ảnh.
- Dùng image CUDA 12 (`server-cuda-b<build>`), không dùng image CUDA 13 vì có nhiều báo lỗi không nhận GPU. Ghim build và giữ một bộ 30 câu hỏi mẫu để kiểm tra JSON mỗi khi nâng phiên bản, vì structured output từng hỏng giữa các bản.
- JSON schema giữ phẳng: schema lồng sâu có thể làm sập server (lỗi bảo mật đã công bố).
- Phương án dự phòng nếu router mode không hợp: đưa binary `llama-server` vào image `api` (nền CUDA runtime) và `api` bật/tắt nó như một tiến trình con.

**Ngân sách VRAM của `llm`** (ước tính, chưa đo):

| Thành phần | Preset `text` | Preset `vision` |
| --- | --- | --- |
| Trọng số Q4\_K\_M | 2,5 GB | 2,5 GB |
| mmproj Q8\_0 | — | 0,45 GB |
| KV cache 4k token, q8\_0 | \~0,3 GB | \~0,3 GB |
| Buffer tính toán + token ảnh (tối đa 2 ảnh) | \~0,5 GB | \~0,6–1 GB |
| **Tổng** | **\~3,3 GB**, vừa \~3,8 GB trống | **\~3,9–4,3 GB**, cần đóng bớt app hoặc bỏ Tiebreak |

**Giao thức khoá GPU**

1. Worker lấy khoá.
2. Nếu `llm` đang nạp model: gọi `POST /models/unload` với preset đang nạp (`{"model": "qwen3-vl-4b-text"}` hoặc `-vision`), hỏi `GET /models` đến khi báo đã gỡ, rồi đọc VRAM trống bằng NVML cho đến khi đạt ngưỡng của stage. Không tin riêng vào HTTP 200.
3. Chạy stage trong tiến trình con hoặc gọi `mask3d`, chờ thoát, ghi thời gian và VRAM đỉnh vào `stage_runs`.
4. Nhả khoá. Câu hỏi cần LLM lấy khoá, gọi `POST /models/load` cho preset cần dùng nếu chưa nạp (đổi preset thì gỡ preset kia trước), rồi gọi `/v1/chat/completions`. Câu do router luật và solver trả lời được thì không cần khoá.
5. Gặp CUDA OOM: giảm batch → giảm độ phân giải ảnh → voxel thô hơn cho Mask3D; ghi lại trong `stage_runs`.

**Cài đặt và chạy**

```bash
# hệ thống, một lần
docker compose build                        # mask3d lâu nhất vì biên dịch MinkowskiEngine
docker save s3d-mask3d:1 -o D:/s3d/images/s3d-mask3d.tar
docker compose run --rm api s3d models pull  # tải model theo models.lock vào volume s3d-models
docker compose up -d
# mở http://localhost:8000

# tiền xử lý, chạy riêng bất cứ lúc nào (mục 3)
uv run tools/scannet_prep.py batch dataset/scans --list scenes.txt --out dataset/preprocessing
# rồi chọn/kéo thả file v2 từ dataset/preprocessing để upload
```

Khi phát triển: chạy web bằng `npm run dev` và `api` bằng `uv run s3d serve` ngoài Docker; chỉ khi biến `S3D_DEV=1` được đặt, `api` mới bật CORS cho cổng dev của Next.js. `mask3d` và `llm` vẫn chạy trong Docker; `compose.dev.yaml` mở cổng của chúng trên `127.0.0.1` và bind thư mục dữ liệu local vào `mask3d`.

**Ước tính thời gian nạp một scene trên RTX 3050** (chưa đo):

- Mốc công bố trên máy mạnh hơn nhiều: Open-YOLO 3D 21,8 giây/scene và Mask3D 13,4 giây/scene trên A100; riêng phần nhãn 2D của Open-YOLO 3D là 24,6 giây/scene trên TITAN V.
- Cộng thêm thời gian nạp/gỡ model và khởi tạo tiến trình con giữa các stage.
- Nên chuẩn bị cho **khoảng 3–6 phút/scene**; giao diện hiện tiến độ từng stage qua SSE. Bảng `stage_runs` ghi số đo thực để thay ước tính này.

## 11. Lộ trình, rủi ro và nguồn

**Lộ trình** (không gắn ngày; thứ tự và phụ thuộc chi tiết nằm trong các ticket ở `.scratch/s3d-v3/issues/`)

| Giai đoạn | Việc | Điều kiện xong |
| --- | --- | --- |
| 0 | Bảy việc kiểm chứng bên dưới (spike Mask3D, spike `llm`); khung web + API chạy được end-to-end | Có số đo thật; chốt Mask3D hay nhánh 2D-only |
| 1 | `scannet_prep.py` (độc lập), Package v2 đã căn chỉnh, upload, `POST /v1/imports`, job và tiến độ, `mesh.bin` và viewer | Import scene0000_00 và scene0000_01 qua web, `verify` đúng, xem được mesh |
| 2 | S2–S4 trong tiến trình con (visibility, instance, YOLOE-26, MobileCLIP2, màu HSV); viewer tô sáng vật; Lookup | Click vật thấy nhãn; Lookup chạy được |
| 3 | Scene graph + solver + vị từ `COLOR` và Viewpoint, chưa dùng LLM | Trả lời đúng các Program viết tay trên hai scene |
| 4 | LLM sinh Program + Pydantic + chuẩn hoá danh từ; câu trả lời SSE; Session và Clarify; Tiebreak; câu hỏi thuộc tính và câu hỏi mở | Hỏi đáp nhiều lượt đầy đủ trên web |
| 5 | Hoàn thiện: quản lý scene, xử lý lỗi, công tắc LLM cloud, sao lưu volume; dựng lại từ đầu bằng Compose | Máy mới chỉ cần Docker, driver và lệnh `s3d models pull` là chạy được |

Làm solver và vị từ trước VLM có chủ đích: nếu LLM 4B không đủ tốt, hệ thống vẫn trả lời được các câu do router luật và solver xử lý.

**Bảy việc kiểm chứng trong giai đoạn 0**

1. **VRAM Mask3D:** chạy scene0000_00 và scene0000_01 (\~81k đỉnh mỗi scan); đo bằng `torch.cuda.max_memory_allocated()` và `nvidia-smi`; xác định ngưỡng số điểm cần voxel hoá. Chưa nguồn nào công bố số này. Đạt khi image có CUDA, VRAM đỉnh ≤ 3,5 GB với voxel ≤ 3 cm và mask hợp lý; quá 2 ngày công mà chưa đạt thì chuyển sang nhánh 2D-only.
2. **VRAM `llm` thực:** cả hai preset `text` và `vision` (KV 4k q8\_0, 2 ảnh ≤ 768 px); ghi VRAM trống ban đầu khi Windows đang chạy.
3. **Gỡ model thật sự trả VRAM:** gọi `/models/unload`, hỏi `GET /models`, xác nhận bằng `nvidia-smi` trước khi chạy `mask3d`.
4. **Test JSON:** 30 câu hỏi mẫu tiếng Anh, một phần kèm ảnh, qua `response_format` trên build đã ghim; đếm tỉ lệ JSON hợp lệ.
5. **Build `mask3d` từ đầu** trong Docker Desktop với `FORCE_CUDA=1`; kiểm tra MinkowskiEngine báo hỗ trợ CUDA trong container đang chạy; `docker save` bản dự phòng.
6. **Thời gian nạp một scene** từ đầu đến cuối và từng stage.
7. **Scene thiếu `axisAlignment`** đi qua toàn pipeline (dùng bản sao scene0000_00 đã xoá dòng `axisAlignment`).

**Rủi ro chính**

| Rủi ro | Mức | Dấu hiệu | Phương án |
| --- | --- | --- | --- |
| Mask3D không vừa 6 GB VRAM | Cao | OOM ở scene lớn | fp16, voxel thô hơn, cắt scene thành khối; thử SGIFormer (spconv, 28,9 mAP ScanNet200); cuối cùng dùng nhánh 2D-only |
| Tag image CUDA 11.3.1 bị NVIDIA xoá | Trung bình | Pull lỗi khi dựng lại | Ghim digest; `docker save` image đã build; phương án B CUDA 12.1 có vá |
| MinkowskiEngine build ra bản chỉ CPU hoặc lỗi | Trung bình | `ME.print_diagnostics()` không thấy CUDA | `FORCE_CUDA=1`, `TORCH_CUDA_ARCH_LIST=8.6`, `MAX_JOBS=2`; ghim commit theo Mask3D |
| CUDA context còn giữ VRAM sau stage | Cao nếu bỏ qua | VRAM không về mức ban đầu, `llm` OOM | Mọi stage GPU chạy trong tiến trình con; khoá GPU kiểm VRAM trống bằng NVML |
| `llm` sát trần VRAM | Cao | OOM khi nạp preset `vision` | Hai preset `text`/`vision`, KV q8\_0, ngữ cảnh 4k, tối đa 2 ảnh ≤ 768 px; thiếu VRAM thì bỏ Tiebreak; dự phòng Qwen3-VL-2B cho vision |
| App Windows chiếm VRAM | Cao | NVML báo thiếu VRAM trước một stage | Ngân sách \~3,8 GB (ADR 0002); khoá GPU báo người dùng đóng bớt app; có thể chuyển màn hình sang iGPU |
| JSON sai dù có grammar | Trung bình | Pydantic báo lỗi; cột `json_retry` tăng | Validate + thử lại; ghim build; test 30 câu mỗi khi nâng cấp |
| Router mode của llama.cpp không gỡ model hoặc đổi API | Trung bình | `GET /models` vẫn báo loaded, VRAM không giảm | Chờ xác nhận bằng NVML; dự phòng đưa `llama-server` vào image `api` làm tiến trình con |
| LLM 4B sinh chương trình sai về ngữ nghĩa | Cao | Solver thường ra 0 lời giải (xem bảng `queries`) | Enum + few-shot, chuẩn hoá danh từ, mở rộng router luật; thử Qwen3.5-4B; chuyển LLM cloud qua `llm.base_url` |
| Nạp scene lâu | Trung bình | Quá 6 phút/scene | Giảm keyframe và độ phân giải ảnh; cache kết quả mỗi stage |
| Nhãn YOLOE lệch với tên vật người dùng hỏi | Trung bình | Tìm theo tên không ra vật nhìn thấy rõ | Top-3 nhãn thay thế, chuẩn hoá danh từ bằng MobileCLIP |
| Vi phạm điều khoản ScanNet | Thấp | Dữ liệu bị chia sẻ | Chạy local, cổng chỉ mở trên `127.0.0.1`, không public dữ liệu hay gói `.s3dpkg` |

**Giấy phép cần lưu ý**

- YOLOE (Ultralytics): AGPL-3.0. Ultralytics cho phép dùng trong nghiên cứu học thuật; điều kiện là công bố toàn bộ mã nguồn hệ thống theo AGPL-3.0. Nêu rõ điều này trong khoá luận; thương mại hoá sau này cần giấy phép doanh nghiệp.
- MobileCLIP2: giấy phép riêng của Apple cho mã và trọng số; kiểm tra điều khoản trước khi dùng ngoài nghiên cứu.
- Mask3D: kiểm tra file LICENSE trong repo và điều khoản của checkpoint ScanNet200.
- Qwen3-VL: Apache-2.0. llama.cpp: MIT.
- ScanNet: Terms of Use; chỉ dùng cho nghiên cứu phi thương mại.

**Nguồn**

- [Open-YOLO 3D (arXiv 2406.02548)](https://arxiv.org/html/2406.02548v3) · [mã nguồn](https://github.com/aminebdj/OpenYOLO3D)
- [CSVG (arXiv 2411.14594)](https://arxiv.org/html/2411.14594v2)
- [Mask3D](https://github.com/JonasSchult/Mask3D) · [SGIFormer](https://github.com/RayYoh/SGIFormer)
- [Qwen3-VL-4B-Instruct-GGUF](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct-GGUF/tree/main)
- [YOLOE / YOLOE-26 (Ultralytics)](https://docs.ultralytics.com/models/yoloe) · [Giấy phép Ultralytics](https://www.ultralytics.com/license)
- [MobileCLIP2 (Apple)](https://github.com/apple-aiml-research/ml-mobileclip)
- [llama.cpp: README của llama-server](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md) · [Model management trong llama.cpp](https://huggingface.co/blog/ggml-org/model-management-in-llamacpp) · [Docker image](https://github.com/ggml-org/llama.cpp/blob/master/docs/docker.md)
- llama.cpp issue: [grammar bị bỏ qua khi bật thinking #20345](https://github.com/ggml-org/llama.cpp/issues/20345) · [grammar lỗi vẫn trả 200 OK #19051](https://github.com/ggml-org/llama.cpp/issues/19051) · [structured output hỏng giữa các bản #20459](https://github.com/ggml-org/llama.cpp/discussions/20459) · [image CUDA 13 không nhận GPU #22561](https://github.com/ggml-org/llama.cpp/issues/22561)
- [NVIDIA: danh sách tag CUDA không còn hỗ trợ](https://gitlab.com/nvidia/container-images/cuda/blob/master/doc/unsupported-tags.md) · [MinkowskiEngine #135 (GPU khi docker build)](https://github.com/NVIDIA/MinkowskiEngine/issues/135) · [#601 (vá CUDA 12)](https://github.com/NVIDIA/MinkowskiEngine/issues/601)
- [PyTorch #17157: empty\_cache không trả CUDA context](https://github.com/pytorch/pytorch/issues/17157)
- [uv trong Docker](https://docs.astral.sh/uv/guides/integration/docker/) · [Docker Desktop: GPU](https://docs.docker.com/desktop/features/gpu/) · [Docker Compose: GPU](https://docs.docker.com/compose/how-tos/gpu-support/)
- [Next.js: static exports](https://nextjs.org/docs/app/guides/static-exports) · [React Three Fiber](https://r3f.docs.pmnd.rs/) · [gltf-transform: Draco và thứ tự đỉnh](https://gltf-transform.dev/modules/extensions/classes/KHRDracoMeshCompression)
- [sqlite-vec (pre-v1)](https://pypi.org/project/sqlite-vec/)
- [SceneGraphGrounder (arXiv 2605.21788)](https://arxiv.org/abs/2605.21788)
- SeeGround (CVPR 2025)
- [Sparse3DPR (arXiv 2511.07813)](https://arxiv.org/abs/2511.07813)
- [ReLaGS (arXiv 2603.17605)](https://arxiv.org/abs/2603.17605)
- [Any3DIS (arXiv 2411.16183)](https://arxiv.org/abs/2411.16183)

Phiên bản trước: [Kiến trúc v1](https://claude.ai/code/artifact/74daed7c-68a7-4b47-8ed8-e1036f44f263) (dùng cả 8 paper) · [Kiến trúc v2](https://claude.ai/code/artifact/a5b1f3b7-63ab-4b9f-928a-a9f043724f4f) (tối ưu, có scannet-prep và đánh giá OpenFunGraph).
