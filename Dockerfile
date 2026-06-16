# syntax=docker/dockerfile:1.7
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /build

RUN python -m venv /opt/venv
COPY requirements.txt .
RUN /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

FROM python:3.11-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/opt/venv/bin:$PATH"

# Cài đặt thư viện OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN addgroup --system appgroup && adduser --system --ingroup appgroup --home /app appuser

COPY --from=builder /opt/venv /opt/venv
COPY src/ ./src/
RUN chown -R appuser:appgroup /app
USER appuser

# Cổng sẽ được ghi đè bởi docker-compose hoặc biến môi trường
EXPOSE 8000

# Lệnh chạy mặc định (cho A2), A4 sẽ được ghi đè command trong docker-compose
CMD ["sh", "-c", "uvicorn iot_app.main:app --app-dir src --host 0.0.0.0 --port ${APP_PORT:-8000}"]
