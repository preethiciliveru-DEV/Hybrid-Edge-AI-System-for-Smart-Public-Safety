"""
Local detection server for PC camera + ESP32 buzzer integration.

- Uses an exported YOLOv8 model (best.pt) via ultralytics for inference.
- Applies post-processing to reduce false positives (confidence threshold, bbox area, consecutive-frame confirmation, cooldown).
- Sends a simple authenticated HTTP POST to the ESP32 to trigger the buzzer.

Usage:
1. Create a Python venv and install requirements: pip install -r requirements.txt
2. Place your exported model weights (YOLO .pt) at MODEL_PATH or set MODEL_PATH to your path.
3. Configure ESP32_IP and AUTH_TOKEN below.
4. Run: python main_server.py

"""

import time
import collections
import argparse
import requests
import cv2
import numpy as np

try:
    from ultralytics import YOLO
except Exception:
    YOLO = None

# --- Configuration (edit as needed) ---
MODEL_PATH = "best.pt"  # path to exported YOLOv8 weights
ESP32_BZZ_URL = "http://192.168.1.50/buzz"  # Change to your ESP32 IP
ESP32_AUTH_TOKEN = "your-secret-token"
CONF_THRESH = 0.75
CONSEC_FRAMES = 3
WINDOW = 5
BBOX_AREA_MIN = 0.02  # min bbox area ratio (fraction of image)
COOLDOWN = 10.0  # seconds between allowed triggers
CAMERA_INDEX = 0  # default PC camera
TARGET_LABELS = {"kitchen_knife", "scissors", "pistol", "rifle"}
# --------------------------------------

history = collections.deque(maxlen=WINDOW)
last_trigger = 0


def bbox_area_ratio(bbox, img_w, img_h):
    x1, y1, x2, y2 = bbox
    area = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    return area / (img_w * img_h)


def send_buzz(url, token, duration_ms=1000, timeout=1.0):
    payload = {"token": token, "duration_ms": int(duration_ms)}
    try:
        r = requests.post(url, json=payload, timeout=timeout)
        return r.status_code == 200
    except Exception as e:
        print("ESP32 request failed:", e)
        return False


def load_model(model_path):
    if YOLO is None:
        raise RuntimeError("ultralytics not installed. Install via pip install ultralytics")
    if not model_path:
        raise ValueError("MODEL_PATH is empty")
    print(f"Loading model from {model_path}...")
    model = YOLO(model_path)
    print("Model loaded. Classes:", model.names)
    return model


def run_loop(model, camera_index=0):
    global last_trigger
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        raise SystemExit("Could not open camera")
    print("Camera opened. Press Ctrl+C to stop.")
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                time.sleep(0.1)
                continue
            img_h, img_w = frame.shape[:2]
            # Inference -- ultralytics returns results
            results = model(frame)[0]
            detections = []
            # results.boxes contains xyxy, conf, cls
            boxes = getattr(results, 'boxes', None)
            if boxes is not None:
                for r in boxes:
                    conf = float(r.conf.cpu().numpy()) if hasattr(r, 'conf') else float(r.conf)
                    cls = int(r.cls.cpu().numpy()) if hasattr(r, 'cls') else int(r.cls)
                    label = model.names.get(cls, str(cls))
                    xyxy = r.xyxy.cpu().numpy() if hasattr(r, 'xyxy') else np.array(r.xyxy)
                    x1, y1, x2, y2 = map(float, xyxy[0])
                    if conf >= CONF_THRESH and bbox_area_ratio((x1, y1, x2, y2), img_w, img_h) >= BBOX_AREA_MIN:
                        if label in TARGET_LABELS:
                            detections.append((label, conf, (x1, y1, x2, y2)))
            history.append(detections)
            # Decide whether to trigger
            count = sum(1 for d in history if any(d))
            now = time.time()
            if count >= CONSEC_FRAMES and (now - last_trigger) >= COOLDOWN:
                # Optional: pick most common label in window
                labels = [d[0] for window in history for d in window]
                if labels:
                    from collections import Counter
                    most_common_label, freq = Counter(labels).most_common(1)[0]
                    print(f"Detected {most_common_label} repeatedly (count={count}), sending buzz...")
                    ok = send_buzz(ESP32_BZZ_URL, ESP32_AUTH_TOKEN, duration_ms=800)
                    if ok:
                        last_trigger = now
                        print("Buzz sent at", time.strftime('%X'))
                    else:
                        print("Failed to send buzz")
            # Small sleep
            time.sleep(0.03)
    except KeyboardInterrupt:
        print("Stopped by user")
    finally:
        cap.release()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', type=str, default=MODEL_PATH, help='Path to YOLO model (.pt)')
    parser.add_argument('--cam', type=int, default=CAMERA_INDEX, help='Camera index')
    parser.add_argument('--esp', type=str, default=ESP32_BZZ_URL, help='ESP32 /buzz endpoint')
    parser.add_argument('--token', type=str, default=ESP32_AUTH_TOKEN, help='ESP32 auth token')
    args = parser.parse_args()
    MODEL_PATH = args.model
    CAMERA_INDEX = args.cam
    ESP32_BZZ_URL = args.esp
    ESP32_AUTH_TOKEN = args.token

    model = load_model(MODEL_PATH)
    run_loop(model, CAMERA_INDEX)
