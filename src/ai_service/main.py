import uuid
import asyncio
import httpx
import os
from datetime import datetime, timezone
from typing import List, Optional, Dict
from fastapi import FastAPI, BackgroundTasks, HTTPException, status
from pydantic import BaseModel, Field

SERVICE_NAME = "ai-vision-service"
SERVICE_VERSION = "1.0.0"

# Webhook URL của Camera Stream API (trong Docker network, 'api' là hostname)
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "http://api:8000/webhook/detection-completed")

app = FastAPI(
    title="AI Vision Provider",
    version=SERVICE_VERSION,
    description="Mock AI provider that sends results via webhook (Lab 05).",
)

# Lưu trữ tạm thời (Mock DB)
DETECTIONS_DB: Dict[str, dict] = {}

class BoundingBox(BaseModel):
    x: int
    y: int
    width: int
    height: int

class DetectRequest(BaseModel):
    cameraId: str
    frameUrl: str
    timestamp: str
    requestId: str
    analysisType: str

class DetectionResponse(BaseModel):
    detectionId: str
    status: str

class DetectionResult(BaseModel):
    detectionId: str
    status: str
    detectionType: Optional[str] = None
    confidence: Optional[float] = None
    boundingBox: Optional[BoundingBox] = None
    trackingId: Optional[str] = None

@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": SERVICE_NAME, "version": SERVICE_VERSION}

async def process_and_send_webhook(detection_id: str, analysis_type: str):
    """
    Giả lập quá trình xử lý AI và gọi Webhook trả kết quả.
    """
    # 1. Mô phỏng thời gian xử lý (2 giây)
    await asyncio.sleep(2)

    # 2. Tạo kết quả giả lập
    detection_result = {
        "detectionId": detection_id,
        "status": "COMPLETED",
        "detectionType": "PERSON" if "PERSON" in analysis_type else "VEHICLE",
        "confidence": 0.98,
        "boundingBox": {"x": 150, "y": 100, "width": 200, "height": 300},
        "trackingId": f"TRK-{uuid.uuid4().hex[:6].upper()}"
    }

    # Cập nhật DB nội bộ
    if detection_id in DETECTIONS_DB:
        DETECTIONS_DB[detection_id].update(detection_result)

    # 3. Gửi Webhook callback về Camera Stream API
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(WEBHOOK_URL, json=detection_result, timeout=5.0)
            print(f"Webhook sent for {detection_id}, status: {response.status_code}")
    except Exception as e:
        print(f"Failed to send webhook for {detection_id}: {e}")

@app.post("/detect", status_code=status.HTTP_202_ACCEPTED, response_model=DetectionResponse)
async def detect(payload: DetectRequest, background_tasks: BackgroundTasks):
    detection_id = str(uuid.uuid4())

    DETECTIONS_DB[detection_id] = {
        "detectionId": detection_id,
        "status": "PROCESSING",
        "cameraId": payload.cameraId,
        "analysisType": payload.analysisType,
        "timestamp": payload.timestamp
    }

    # Chạy xử lý ngầm và callback
    background_tasks.add_task(process_and_send_webhook, detection_id, payload.analysisType)

    return {"detectionId": detection_id, "status": "PROCESSING"}

@app.get("/detections")
def list_detections(cursor: Optional[str] = None, limit: int = 20):
    items = list(DETECTIONS_DB.values())
    return {
        "items": items[:limit],
        "nextCursor": None,
        "hasMore": False
    }

@app.get("/detections/{detection_id}", response_model=DetectionResult)
def get_detection(detection_id: str):
    if detection_id not in DETECTIONS_DB:
        raise HTTPException(status_code=404, detail="Detection not found")
    return DETECTIONS_DB[detection_id]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)
