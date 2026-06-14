import os
import uuid
import asyncio
import httpx
from datetime import datetime, timezone
from typing import List, Optional, Dict
from fastapi import FastAPI, BackgroundTasks, HTTPException, status, Header, Depends
from pydantic import BaseModel, Field

# Configuration
SERVICE_NAME = os.getenv("SERVICE_NAME", "camera-stream-service")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "1.0.0")
AUTH_TOKEN = os.getenv("AUTH_TOKEN", "lab-token")
AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "http://ai-service:9000")

app = FastAPI(
    title="Camera Stream API",
    version=SERVICE_VERSION,
    description="Service for camera frame analysis and tracking (Lab 05).",
)

# In-memory storage (Simulating DB)
DETECTIONS_DB: Dict[str, dict] = {}

class BoundingBox(BaseModel):
    x: int
    y: int
    width: int
    height: int

class DetectionWebhookPayload(BaseModel):
    detectionId: str
    status: str
    detectionType: Optional[str] = None
    confidence: Optional[float] = None
    boundingBox: Optional[BoundingBox] = None
    trackingId: Optional[str] = None

class DetectRequest(BaseModel):
    cameraId: str
    frameUrl: str
    timestamp: str
    requestId: str
    analysisType: str

class DetectionResponse(BaseModel):
    detectionId: str
    status: str

def verify_token(authorization: str = Header(None)):
    if not authorization or authorization != f"Bearer {AUTH_TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized")

@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE_NAME, "version": SERVICE_VERSION}

async def trigger_ai_analysis(detection_id: str, payload: DetectRequest):
    try:
        async with httpx.AsyncClient() as client:
            # Gọi AI Provider
            await client.post(
                f"{AI_SERVICE_URL}/detect",
                json=payload.model_dump(),
                timeout=5.0
            )
            # Sau khi AI nhận (202), trạng thái tại API là PROCESSING
            DETECTIONS_DB[detection_id]["status"] = "PROCESSING"
    except Exception:
        DETECTIONS_DB[detection_id]["status"] = "FAILED"

@app.post("/detect", status_code=status.HTTP_202_ACCEPTED, response_model=DetectionResponse, dependencies=[Depends(verify_token)])
async def create_detection(payload: DetectRequest, background_tasks: BackgroundTasks):
    detection_id = str(uuid.uuid4())
    DETECTIONS_DB[detection_id] = {
        "detectionId": detection_id,
        "status": "ACCEPTED",
        "timestamp": payload.timestamp
    }
    background_tasks.add_task(trigger_ai_analysis, detection_id, payload)
    return {"detectionId": detection_id, "status": "PROCESSING"}

# WEBHOOK ENDPOINT: AI Vision gọi lại đây
@app.post("/webhook/detection-completed", status_code=status.HTTP_200_OK)
async def receive_detection_result(payload: DetectionWebhookPayload):
    if payload.detectionId in DETECTIONS_DB:
        DETECTIONS_DB[payload.detectionId].update(payload.model_dump())
        print(f"Webhook received: Detection {payload.detectionId} is now {payload.status}")
    return {"message": "Webhook received"}

@app.get("/detections", dependencies=[Depends(verify_token)])
def list_detections(cursor: Optional[str] = None, limit: int = 20):
    return {"items": list(DETECTIONS_DB.values())[:limit], "nextCursor": None, "hasMore": False}

@app.get("/detections/recent", dependencies=[Depends(verify_token)])
def get_recent():
    return list(DETECTIONS_DB.values())[-5:]

@app.get("/detections/{detection_id}", dependencies=[Depends(verify_token)])
def get_detection(detection_id: str):
    if detection_id not in DETECTIONS_DB:
        raise HTTPException(status_code=404, detail="Detection not found")
    return DETECTIONS_DB[detection_id]
