"""Connect to an ESP-CAM-MB and display its MJPEG video stream."""

import cv2
import sys

# Default ESP-CAM stream URL (the :81/stream endpoint serves MJPEG)
ESP_CAM_URL = "http://192.168.1.3:81/stream"


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else ESP_CAM_URL
    print(f"Connecting to ESP-CAM at {url} ...")

    cap = cv2.VideoCapture(url)
    if not cap.isOpened():
        print(f"Error: could not connect to {url}")
        sys.exit(1)

    print("Connected. Press 'q' to quit.")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Lost connection to camera.")
            break

        cv2.imshow("ESP-CAM", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
