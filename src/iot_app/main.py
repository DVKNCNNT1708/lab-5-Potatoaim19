import os
import uuid
import asyncio
import httpx
from enum import Enum
from datetime import datetime, timezone
from typing import List, Optional, Dict
from fastapi import FastAPI, BackgroundTasks, HTTPException, status, Header, Depends
from pydantic import BaseModel

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

# In-memory storage
DETECTIONS_DB: Dict[str, dict] = {}

class AnalysisType(str, Enum):
    PERSON_DETECTION = "PERSON_DETECTION"
    VEHICLE_DETECTION = "VEHICLE_DETECTION"
    UNKNOWN = "UNKNOWN"

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
    analysisType: AnalysisType

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
            await client.post(
                f"{AI_SERVICE_URL}/detect",
                json=payload.model_dump(),
                timeout=5.0
            )
            if detection_id in DETECTIONS_DB:
                DETECTIONS_DB[detection_id]["status"] = "PROCESSING"
    except Exception:
        if detection_id in DETECTIONS_DB:
            DETECTIONS_DB[detection_id]["status"] = "FAILED"

@app.post("/detect", status_code=status.HTTP_202_ACCEPTED, response_model=DetectionResponse, dependencies=[Depends(verify_token)])
async def create_detection(payload: DetectRequest, background_tasks: BackgroundTasks):
    detection_id = str(uuid.uuid4())
    DETECTIONS_DB[detection_id] = {
        "detectionId": detection_id,
        "status": "ACCEPTED",
        "timestamp": payload.timestamp,
        "cameraId": payload.cameraId
    }
    background_tasks.add_task(trigger_ai_analysis, detection_id, payload)
    return {"detectionId": detection_id, "status": "PROCESSING"}

@app.post("/webhook/detection-completed", status_code=status.HTTP_200_OK)
async def receive_detection_result(payload: DetectionWebhookPayload):
    if payload.detectionId in DETECTIONS_DB:
        DETECTIONS_DB[payload.detectionId].update(payload.model_dump())
    return {"message": "Webhook received"}

@app.get("/detections", dependencies=[Depends(verify_token)])
def list_detections(limit: int = 20):
    return {"items": list(DETECTIONS_DB.values())[:limit], "nextCursor": None, "hasMore": False}

@app.get("/detections/recent", dependencies=[Depends(verify_token)])
def get_recent():
    return list(DETECTIONS_DB.values())[-5:]

@app.get("/detections/{detection_id}", dependencies=[Depends(verify_token)])
def get_detection(detection_id: str):
    if detection_id not in DETECTIONS_DB:
        raise HTTPException(status_code=404, detail="Detection not found")
    return DETECTIONS_DB[detection_id]
