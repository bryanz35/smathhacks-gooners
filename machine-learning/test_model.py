"""
Test fish_classifier.onnx accuracy against the validation dataset.

Uses only OpenCV and NumPy (no PyTorch required), so this can run
on the Raspberry Pi as well.

Usage:
    python test_model.py                         # test on validation set
    python test_model.py --split test             # test on test set
    python test_model.py --model output/fish_classifier.onnx
"""

import argparse
from pathlib import Path
from collections import defaultdict

import cv2
import numpy as np
import onnxruntime as ort
from PIL import Image

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DATA_DIR = Path(__file__).parent / "data"
OUTPUT_DIR = Path(__file__).parent / "output"
IMG_SIZE = 128
CLASS_NAMES = [
    "AngelFish", "BlueTang", "ButterflyFish", "ClownFish", "GoldFish",
    "Gourami", "MorishIdol", "PlatyFish", "RibbonedSweetlips",
    "ThreeStripedDamselfish", "YellowCichlid", "YellowTang", "ZebraFish",
    "Lionfish",
]
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


# ---------------------------------------------------------------------------
# Load crops from YOLO labels
# ---------------------------------------------------------------------------
def load_samples(split_dir: Path):
    """Yield (crop_bgr, class_id) for every bounding box in the split."""
    img_dir = split_dir / "images"
    lbl_dir = split_dir / "labels"

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

        img = Image.open(img_path).convert("RGB")
        iw, ih = img.size

        for line in lbl_path.read_text().strip().splitlines():
            parts = line.strip().split()
            if len(parts) < 5:
                continue
            cls_id = int(parts[0])
            cx, cy, bw, bh = map(float, parts[1:5])

            x1 = max(0, int((cx - bw / 2) * iw))
            y1 = max(0, int((cy - bh / 2) * ih))
            x2 = min(iw, int((cx + bw / 2) * iw))
            y2 = min(ih, int((cy + bh / 2) * ih))

            crop = img.crop((x1, y1, x2, y2))
            crop_bgr = cv2.cvtColor(np.array(crop), cv2.COLOR_RGB2BGR)
            yield crop_bgr, cls_id


# ---------------------------------------------------------------------------
# Preprocessing (matches torchvision val transforms)
# ---------------------------------------------------------------------------
def preprocess(crop_bgr: np.ndarray) -> np.ndarray:
    """Resize, normalize, and return a (1, 3, H, W) float32 blob."""
    resized = cv2.resize(crop_bgr, (IMG_SIZE, IMG_SIZE))
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0

    # normalize per-channel
    for c in range(3):
        rgb[:, :, c] = (rgb[:, :, c] - IMAGENET_MEAN[c]) / IMAGENET_STD[c]

    # HWC -> NCHW
    blob = np.transpose(rgb, (2, 0, 1))[np.newaxis, ...]
    return blob


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------
def evaluate(model_path: Path, split_dir: Path):
    session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name
    print(f"Loaded model: {model_path}")
    print(f"Evaluating on: {split_dir}\n")

    correct = 0
    total = 0

    # per-class tracking
    class_correct = defaultdict(int)
    class_total = defaultdict(int)

    # confusion matrix
    confusion = np.zeros((len(CLASS_NAMES), len(CLASS_NAMES)), dtype=int)

    for crop_bgr, cls_id in load_samples(split_dir):
        blob = preprocess(crop_bgr)
        output = session.run(None, {input_name: blob})[0]
        pred = int(np.argmax(output[0]))

        confusion[cls_id][pred] += 1
        class_total[cls_id] += 1
        if pred == cls_id:
            correct += 1
            class_correct[cls_id] += 1
        total += 1

    if total == 0:
        print("No samples found.")
        return

    # overall accuracy
    overall_acc = correct / total
    print(f"Overall accuracy: {correct}/{total} = {overall_acc:.4f} ({overall_acc*100:.1f}%)\n")

    # per-class accuracy
    print(f"{'Class':<28s} {'Correct':>8s} {'Total':>8s} {'Accuracy':>10s}")
    print("-" * 58)
    for i, name in enumerate(CLASS_NAMES):
        t = class_total.get(i, 0)
        c = class_correct.get(i, 0)
        acc = c / t if t > 0 else 0.0
        print(f"{name:<28s} {c:>8d} {t:>8d} {acc:>9.1%}")

    # confusion matrix to CSV
    csv_path = OUTPUT_DIR / "confusion_matrix.csv"
    header = "," + ",".join(CLASS_NAMES)
    rows = [header]
    for i, name in enumerate(CLASS_NAMES):
        rows.append(name + "," + ",".join(str(confusion[i][j]) for j in range(len(CLASS_NAMES))))
    csv_path.write_text("\n".join(rows) + "\n")
    print(f"\nConfusion matrix saved to {csv_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Test fish classifier ONNX model")
    parser.add_argument("--model", type=str, default=str(OUTPUT_DIR / "fish_classifier.onnx"),
                        help="Path to ONNX model")
    parser.add_argument("--split", type=str, default="valid",
                        choices=["train", "valid", "test"],
                        help="Dataset split to evaluate")
    args = parser.parse_args()

    model_path = Path(args.model)
    split_dir = DATA_DIR / args.split

    if not model_path.exists():
        print(f"Error: model not found at {model_path}")
        print("Run train.py first, or pass --model with the correct path.")
        return

    if not split_dir.exists():
        print(f"Error: split directory not found at {split_dir}")
        return

    evaluate(model_path, split_dir)


if __name__ == "__main__":
    main()
