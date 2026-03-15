"""Flask backend for GOONER ROV — two camera streams, motor commands via Feather, sensor data display."""

import time
import threading
import requests
import cv2
from flask import Flask, Response, jsonify, request, send_from_directory

# ---- CONFIGURE THESE ----
FEATHER_IP  = "http://172.20.10.6"  
CAMERA1_URL = "http://172.20.10.4/stream"  # First ESP32-CAM
CAMERA2_URL = "http://172.20.10.5/stream"  # Second ESP32-CAM
# -------------------------

app = Flask(__name__, static_folder="frontend", static_url_path="/static")

KEY_MAP = {"w": "F", "a": "L", "s": "B", "d": "R"}

# ---------- CAMERA STATE ----------
latest_frame1 = None
latest_frame2 = None
lock1 = threading.Lock()
lock2 = threading.Lock()

def capture_loop(url, lock, setter):
    print(f"Opening stream: {url}")
    cap = cv2.VideoCapture(url)
    if not cap.isOpened():
        print(f"Could not open: {url}")
        return
    print(f"Camera connected: {url}")
    while True:
        ret, frame = cap.read()
        if ret:
            with lock:
                setter(frame)

def set1(f):
    global latest_frame1
    latest_frame1 = f

def set2(f):
    global latest_frame2
    latest_frame2 = f

def generate_frames(getter, lock):
    while True:
        with lock:
            frame = getter()
        if frame is None:
            time.sleep(0.03)
            continue
        ret, jpeg = cv2.imencode(".jpg", frame)
        if not ret:
            continue
        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n")

# ---------- FEATHER HELPERS ----------
def send_command(cmd):
    try:
        r = requests.post(f"{FEATHER_IP}/command", json={"cmd": cmd}, timeout=2)
        return r.json()
    except Exception as e:
        return {"error": str(e)}

def get_sensors():
    try:
        r = requests.get(f"{FEATHER_IP}/sensors", timeout=2)
        return r.json()
    except Exception as e:
        return {"error": str(e)}

# ---------- ROUTES ----------
@app.route("/")
def index():
    return send_from_directory("frontend", "home.html")

@app.route("/video_feed1")
def video_feed1():
    return Response(generate_frames(lambda: latest_frame1, lock1),
                    mimetype="multipart/x-mixed-replace; boundary=frame")

@app.route("/video_feed2")
def video_feed2():
    return Response(generate_frames(lambda: latest_frame2, lock2),
                    mimetype="multipart/x-mixed-replace; boundary=frame")

@app.route("/command", methods=["POST"])
def command():
    data = request.get_json(silent=True) or {}
    key = data.get("key", "")
    if key == "stop":
        result = send_command("S")
    else:
        cmd = KEY_MAP.get(key)
        if not cmd:
            return jsonify(ok=False, error="Unknown key"), 400
        result = send_command(cmd)
    return jsonify(ok=True, result=result)

@app.route("/sensors")
def sensors():
    return jsonify(get_sensors())

@app.route("/status")
def status():
    try:
        r = requests.get(f"{FEATHER_IP}/status", timeout=2)
        return jsonify(r.json())
    except Exception as e:
        return jsonify(error=str(e)), 503

# ---------- MAIN ----------
if __name__ == "__main__":
    threading.Thread(target=capture_loop, args=(CAMERA1_URL, lock1, set1), daemon=True).start()
    threading.Thread(target=capture_loop, args=(CAMERA2_URL, lock2, set2), daemon=True).start()
    print(f"Server running at http://localhost:8080")
    app.run(host="0.0.0.0", port=8080, debug=False)
