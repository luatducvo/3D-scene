# Chỉ hỗ trợ câu hỏi và giao diện tiếng Anh

Encoder text của MobileCLIP2 chỉ được huấn luyện trên tiếng Anh, nên Lookup và bước chuẩn hoá danh từ sẽ cho kết quả gần như ngẫu nhiên với câu tiếng Việt. Ta giới hạn câu hỏi và giao diện web ở tiếng Anh: few-shot của Program, nhãn, tên màu và câu trả lời đều tiếng Anh; tài liệu và ticket của dự án vẫn viết tiếng Việt.

## Considered Options

- Từ điển alias Việt–Anh cho 200 lớp ScanNet200 kèm LLM dịch dự phòng: bị loại để giữ phạm vi nhỏ; có thể thêm sau mà không đổi kiến trúc.
- Encoder text đa ngôn ngữ: lệch không gian embedding với ảnh MobileCLIP2, phải huấn luyện ánh xạ.
