import os
import uuid
import asyncio
import httpx
import cv2
import numpy as np
import threading
import time
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict
from fastapi import FastAPI, BackgroundTasks, HTTPException, status, Header, Depends, Query
from pydantic import BaseModel

# --- Configuration ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CameraStreamService")

SERVICE_NAME = os.getenv("SERVICE_NAME", "camera-stream-service")
SERVICE_VERSION = "0.1.0"
AUTH_TOKEN = os.getenv("AUTH_TOKEN", "lab-token")
AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "http://ai-vision-provider:9000")
STREAM_URL = os.getenv("CAMERA_STREAM_URL", "https://camera.labaiotdnu.app/video?key=demo")
CAMERA_ID = os.getenv("CAMERA_ID", "CAM-01")
LOCATION = os.getenv("LOCATION", "Main Gate A")
MOTION_THRESHOLD = float(os.getenv("MOTION_THRESHOLD", "500.0"))
AI_COOLDOWN = int(os.getenv("AI_COOLDOWN", "5"))
SNAPSHOT_DIR = "/app/snapshots"

app = FastAPI(title="Camera Stream API (Team A2)")
os.makedirs(os.path.join(SNAPSHOT_DIR, CAMERA_ID), exist_ok=True)

# --- Internal DB ---
DETECTIONS_DB: Dict[str, dict] = {}
latest_frame = None
last_ai_trigger_time = 0

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
    frameUrl: Optional[str] = None
    timestamp: str
    requestId: str
    analysisType: str

# --- Camera Processing Thread ---
def camera_worker():
    global latest_frame, last_ai_trigger_time
    cap = cv2.VideoCapture(STREAM_URL)
    ret, frame1 = cap.read()
    if not ret: return
    gray1 = cv2.GaussianBlur(cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY), (21, 21), 0)

    while True:
        ret, frame2 = cap.read()
        if not ret:
            time.sleep(2); cap = cv2.VideoCapture(STREAM_URL); continue
        latest_frame = frame2.copy()
        gray2 = cv2.GaussianBlur(cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY), (21, 21), 0)
        delta = cv2.absdiff(gray1, gray2)
        score = np.sum(cv2.threshold(delta, 25, 255, cv2.THRESH_BINARY)[1]) / 1000000.0

        curr_time = time.time()
        if score > (MOTION_THRESHOLD/1000.0) and (curr_time - last_ai_trigger_time) > AI_COOLDOWN:
            last_ai_trigger_time = curr_time
            rel_path = os.path.join(CAMERA_ID, f"{datetime.now().strftime('%H%M%S')}.jpg")
            cv2.imwrite(os.path.join(SNAPSHOT_DIR, rel_path), cv2.resize(frame2, (640, 480)))
            # Trigger AI
            det_id = str(uuid.uuid4())
            DETECTIONS_DB[det_id] = {"detectionId": det_id, "status": "PROCESSING", "snapshot": rel_path}
            asyncio.run(call_ai(det_id, rel_path))
        gray1 = gray2

async def call_ai(det_id, path):
    payload = {
        "cameraId": CAMERA_ID,
        "frameUrl": f"http://team-camera/snapshots/{path}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "requestId": f"REQ-{det_id[:6].upper()}",
        "analysisType": "PERSON_DETECTION"
    }
    try:
        async with httpx.AsyncClient() as client:
            await client.post(f"{AI_SERVICE_URL}/detect", json=payload, timeout=5.0)
    except: DETECTIONS_DB[det_id]["status"] = "FAILED"

threading.Thread(target=camera_worker, daemon=True).start()

# --- API ---
def verify_token(authorization: str = Header(None)):
    if not authorization or authorization != f"Bearer {AUTH_TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized")

@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE_NAME, "version": SERVICE_VERSION}

@app.post("/detect", status_code=202)
async def manual_detect(payload: DetectRequest, background_tasks: BackgroundTasks, auth=Depends(verify_token)):
    det_id = str(uuid.uuid4())
    DETECTIONS_DB[det_id] = {"detectionId": det_id, "status": "PROCESSING"}
    background_tasks.add_task(httpx.AsyncClient().post, f"{AI_SERVICE_URL}/detect", json=payload.model_dump())
    return {"detectionId": det_id, "status": "PROCESSING"}

@app.post("/webhook/detection-completed")
async def webhook(payload: DetectionWebhookPayload):
    if payload.detectionId in DETECTIONS_DB:
        DETECTIONS_DB[payload.detectionId].update(payload.model_dump())
    return {"status": "ok"}

@app.get("/detections", dependencies=[Depends(verify_token)])
def list_detections(cursor: Optional[str] = Query(None), limit: int = 20):
    all_items = list(DETECTIONS_DB.values())
    start = int(cursor) if cursor and cursor.isdigit() else 0
    end = start + limit
    return {
        "items": all_items[start:end],
        "nextCursor": str(end) if end < len(all_items) else None,
        "hasMore": end < len(all_items)
    }

@app.get("/detections/recent", dependencies=[Depends(verify_token)])
def get_recent():
    return list(DETECTIONS_DB.values())[-5:]

@app.get("/detections/{detectionId}", dependencies=[Depends(verify_token)])
def get_by_id(detectionId: str):
    if detectionId not in DETECTIONS_DB: raise HTTPException(status_code=404)
    return DETECTIONS_DB[detectionId]
