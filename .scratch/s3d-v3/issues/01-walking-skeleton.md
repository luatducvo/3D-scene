# 01: Walking skeleton

**What to build:** Người dùng chạy một lệnh, mở trình duyệt và thấy trang web (tiếng Anh) của hệ thống báo API đang sống. Đây là khung để mọi ticket sau cắm vào: backend Python 3.12 với package `s3d_app` và CLI `s3d`, frontend Next.js static export do chính FastAPI phục vụ, kiểu TypeScript sinh từ OpenAPI, test và CI. Xem ADR 0001, 0003, 0006 và `docs/implement_plan.md` mục 7, 8.

**Blocked by:** None (can start immediately)

**Status:** complete

- [x] `s3d serve` chạy native trên Windows bằng uv, phục vụ web tĩnh ở `/` và `GET /v1/health`, chỉ bind `127.0.0.1`.
- [x] Trang chủ gọi `/v1/health` bằng đường dẫn tương đối và hiện trạng thái.
- [x] Package Python đổi từ `backend` thành `s3d_app`, Python 3.12; `uv.lock` resolve cho cả Windows và Linux x86_64.
- [x] Frontend Next.js (App Router, TypeScript, Tailwind CSS, shadcn/ui) với `output: 'export'`; bản build được FastAPI phục vụ.
- [x] Kiểu TypeScript sinh từ `/openapi.json` bằng `openapi-typescript`; đổi API mà không sinh lại kiểu thì build web báo lỗi.
- [x] `S3D_DEV=1` bật CORS cho cổng dev của Next.js; không đặt biến thì không có CORS.
- [x] pytest, vitest, ruff chạy được; GitHub Actions chạy test CPU, ruff và build web, và đang xanh.

**Verification:** See [implementation evidence](../../../docs/verification.md) and [review](../../../docs/code-review.md).
