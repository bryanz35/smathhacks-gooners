# YOLO ONNX object detection for invasive species in coral reefs
# Loads best.onnx from machine-learning/output-yolo/ and runs inference via OpenCV DNN

import os
import cv2
import numpy as np

CONFIDENCE_THRESHOLD = 0.5
NMS_THRESHOLD = 0.45
INPUT_SIZE = 320

INVASIVE_SPECIES = {"lionfish"}

_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_DIR)
MODEL_PATH = os.path.join(_REPO, "machine-learning", "output-yolo", "best.onnx")
LABELS_FILE = os.path.join(_REPO, "machine-learning", "output-yolo", "labels.txt")


def load_model(model_path: str = MODEL_PATH, labels_path: str = LABELS_FILE):
    """Load YOLO ONNX model and class labels. Returns (net, labels)."""
    net = cv2.dnn.readNetFromONNX(model_path)
    with open(labels_path, "r") as f:
        labels = [line.strip() for line in f if line.strip()]
    return net, labels


def detect(frame: np.ndarray, net, labels: list[str]) -> list[dict]:
    """
    Run YOLO detection on a BGR frame.

    Returns list of dicts with keys: label, confidence, box (x, y, w, h), invasive.
    """
    h, w = frame.shape[:2]

    # Preprocess: letterbox to INPUT_SIZE x INPUT_SIZE
    blob = cv2.dnn.blobFromImage(
        frame, scalefactor=1.0 / 255.0,
        size=(INPUT_SIZE, INPUT_SIZE),
        swapRB=True, crop=False,
    )
    net.setInput(blob)
    outputs = net.forward()  # shape: (1, 4+num_classes, num_preds)

    # Transpose to (num_preds, 4+num_classes)
    outputs = outputs[0].T  # (num_preds, 18)

    boxes = []
    confidences = []
    class_ids = []

    x_scale = w / INPUT_SIZE
    y_scale = h / INPUT_SIZE

    for row in outputs:
        cx, cy, bw, bh = row[0], row[1], row[2], row[3]
        scores = row[4:]
        max_score = float(np.max(scores))
        if max_score < CONFIDENCE_THRESHOLD:
            continue

        class_id = int(np.argmax(scores))

        # Convert from center coords to top-left corner
        x1 = int((cx - bw / 2) * x_scale)
        y1 = int((cy - bh / 2) * y_scale)
        box_w = int(bw * x_scale)
        box_h = int(bh * y_scale)

        boxes.append([x1, y1, box_w, box_h])
        confidences.append(max_score)
        class_ids.append(class_id)

    # Non-maximum suppression
    indices = cv2.dnn.NMSBoxes(boxes, confidences, CONFIDENCE_THRESHOLD, NMS_THRESHOLD)

    results = []
    for i in indices:
        idx = i if isinstance(i, int) else i[0]
        label = labels[class_ids[idx]] if class_ids[idx] < len(labels) else "unknown"
        results.append({
            "label": label,
            "confidence": confidences[idx],
            "box": tuple(boxes[idx]),
            "invasive": label.lower() in INVASIVE_SPECIES,
        })

    return results


def draw_detections(frame: np.ndarray, detections: list[dict]) -> np.ndarray:
    """Draw bounding boxes and labels. Invasive species in red, others in green."""
    output = frame.copy()
    for det in detections:
        x, y, bw, bh = det["box"]
        color = (0, 0, 255) if det["invasive"] else (0, 255, 0)
        label = f"{det['label']} ({det['confidence']:.2f})"
        cv2.rectangle(output, (x, y), (x + bw, y + bh), color, 2)
        cv2.putText(output, label, (x, max(y - 8, 10)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
    return output
