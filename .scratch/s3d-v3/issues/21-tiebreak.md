# 21: Tiebreak bằng model thị giác

**What to build:** Khi còn nhiều Solution và câu hỏi có từ chỉ ngoại hình, hệ thống áp `COLOR` trước; nếu vẫn còn nhiều thì cho model thị giác chọn: tối đa 2 Keyframe thật, mỗi Candidate được vẽ viền màu và đánh số, model trả về một số. Không đủ VRAM cho preset `vision` thì bỏ Tiebreak và Clarify. Xem `docs/implement_plan.md` mục 6 (bước 7) và ADR 0004.

**Blocked by:** 20

**Status:** ready-for-agent

- [ ] Chọn các Keyframe thấy rõ nhiều Candidate nhất; vẽ viền và số lên ảnh; cạnh dài tối đa 768 px; tối đa 2 ảnh.
- [ ] Lấy khoá GPU, gỡ preset `text`, nạp preset `vision`; NVML không đạt ngưỡng thì bỏ qua và chuyển sang Clarify (test với NVML giả).
- [ ] Câu trả lời của model phải là số của một Candidate; không hợp lệ thì Clarify.
- [ ] SSE phát sự kiện `tiebreak`; `evidence.tiebreak` là true; `used_tiebreak` được ghi vào `queries`.
- [ ] Câu có từ chỉ màu được giải bằng `COLOR` trước khi tính tới Tiebreak.
