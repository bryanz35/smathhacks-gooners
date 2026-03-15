"""Read video from an ESP32-CAM-MB connected via USB serial and display it."""

import cv2
import sys

SERIAL_PORT = "/dev/ttyUSB0"
BAUD_RATE = 115200 


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else SERIAL_PORT

    print(f"Opening ESP32-CAM on {port} ...")
    cap = cv2.VideoCapture(port)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    if not cap.isOpened():
        print(f"Error: could not open {port}")
        sys.exit(1)

    print("Connected. Press 'q' to quit.")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to read frame.")
            continue

        cv2.imshow("ESP32-CAM", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
