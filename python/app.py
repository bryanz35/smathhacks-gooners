"""Flask backend for GOONER ROV — serves video feed, forwards motor commands to Feather over WiFi, and streams sensor data to frontend."""

import time
import threading
import requests

import cv2
from flask import Flask, Response, jsonify, request, send_from_directory

# ---- CONFIGURE THIS ----
FEATHER_IP  = "http://172.20.10.x"  # Replace with Feather's IP from Serial Monitor
CAMERA1_URL = "http://172.20.10.4/stream"  # First ESP32-CAM
CAMERA2_URL = "http://172.20.10.5/stream"  # Second ESP32-CAM — replace with its IP
# ------------------------

app = Flask(__name__, static_folder="frontend", static_url_path="/static")

KEY_MAP = {
    "w": "F",
    "a": "L",
    "s": "B",
    "d": "R",
}

# ---------- CAMERA STATE ----------
latest_frame1 = None
latest_frame2 = None
frame_lock1 = threading.Lock()
frame_lock2 = threading.Lock()

# ---------- CAMERA THREADS ----------
def capture_loop(url, get_lock, set_frame):
    """Continuously grab frames from one ESP32-CAM."""
    print(f"Opening stream at {url} ...")
    cap = cv2.VideoCapture(url)
    if not cap.isOpened():
        print(f"Error: could not open {url}")
        return
    print(f"Camera connected: {url}")
    while True:
        ret, frame = cap.read()
        if not ret:
            continue
        with get_lock:
            set_frame(frame)

def set_frame1(f):
    global latest_frame1
    latest_frame1 = f

def set_frame2(f):
    global latest_frame2
    latest_frame2 = f

def generate_frames(get_frame, lock):
    """Yield MJPEG frames for one video feed endpoint."""
    while True:
        with lock:
            frame = get_frame()
        if frame is None:
            time.sleep(0.03)
            continue
        ret, jpeg = cv2.imencode(".jpg", frame)
        if not ret:
            continue
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n"
        )


# ---------- FEATHER HELPERS ----------
def send_command(cmd):
    """POST a motor command to the Feather."""
    try:
        r = requests.post(
            f"{FEATHER_IP}/command",
            json={"cmd": cmd},
            timeout=2
        )
        return r.json()
    except Exception as e:
        print(f"Command error: {e}")
        return {"error": str(e)}


def get_sensors():
    """GET latest sensor data from the Feather."""
    try:
        r = requests.get(f"{FEATHER_IP}/sensors", timeout=2)
        return r.json()
    except Exception as e:
        print(f"Sensor error: {e}")
        return {"error": str(e)}


# ---------- ROUTES ----------
@app.route("/")
def index():
    return send_from_directory("frontend", "home.html")


@app.route("/video_feed1")
def video_feed1():
    return Response(
        generate_frames(lambda: latest_frame1, frame_lock1),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )

@app.route("/video_feed2")
def video_feed2():
    return Response(
        generate_frames(lambda: latest_frame2, frame_lock2),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


@app.route("/command", methods=["POST"])
def command():
    """Receive keypress from home.js, forward to Feather."""
    data = request.get_json(silent=True) or {}
    key = data.get("key", "")

    if key == "stop":
        result = send_command("S")
    else:
        cmd = KEY_MAP.get(key)
        if cmd:
            result = send_command(cmd)
        else:
            return jsonify(ok=False, error="Unknown key"), 400

    return jsonify(ok=True, result=result)


@app.route("/sensors", methods=["GET"])
def sensors():
    """Proxy sensor data from Feather to frontend."""
    data = get_sensors()
    return jsonify(data)


@app.route("/feather_status", methods=["GET"])
def feather_status():
    """Check Feather WiFi status."""
    try:
        r = requests.get(f"{FEATHER_IP}/status", timeout=2)
        return jsonify(r.json())
    except Exception as e:
        return jsonify(error=str(e)), 503


# ---------- MAIN ----------
if __name__ == "__main__":
    threading.Thread(target=capture_loop, args=(CAMERA1_URL, frame_lock1, set_frame1), daemon=True).start()
    threading.Thread(target=capture_loop, args=(CAMERA2_URL, frame_lock2, set_frame2), daemon=True).start()

    print(f"Connecting to Feather at {FEATHER_IP} ...")
    app.run(host="0.0.0.0", port=8080, debug=False)