# Hướng dẫn chạy Camera Stream Stack (Team A2 & A4)

Hệ thống này được cấu hình để tích hợp vào Smart Campus Platform.

## 1. Khởi chạy
```bash
# Tạo file .env
cp .env.example .env

# Chạy bằng Docker Compose
docker compose up -d --build
```

## 2. Kiểm tra Health (Theo yêu cầu Leader)
- **A2: Camera Stream:** `curl http://localhost:8002/health`
- **A4: AI Vision:** `curl http://localhost:8004/health`

## 3. Ma trận Kết nối đã cấu hình
- **Sync REST:** A2 (`:8002`) gọi A4 (`:8004`) tại endpoint `POST /detect`.
- **Async Webhook:** A4 gọi ngược lại A2 tại `POST /webhook/detection-completed`.
- **Database:** A2 lưu trữ lịch sử tại PostgreSQL port `5432`.

## 4. Kiểm thử
Sử dụng Newman để chạy test tự động:
```bash
npm run test:compose
```
