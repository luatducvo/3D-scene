# Hai preset text và vision trên cùng một model Qwen3-VL-4B

Với ~3,8 GB VRAM trống (ADR 0002), Qwen3-VL-4B Q4_K_M kèm mmproj và ngữ cảnh 4k ước tính cần 3,9–4,3 GB, còn bản không mmproj chỉ ~3,3 GB. Ta khai báo hai preset trong router mode của `llama-server` dùng chung một file GGUF: `text` (không mmproj) để sinh Program và diễn đạt câu trả lời, `vision` (có mmproj, tối đa 2 ảnh ≤ 768 px) chỉ cho Tiebreak và câu hỏi thuộc tính; `--models-max 1` nên mỗi lúc chỉ một preset nằm trên GPU. Khi NVML báo không đủ VRAM cho `vision`, hệ thống bỏ Tiebreak và chuyển thẳng sang Clarify.

## Considered Options

- Qwen3-VL-2B cho vai trò vision: giữ làm phương án dự phòng nếu spike đo thấy preset `vision` vẫn OOM.
- Một preset như kiến trúc v3: phụ thuộc người dùng đóng app mỗi lần, bị loại.
