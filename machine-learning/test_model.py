"""
Test YOLO fish detector against the validation/test dataset.

Loads the ONNX model exported by train_yolo.py, runs inference on each
image, and matches predicted boxes to ground-truth boxes via IoU to
compute per-class AP, mAP@50, precision, recall, and a confusion matrix.

Uses only OpenCV, NumPy, and ONNX Runtime (no PyTorch/Ultralytics
required), so this can run on the Raspberry Pi as well.

Usage:
    python test_model.py                              # test on validation set
    python test_model.py --split test                  # test on test set
    python test_model.py --model output-yolo/best.onnx
    python test_model.py --conf 0.5                    # raise confidence threshold
"""

import argparse
from pathlib import Path
from collections import defaultdict

import cv2
import numpy as np
import onnxruntime as ort

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DATA_DIR = Path(__file__).parent / "data"
OUTPUT_DIR = Path(__file__).parent / "output-yolo"
IMG_SIZE = 320
CONF_THRESHOLD = 0.25
IOU_THRESHOLD = 0.45  # NMS IoU threshold
MATCH_IOU = 0.5       # IoU threshold for matching pred to ground truth
CLASS_NAMES = [
    "AngelFish", "BlueTang", "ButterflyFish", "ClownFish", "GoldFish",
    "Gourami", "MorishIdol", "PlatyFish", "RibbonedSweetlips",
    "ThreeStripedDamselfish", "YellowCichlid", "YellowTang", "ZebraFish",
    "Lionfish",
]
NUM_CLASSES = len(CLASS_NAMES)


# ---------------------------------------------------------------------------
# Load ground-truth boxes from YOLO label files
# ---------------------------------------------------------------------------
def load_gt_boxes(lbl_path: Path, img_w: int, img_h: int) -> list[dict]:
    """Parse a YOLO label file into absolute-coordinate boxes."""
    boxes = []
    for line in lbl_path.read_text().strip().splitlines():
        parts = line.strip().split()
        if len(parts) < 5:
            continue
        cls_id = int(parts[0])
        cx, cy, bw, bh = map(float, parts[1:5])
        x1 = (cx - bw / 2) * img_w
        y1 = (cy - bh / 2) * img_h
        x2 = (cx + bw / 2) * img_w
        y2 = (cy + bh / 2) * img_h
        boxes.append({"class_id": cls_id, "box": (x1, y1, x2, y2)})
    return boxes


# ---------------------------------------------------------------------------
# YOLO ONNX preprocessing
# ---------------------------------------------------------------------------
def preprocess(img_bgr: np.ndarray, imgsz: int) -> tuple[np.ndarray, float, tuple[int, int]]:
    """Letterbox-resize and normalize for YOLO ONNX input.

    Returns (blob, ratio, pad) where ratio and pad are needed to
    map predictions back to original image coordinates.
    """
    h, w = img_bgr.shape[:2]
    scale = imgsz / max(h, w)
    new_w, new_h = int(w * scale), int(h * scale)
    resized = cv2.resize(img_bgr, (new_w, new_h))

    # pad to square
    canvas = np.full((imgsz, imgsz, 3), 114, dtype=np.uint8)
    pad_x, pad_y = (imgsz - new_w) // 2, (imgsz - new_h) // 2
    canvas[pad_y:pad_y + new_h, pad_x:pad_x + new_w] = resized

    # HWC BGR -> NCHW RGB float32 [0,1]
    rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    blob = np.transpose(rgb, (2, 0, 1))[np.newaxis, ...]
    return blob, scale, (pad_x, pad_y)


def postprocess(output: np.ndarray, scale: float, pad: tuple[int, int],
                img_w: int, img_h: int, conf_thresh: float,
                iou_thresh: float) -> list[dict]:
    """Decode YOLO ONNX output into a list of detections.

    Handles the standard Ultralytics ONNX output shape: (1, 4+nc, N)
    where rows 0-3 are cx, cy, w, h and rows 4+ are class scores.
    """
    # output shape: (1, 4+nc, N) -> squeeze and transpose to (N, 4+nc)
    preds = output[0]
    if preds.shape[0] < preds.shape[1]:
        preds = preds.T  # (N, 4+nc)

    if preds.shape[1] < 4 + NUM_CLASSES:
        return []

    cx = preds[:, 0]
    cy = preds[:, 1]
    w = preds[:, 2]
    h = preds[:, 3]
    class_scores = preds[:, 4:4 + NUM_CLASSES]

    # best class per detection
    class_ids = np.argmax(class_scores, axis=1)
    confidences = class_scores[np.arange(len(class_ids)), class_ids]

    # confidence filter
    mask = confidences >= conf_thresh
    cx, cy, w, h = cx[mask], cy[mask], w[mask], h[mask]
    class_ids = class_ids[mask]
    confidences = confidences[mask]

    if len(confidences) == 0:
        return []

    # convert cx,cy,w,h to x1,y1,x2,y2 in letterboxed coords
    x1 = cx - w / 2
    y1 = cy - h / 2
    x2 = cx + w / 2
    y2 = cy + h / 2

    # undo letterbox: remove padding, undo scale
    pad_x, pad_y = pad
    x1 = (x1 - pad_x) / scale
    y1 = (y1 - pad_y) / scale
    x2 = (x2 - pad_x) / scale
    y2 = (y2 - pad_y) / scale

    # clip to image bounds
    x1 = np.clip(x1, 0, img_w)
    y1 = np.clip(y1, 0, img_h)
    x2 = np.clip(x2, 0, img_w)
    y2 = np.clip(y2, 0, img_h)

    # NMS per class
    boxes_for_nms = np.stack([x1, y1, x2, y2], axis=1).astype(np.float32)
    keep = []
    for cls in np.unique(class_ids):
        cls_mask = class_ids == cls
        cls_indices = np.where(cls_mask)[0]
        cls_boxes = boxes_for_nms[cls_mask]
        cls_confs = confidences[cls_mask]

        nms_indices = cv2.dnn.NMSBoxes(
            cls_boxes.tolist(), cls_confs.tolist(),
            conf_thresh, iou_thresh,
        )
        if len(nms_indices) > 0:
            nms_indices = np.array(nms_indices).flatten()
            keep.extend(cls_indices[nms_indices])

    detections = []
    for i in keep:
        detections.append({
            "class_id": int(class_ids[i]),
            "confidence": float(confidences[i]),
            "box": (float(x1[i]), float(y1[i]), float(x2[i]), float(y2[i])),
        })

    return detections


# ---------------------------------------------------------------------------
# IoU
# ---------------------------------------------------------------------------
def compute_iou(box_a, box_b) -> float:
    """Compute IoU between two (x1, y1, x2, y2) boxes."""
    xa = max(box_a[0], box_b[0])
    ya = max(box_a[1], box_b[1])
    xb = min(box_a[2], box_b[2])
    yb = min(box_a[3], box_b[3])
    inter = max(0, xb - xa) * max(0, yb - ya)
    area_a = (box_a[2] - box_a[0]) * (box_a[3] - box_a[1])
    area_b = (box_b[2] - box_b[0]) * (box_b[3] - box_b[1])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


# ---------------------------------------------------------------------------
# Match predictions to ground truth
# ---------------------------------------------------------------------------
def match_detections(gt_boxes: list[dict], pred_boxes: list[dict],
                     iou_thresh: float) -> tuple[list, list, list]:
    """Match predicted boxes to ground-truth boxes using IoU.

    Returns:
        tp_list: list of (gt_class, pred_class, confidence) for matched pairs
        fp_list: list of (pred_class, confidence) for unmatched predictions
        fn_list: list of (gt_class,) for unmatched ground truths
    """
    tp_list, fp_list, fn_list = [], [], []
    matched_gt = set()

    # sort predictions by confidence (highest first)
    sorted_preds = sorted(pred_boxes, key=lambda d: d["confidence"], reverse=True)

    for pred in sorted_preds:
        best_iou = 0
        best_gt_idx = -1
        for i, gt in enumerate(gt_boxes):
            if i in matched_gt:
                continue
            iou = compute_iou(pred["box"], gt["box"])
            if iou > best_iou:
                best_iou = iou
                best_gt_idx = i

        if best_iou >= iou_thresh and best_gt_idx >= 0:
            matched_gt.add(best_gt_idx)
            tp_list.append((gt_boxes[best_gt_idx]["class_id"],
                            pred["class_id"], pred["confidence"]))
        else:
            fp_list.append((pred["class_id"], pred["confidence"]))

    for i, gt in enumerate(gt_boxes):
        if i not in matched_gt:
            fn_list.append((gt["class_id"],))

    return tp_list, fp_list, fn_list


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------
def evaluate(model_path: Path, split_dir: Path, conf_thresh: float,
             iou_thresh: float):
    session = ort.InferenceSession(str(model_path),
                                   providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name
    print(f"Loaded model: {model_path}")
    print(f"Evaluating on: {split_dir}")
    print(f"Confidence threshold: {conf_thresh}")
    print(f"IoU match threshold: {iou_thresh}\n")

    img_dir = split_dir / "images"
    lbl_dir = split_dir / "labels"

    # accumulators
    all_tp, all_fp, all_fn = [], [], []
    confusion = np.zeros((NUM_CLASSES, NUM_CLASSES), dtype=int)
    # for missed detections (FN) — row = gt class, col = "background"
    fn_per_class = defaultdict(int)
    # for false positives — "background" predicted as class
    fp_per_class = defaultdict(int)

    image_count = 0

    for lbl_path in sorted(lbl_dir.glob("*.txt")):
        stem = lbl_path.stem
        img_path = None
        for ext in (".jpg", ".jpeg", ".png"):
            candidate = img_dir / f"{stem}{ext}"
            if candidate.exists():
                img_path = candidate
                break
        if img_path is None:
            continue

        img_bgr = cv2.imread(str(img_path))
        if img_bgr is None:
            continue

        img_h, img_w = img_bgr.shape[:2]
        gt_boxes = load_gt_boxes(lbl_path, img_w, img_h)
        if not gt_boxes:
            continue

        image_count += 1

        # run inference
        blob, scale, pad = preprocess(img_bgr, IMG_SIZE)
        output = session.run(None, {input_name: blob})[0]
        pred_boxes = postprocess(output, scale, pad, img_w, img_h,
                                 conf_thresh, IOU_THRESHOLD)

        # match
        tp_list, fp_list, fn_list = match_detections(gt_boxes, pred_boxes,
                                                      iou_thresh)
        all_tp.extend(tp_list)
        all_fp.extend(fp_list)
        all_fn.extend(fn_list)

        # confusion matrix (TP: gt_class vs pred_class)
        for gt_cls, pred_cls, _ in tp_list:
            confusion[gt_cls][pred_cls] += 1
        for pred_cls, _ in fp_list:
            fp_per_class[pred_cls] += 1
        for (gt_cls,) in fn_list:
            fn_per_class[gt_cls] += 1

    if image_count == 0:
        print("No images found.")
        return

    # -----------------------------------------------------------------------
    # Overall stats
    # -----------------------------------------------------------------------
    total_tp = len(all_tp)
    total_fp = len(all_fp)
    total_fn = len(all_fn)
    precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0
    recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    print(f"Images evaluated: {image_count}")
    print(f"Total TP: {total_tp}  FP: {total_fp}  FN: {total_fn}")
    print(f"Precision: {precision:.4f}")
    print(f"Recall:    {recall:.4f}")
    print(f"F1 Score:  {f1:.4f}\n")

    # -----------------------------------------------------------------------
    # Per-class results
    # -----------------------------------------------------------------------
    print(f"{'Class':<28s} {'TP':>6s} {'FP':>6s} {'FN':>6s} "
          f"{'Prec':>8s} {'Recall':>8s} {'F1':>8s}")
    print("-" * 74)

    # count TP per class (where gt_class == pred_class)
    class_tp = defaultdict(int)
    for gt_cls, pred_cls, _ in all_tp:
        if gt_cls == pred_cls:
            class_tp[gt_cls] += 1

    for i, name in enumerate(CLASS_NAMES):
        tp = class_tp.get(i, 0)
        fp = fp_per_class.get(i, 0)
        # also count misclassified detections as FP for this class
        for gt_cls, pred_cls, _ in all_tp:
            if pred_cls == i and gt_cls != i:
                fp += 1
        fn = fn_per_class.get(i, 0)
        # also count misclassified detections as FN for the gt class
        for gt_cls, pred_cls, _ in all_tp:
            if gt_cls == i and pred_cls != i:
                fn += 1

        p = tp / (tp + fp) if (tp + fp) > 0 else 0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0
        f = 2 * p * r / (p + r) if (p + r) > 0 else 0
        print(f"{name:<28s} {tp:>6d} {fp:>6d} {fn:>6d} "
              f"{p:>7.1%} {r:>7.1%} {f:>7.1%}")

    # -----------------------------------------------------------------------
    # Confusion matrix to CSV
    # -----------------------------------------------------------------------
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUTPUT_DIR / "confusion_matrix.csv"
    header = "," + ",".join(CLASS_NAMES)
    rows = [header]
    for i, name in enumerate(CLASS_NAMES):
        rows.append(name + "," + ",".join(
            str(confusion[i][j]) for j in range(NUM_CLASSES)))
    csv_path.write_text("\n".join(rows) + "\n")
    print(f"\nConfusion matrix saved to {csv_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Test YOLO fish detector")
    parser.add_argument("--model", type=str,
                        default=str(OUTPUT_DIR / "best.onnx"),
                        help="Path to ONNX model")
    parser.add_argument("--split", type=str, default="valid",
                        choices=["train", "valid", "test"],
                        help="Dataset split to evaluate")
    parser.add_argument("--conf", type=float, default=CONF_THRESHOLD,
                        help="Confidence threshold")
    parser.add_argument("--iou", type=float, default=MATCH_IOU,
                        help="IoU threshold for matching predictions to GT")
    args = parser.parse_args()

    model_path = Path(args.model)
    split_dir = DATA_DIR / args.split

    if not model_path.exists():
        print(f"Error: model not found at {model_path}")
        print("Run train_yolo.py first, or pass --model with the correct path.")
        return

    if not split_dir.exists():
        print(f"Error: split directory not found at {split_dir}")
        return

    evaluate(model_path, split_dir, args.conf, args.iou)


if __name__ == "__main__":
    main()
