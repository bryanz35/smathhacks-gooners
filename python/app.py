"""Flask backend for GOONER ROV — serves video feed and forwards motor commands."""

import time
import threading

import cv2
from flask import Flask, Response, jsonify, request, send_from_directory

from input import ArduinoController
from model import load_model, detect, draw_detections

SERIAL_PORT = "/dev/cu.usbmodem1101" #VARIABLE PORT
BAUD_RATE = 115200

app = Flask(__name__, static_folder="frontend", static_url_path="/static")

# Global state
latest_frame = None
frame_lock = threading.Lock()
arduino = None

# Load YOLO model at startup
print("Loading YOLO detection model...")
yolo_net, yolo_labels = load_model()
print(f"Model loaded — {len(yolo_labels)} classes: {yolo_labels}")

KEY_MAP = {
    "w": b"F",
    "a": b"L",
    "s": b"B",
    "d": b"R",
}


def capture_loop(port):
    """Continuously grab frames from the ESP32-CAM and store the latest one."""
    global latest_frame

    print(f"Opening ESP32-CAM on {port} ...")
    cap = cv2.VideoCapture(port)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    if not cap.isOpened():
        print(f"Error: could not open {port}")
        return

    print("Camera connected.")
    while True:
        ret, frame = cap.read()
        if not ret:
            continue
        with frame_lock:
            latest_frame = frame


def generate_frames():
    """Yield MJPEG frames with YOLO detections drawn on."""
    while True:
        with frame_lock:
            frame = latest_frame
        if frame is None:
            time.sleep(0.03)
            continue

        # Run YOLO detection and draw bounding boxes
        detections = detect(frame, yolo_net, yolo_labels)
        annotated = draw_detections(frame, detections)

        ret, jpeg = cv2.imencode(".jpg", annotated)
        if not ret:
            continue
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n"
        )


@app.route("/")
def index():
    return send_from_directory("frontend", "home.html")


@app.route("/video_feed")
def video_feed():
    return Response(
        generate_frames(), mimetype="multipart/x-mixed-replace; boundary=frame"
    )


@app.route("/command", methods=["POST"])
def command():
    data = request.get_json(silent=True) or {}
    key = data.get("key", "")

    if key == "stop":
        arduino.stop()
    else:
        cmd = KEY_MAP.get(key)
        if cmd:
            arduino.send(cmd)

    return jsonify(ok=True)


if __name__ == "__main__":
    arduino = ArduinoController(port="/dev/cu.usbmodem1101") #VARIABLE PORT

    app.run(host="0.0.0.0", port=8080, debug=False)