# OpenCV image recognition for invasive species in coral reefs
# Called by main.py (runs on laptop)
# Input: underwater image
# Functions: box highlight for invasive species

import os
import cv2
import numpy as np

CONFIDENCE_THRESHOLD = 0.5

# Target invasive coral reef species (matched against COCO-style labels or custom model)
INVASIVE_SPECIES = {
    "lionfish",
    "crown-of-thorns starfish",
    "green sea turtle",  # placeholder; swap with your custom class names
}

_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_WEIGHTS = os.path.join(_DIR, "model.caffemodel")
MODEL_CONFIG  = os.path.join(_DIR, "model.prototxt")
LABELS_FILE   = os.path.join(_DIR, "labels.txt")


def load_model(weights_path: str = MODEL_WEIGHTS,
               config_path: str  = MODEL_CONFIG,
               labels_path: str  = LABELS_FILE):
    """
    Load an OpenCV DNN model and its class labels.

    Returns:
        (net, labels) where net is the DNN network and labels is a list of
        class name strings indexed by class ID.
    """
    net = cv2.dnn.readNetFromCaffe(config_path, weights_path)

    with open(labels_path, "r") as f:
        labels = [line.strip() for line in f.readlines()]

    return net, labels


def detect(frame: np.ndarray, net, labels: list[str]) -> list[dict]:
    """
    Run object detection on a single BGR underwater frame.

    Args:
        frame:  BGR image as a numpy array (H x W x 3).
        net:    OpenCV DNN network from load_model().
        labels: Class label list from load_model().

    Returns:
        List of dicts for each detection above the confidence threshold:
            'label'      - class name string
            'confidence' - float in [0, 1]
            'box'        - (x, y, w, h) in pixel coordinates
            'invasive'   - True if the species is in INVASIVE_SPECIES
    """
    h, w = frame.shape[:2]
    blob = cv2.dnn.blobFromImage(
        cv2.resize(frame, (300, 300)),
        scalefactor=0.007843,
        size=(300, 300),
        mean=127.5,
    )
    net.setInput(blob)
    detections = net.forward()  # shape: (1, 1, N, 7)

    results = []
    for i in range(detections.shape[2]):
        confidence = float(detections[0, 0, i, 2])
        if confidence < CONFIDENCE_THRESHOLD:
            continue

        class_id = int(detections[0, 0, i, 1])
        label = labels[class_id] if class_id < len(labels) else "unknown"

        x1 = int(detections[0, 0, i, 3] * w)
        y1 = int(detections[0, 0, i, 4] * h)
        x2 = int(detections[0, 0, i, 5] * w)
        y2 = int(detections[0, 0, i, 6] * h)

        results.append({
            "label":      label,
            "confidence": confidence,
            "box":        (x1, y1, x2 - x1, y2 - y1),
            "invasive":   label.lower() in INVASIVE_SPECIES,
        })

    return results


def draw_detections(frame: np.ndarray, detections: list[dict]) -> np.ndarray:
    """
    Draw bounding boxes and labels onto a copy of frame.

    Invasive species boxes are drawn in red; others in green.

    Args:
        frame:      BGR image.
        detections: Output list from detect().

    Returns:
        Annotated BGR image.
    """
    output = frame.copy()
    for det in detections:
        x, y, bw, bh = det["box"]
        color = (0, 0, 255) if det["invasive"] else (0, 255, 0)
        label = f"{det['label']} ({det['confidence']:.2f})"
        cv2.rectangle(output, (x, y), (x + bw, y + bh), color, 2)
        cv2.putText(output, label, (x, max(y - 8, 10)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
    return output
