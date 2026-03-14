# Main script
"""
Functionality:
 - GUI (image viewer from arduino)
 - Image recognition: call model.py
 - Keyboard input - WASD to control arduino motors
"""

import cv2
from model import load_model, detect, draw_detections
from input import ArduinoController

def main():
    net, labels = load_model()
    controller = ArduinoController()

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: cannot open camera")
        controller.close()
        return

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        detections = detect(frame, net, labels)
        annotated = draw_detections(frame, detections)

        cv2.imshow("Coral Reef Monitor", annotated)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        elif key != 255:
            controller.handle_key(key)

    controller.close()
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
