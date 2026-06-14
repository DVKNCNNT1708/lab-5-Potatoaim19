# Hướng dẫn chạy Camera Stream Stack (Team A2)

Tài liệu này hướng dẫn khởi chạy hệ thống Camera Stream tích hợp AI Vision Provider theo đúng quy trình Lab 05.

## 1. Yêu cầu hệ thống
- Docker & Docker Compose v2
- Node.js & Newman (để chạy test)
- Đã tạo mạng external `class-net` (nếu chạy local):
  ```bash
  docker network create class-net
  ```

## 2. Khởi chạy Stack
Sử dụng Makefile để build và chạy toàn bộ dịch vụ:

```bash
# Tạo file môi trường từ mẫu
cp .env.example .env

# Khởi chạy stack (API, DB, AI)
make compose-up
```

## 3. Kiểm tra trạng thái sẵn sàng
Hệ thống sử dụng cơ chế Healthcheck của Docker. Bạn có thể kiểm tra qua:
- **API:** `http://localhost:8000/health`
- **AI Service:** `http://localhost:9000/health`
- **Database:** `docker exec -it camera-db pg_isready -U lab05`

## 4. Luồng kiểm thử Async (Quan trọng)
Hệ thống Camera Stream hoạt động theo mô hình Async Webhook:
1. **Gửi yêu cầu:** `POST /detect` -> Nhận `202 Accepted` và `detectionId`.
2. **Xử lý ngầm:** AI Vision Provider xử lý trong 2 giây.
3. **Webhook Callback:** AI Provider gọi lại `/webhook/detection-completed` để cập nhật kết quả.
4. **Kiểm tra kết quả:** `GET /detections/{id}` để xem thông tin `boundingBox` và `status: COMPLETED`.

## 5. Chạy Automated Tests
```bash
npm run test:compose
```
Kết quả báo cáo sẽ sinh ra tại thư mục `reports/`.
