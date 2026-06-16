import os
import uuid
import asyncio
import httpx
import cv2
import numpy as np
import threading
import time
from datetime import datetime, timezone
from typing import List, Optional, Dict
from fastapi import FastAPI, BackgroundTasks, HTTPException, status, Header, Depends
from pydantic import BaseModel

# --- Configuration ---
SERVICE_NAME = os.getenv("SERVICE_NAME", "camera-stream-service")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "1.0.0")
AUTH_TOKEN = os.getenv("AUTH_TOKEN", "lab-token")
# Đảm bảo gọi đến port 8004 của AI service
AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "http://ai-vision-provider:8004")
STREAM_URL = os.getenv("CAMERA_STREAM_URL", "https://camera.labaiotdnu.app/video?key=demo")
CAMERA_ID = os.getenv("CAMERA_ID", "CAM-GATE-A")
LOCATION = os.getenv("LOCATION", "Main Gate A")
MOTION_THRESHOLD = float(os.getenv("MOTION_THRESHOLD", "500.0"))
AI_COOLDOWN = int(os.getenv("AI_COOLDOWN", "5"))
SNAPSHOT_DIR = "/app/snapshots"

app = FastAPI(title="Camera Stream Service (Team A2)")

# Đảm bảo thư mục lưu snapshot tồn tại
os.makedirs(os.path.join(SNAPSHOT_DIR, CAMERA_ID), exist_ok=True)

# --- In-memory Storage & State ---
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

# --- Stream Processing Logic ---
def process_camera_stream():
    global latest_frame, last_ai_trigger_time
    print(f"Connecting to MJPEG stream: {STREAM_URL}")
    cap = cv2.VideoCapture(STREAM_URL)

    ret, frame1 = cap.read()
    if not ret:
        print("Error: Cannot read initial frame from camera stream.")
        return

    gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
    gray1 = cv2.GaussianBlur(gray1, (21, 21), 0)

    while True:
        ret, frame2 = cap.read()
        if not ret:
            time.sleep(2)
            cap = cv2.VideoCapture(STREAM_URL)
            continue

        latest_frame = frame2.copy()
        gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.GaussianBlur(gray2, (21, 21), 0)

        frame_delta = cv2.absdiff(gray1, gray2)
        thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
        thresh = cv2.dilate(thresh, None, iterations=2)
        motion_score = np.sum(thresh) / 1000000.0

        current_time = time.time()
        if motion_score > (MOTION_THRESHOLD / 1000.0) and (current_time - last_ai_trigger_time) > AI_COOLDOWN:
            last_ai_trigger_time = current_time

            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp_str}.jpg"
            relative_path = os.path.join(CAMERA_ID, filename)
            full_path = os.path.join(SNAPSHOT_DIR, relative_path)

            resized = cv2.resize(frame2, (640, 480))
            cv2.imwrite(full_path, resized, [cv2.IMWRITE_JPEG_QUALITY, 85])

            # Chạy trigger AI (sync bridge to async)
            asyncio.run(trigger_ai_vision(relative_path, motion_score))

        gray1 = gray2

async def trigger_ai_vision(snapshot_path, score):
    detection_id = str(uuid.uuid4())

    # Payload khớp hoàn toàn với OpenAPI Contract (camelCase)
    payload = {
        "requestId": f"REQ-{uuid.uuid4().hex[:6].upper()}",
        "cameraId": CAMERA_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "frameUrl": f"file://{snapshot_path}",
        "analysisType": "PERSON_DETECTION"
    }

    DETECTIONS_DB[detection_id] = {
        "detectionId": detection_id,
        "status": "PROCESSING",
        "snapshot": snapshot_path,
        "motion_score": score,
        "created_at": payload["timestamp"]
    }

    try:
        async with httpx.AsyncClient() as client:
            await client.post(f"{AI_SERVICE_URL}/detect", json=payload, timeout=5.0)
    except Exception as e:
        print(f"Error calling AI Vision service at {AI_SERVICE_URL}: {e}")
        DETECTIONS_DB[detection_id]["status"] = "FAILED"

# Khởi chạy Worker
threading.Thread(target=process_camera_stream, daemon=True).start()

# --- API Endpoints ---
def verify_token(authorization: str = Header(None)):
    if not authorization or authorization != f"Bearer {AUTH_TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized")

@app.get("/health")
def health():
    return {
        "status": "ok" if latest_frame is not None else "warning",
        "camera_connected": latest_frame is not None,
        "service": SERVICE_NAME
    }

@app.post("/webhook/detection-completed")
async def receive_result(payload: DetectionWebhookPayload):
    # Tìm detection trong DB dựa trên ID trả về từ webhook
    if payload.detectionId in DETECTIONS_DB:
        DETECTIONS_DB[payload.detectionId].update(payload.model_dump())
        print(f"Result updated for {payload.detectionId}")
    return {"message": "ok"}

@app.get("/detections", dependencies=[Depends(verify_token)])
def list_detections(limit: int = 10):
    return {"items": list(DETECTIONS_DB.values())[-limit:]}
