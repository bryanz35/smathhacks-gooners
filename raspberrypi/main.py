# Main script (runs on Raspberry Pi)
"""
Functionality:
 - Camera capture and OpenCV species detection
 - Streams annotated video frames to laptop over TCP
 - Receives motor commands from laptop and forwards to Arduino via serial
"""

import cv2
import socket
import struct
import threading
from model import load_model, detect, draw_detections
from input import ArduinoController

VIDEO_PORT = 5000
CMD_PORT = 5001
UPDATE_MS = 30


def start_video_server(net, labels):
    """Capture camera frames, run detection, and stream to laptop."""
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: cannot open camera")
        return

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", VIDEO_PORT))
    server.listen(1)
    print(f"Video server listening on port {VIDEO_PORT}")

    while True:
        conn, addr = server.accept()
        print(f"Laptop connected for video from {addr}")
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    continue

                detections = detect(frame, net, labels)
                annotated = draw_detections(frame, detections)

                _, jpg = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 70])
                data = jpg.tobytes()

                # send 4-byte length prefix + JPEG data
                conn.sendall(struct.pack(">I", len(data)) + data)
        except (BrokenPipeError, ConnectionResetError):
            print(f"Laptop disconnected from video")
        finally:
            conn.close()


def start_cmd_server(controller):
    """Receive motor commands from laptop and forward to Arduino."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", CMD_PORT))
    server.listen(1)
    print(f"Command server listening on port {CMD_PORT}")

    cmd_map = {
        ord("F"): b"F",
        ord("B"): b"B",
        ord("L"): b"L",
        ord("R"): b"R",
        ord("S"): b"S",
    }

    while True:
        conn, addr = server.accept()
        print(f"Laptop connected for commands from {addr}")
        try:
            while True:
                data = conn.recv(1)
                if not data:
                    break
                cmd = cmd_map.get(data[0])
                if cmd:
                    controller.send(cmd)
        except (BrokenPipeError, ConnectionResetError):
            print(f"Laptop disconnected from commands")
        finally:
            conn.close()


def main():
    print("Starting Coral Reef Monitor (Raspberry Pi)")
    net, labels = load_model()
    controller = ArduinoController()

    cmd_thread = threading.Thread(target=start_cmd_server, args=(controller,), daemon=True)
    cmd_thread.start()

    # video server runs on main thread (blocking)
    start_video_server(net, labels)

    controller.close()


if __name__ == "__main__":
    main()
