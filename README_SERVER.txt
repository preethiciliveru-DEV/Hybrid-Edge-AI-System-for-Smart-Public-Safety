Local detection server + ESP32 buzzer integration

Files:
- main_server.py : main detection loop using ultralytics (YOLOv8 .pt weights)
- requirements.txt : Python dependencies
- esp_buzzer.ino : ESP32 Arduino sketch (simple HTTP server to trigger buzzer)

Quick start:
1. On the Roboflow side, train RF-DETR and export YOLOv8 weights (best.pt) or download a YOLO-compatible .pt file.
2. Copy the best.pt file to this folder or set --model path when running main_server.py
3. Install dependencies: python -m venv venv && venv\Scripts\activate && pip install -r requirements.txt
4. Configure ESP32 IP and AUTH token either by editing the constants in main_server.py or passing --esp and --token arguments.
5. Run: python main_server.py

Tune constants in main_server.py: CONF_THRESH, CONSEC_FRAMES, WINDOW, BBOX_AREA_MIN, COOLDOWN

Security note: The ESP32 HTTP token is simple; restrict to a trusted LAN. For production, use MQTT with auth and TLS or use a VPN.
