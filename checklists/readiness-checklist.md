# Readiness Checklist - Team A2 & A4 (Smart Campus Integration)

Tài liệu này đánh giá mức độ sẵn sàng của stack trước khi thực hiện Pull Request vào repo của Leader.

## 1. Sẵn sàng Cơ sở dữ liệu (Database Readiness)
- [x] Container `camera-db` đã khởi động thành công.
- [x] Lệnh `pg_isready` trả về trạng thái sẵn sàng.
- [x] Volume `db-data` được gắn đúng để lưu trữ dữ liệu bền vững.

## 2. Sẵn sàng AI Vision Provider (AI Readiness - A4)
- [x] Container `ai-vision-provider` lắng nghe trên port **8004**.
- [x] Endpoint `GET /health` của AI service trả về 200 OK.
- [x] Đã cấu hình `WEBHOOK_URL` trỏ về port **8002** của Camera API.

## 3. Xác thực & Bảo mật (Token & Auth)
- [x] Biến môi trường `AUTH_TOKEN` được thiết lập đồng nhất.
- [x] Header `Authorization: Bearer <token>` hoạt động đúng cho các endpoint.
- [x] Đã kiểm tra và loại bỏ secret khỏi git (chỉ dùng `.env.example`).

## 4. Cấu hình Port & Network (Ma trận kết nối)
- [x] **A2: Camera Stream** chạy trên port **8002**.
- [x] **A4: AI Vision** chạy trên port **8004**.
- [x] Cấu hình `class-net` (external) để Leader có thể gọi vào.
- [x] Giao tiếp nội bộ sử dụng container name (`camera-stream-api`, `ai-vision-provider`).

## 5. Luồng nghiệp vụ & Payload
- [x] Payload giữa A2 và A4 sử dụng `camelCase` (cameraId, requestId...) khớp với OpenAPI Contract.
- [x] `POST /detect` trả về `202 Accepted`.
- [x] Webhook callback trả về kết quả `COMPLETED` sau 2 giây.

## 6. Kiểm thử & Bằng chứng (Evidence)
- [x] Đã cập nhật `RUN_COMPOSE.md` hướng dẫn Leader cách chạy.
- [x] Chạy thành công Newman test trên môi trường Docker Compose.
- [x] Đã sinh báo cáo trong thư mục `reports/`.
