"""
YOLO11n fish detection model.

Trains a YOLO11n object detector on the YOLO-format dataset in data/.
Outputs bounding boxes + class labels, suitable for drawing detections
on the ROV video feed.

Usage:
    pip install ultralytics matplotlib
    python train_yolo.py                    # train with defaults (50 epochs, 320px)
    python train_yolo.py --epochs 100       # customize epochs
    python train_yolo.py --model yolo11s    # use a larger model variant
    python train_yolo.py --export-only      # export existing best.pt to ONNX
"""

import argparse
import json
import shutil
import tempfile
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
OUTPUT_DIR = Path(__file__).parent / "output-yolo"

CLASS_NAMES = [
    "AngelFish", "BlueTang", "ButterflyFish", "ClownFish", "GoldFish",
    "Gourami", "MorishIdol", "PlatyFish", "RibbonedSweetlips",
    "ThreeStripedDamselfish", "YellowCichlid", "YellowTang", "ZebraFish",
    "Lionfish",
]


def build_data_yaml() -> Path:
    """Write a data.yaml with absolute paths so Ultralytics resolves them correctly."""
    yaml_path = OUTPUT_DIR / "data.yaml"
    yaml_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        f"train: {DATA_DIR / 'train' / 'images'}",
        f"val: {DATA_DIR / 'valid' / 'images'}",
        f"test: {DATA_DIR / 'test' / 'images'}",
        "",
        f"nc: {len(CLASS_NAMES)}",
        f"names: {CLASS_NAMES}",
    ]
    yaml_path.write_text("\n".join(lines) + "\n")
    print(f"Wrote data config to {yaml_path}")
    return yaml_path


def train(args):
    from ultralytics import YOLO

    yaml_path = build_data_yaml()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    model = YOLO(f"{args.model}.pt")

    results = model.train(
        data=str(yaml_path),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch_size,
        workers=args.workers,
        project=str(OUTPUT_DIR),
        name="train",
        exist_ok=True,
        save=True,
        plots=True,  # Ultralytics saves confusion matrix, PR curves, etc.
        val=True,     # run validation every epoch
    )

    # -----------------------------------------------------------------------
    # Collect per-epoch metrics from the Ultralytics CSV log
    # -----------------------------------------------------------------------
    csv_path = OUTPUT_DIR / "train" / "results.csv"
    history = parse_results_csv(csv_path)

    if history:
        hist_path = OUTPUT_DIR / "history.json"
        hist_path.write_text(json.dumps(history, indent=2))
        print(f"Saved metrics history to {hist_path}")
        plot_history(history)

    # Copy best weights to a predictable location
    best_src = OUTPUT_DIR / "train" / "weights" / "best.pt"
    best_dst = OUTPUT_DIR / "best.pt"
    if best_src.exists():
        shutil.copy2(best_src, best_dst)
        print(f"Copied best weights to {best_dst}")

    # Export to ONNX
    export_onnx(best_dst, args.imgsz)


def parse_results_csv(csv_path: Path) -> dict:
    """Parse the Ultralytics results.csv into a history dict."""
    if not csv_path.exists():
        print(f"Warning: {csv_path} not found, skipping history export")
        return {}

    import csv
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        return {}

    # Ultralytics CSV columns have leading spaces — strip them
    rows = [{k.strip(): v.strip() for k, v in row.items()} for row in rows]

    history = {
        "epoch": [],
        "train_box_loss": [],
        "train_cls_loss": [],
        "train_dfl_loss": [],
        "val_box_loss": [],
        "val_cls_loss": [],
        "val_dfl_loss": [],
        "mAP50": [],
        "mAP50-95": [],
        "precision": [],
        "recall": [],
    }

    # Map from our keys to CSV column names
    col_map = {
        "epoch": "epoch",
        "train_box_loss": "train/box_loss",
        "train_cls_loss": "train/cls_loss",
        "train_dfl_loss": "train/dfl_loss",
        "val_box_loss": "val/box_loss",
        "val_cls_loss": "val/cls_loss",
        "val_dfl_loss": "val/dfl_loss",
        "mAP50": "metrics/mAP50(B)",
        "mAP50-95": "metrics/mAP50-95(B)",
        "precision": "metrics/precision(B)",
        "recall": "metrics/recall(B)",
    }

    for row in rows:
        for key, col in col_map.items():
            val = row.get(col)
            if val is not None:
                history[key].append(float(val))

    return history


def plot_history(history: dict):
    """Save training curves to output-yolo/training_curves.png."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    epochs = history.get("epoch", [])
    if not epochs:
        return

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # --- Loss ---
    ax = axes[0][0]
    ax.plot(epochs, history["train_box_loss"], label="Train Box Loss")
    ax.plot(epochs, history["train_cls_loss"], label="Train Cls Loss")
    ax.plot(epochs, history["train_dfl_loss"], label="Train DFL Loss")
    ax.set_xlabel("Epoch")
    ax.set_ylabel("Loss")
    ax.set_title("Training Loss")
    ax.legend()
    ax.grid(True)

    ax = axes[0][1]
    ax.plot(epochs, history["val_box_loss"], label="Val Box Loss")
    ax.plot(epochs, history["val_cls_loss"], label="Val Cls Loss")
    ax.plot(epochs, history["val_dfl_loss"], label="Val DFL Loss")
    ax.set_xlabel("Epoch")
    ax.set_ylabel("Loss")
    ax.set_title("Validation Loss")
    ax.legend()
    ax.grid(True)

    # --- mAP ---
    ax = axes[1][0]
    ax.plot(epochs, history["mAP50"], label="mAP@50")
    ax.plot(epochs, history["mAP50-95"], label="mAP@50-95")
    ax.set_xlabel("Epoch")
    ax.set_ylabel("mAP")
    ax.set_title("Mean Average Precision")
    ax.legend()
    ax.grid(True)

    # --- Precision / Recall ---
    ax = axes[1][1]
    ax.plot(epochs, history["precision"], label="Precision")
    ax.plot(epochs, history["recall"], label="Recall")
    ax.set_xlabel("Epoch")
    ax.set_ylabel("Score")
    ax.set_title("Precision & Recall")
    ax.legend()
    ax.grid(True)

    fig.tight_layout()
    path = OUTPUT_DIR / "training_curves.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"Saved training curves to {path}")


def export_onnx(weights_path: Path = None, imgsz: int = 640):
    """Export the best YOLO weights to ONNX."""
    from ultralytics import YOLO

    if weights_path is None:
        weights_path = OUTPUT_DIR / "best.pt"

    if not weights_path.exists():
        print(f"Error: weights not found at {weights_path}")
        print("Run training first, or pass the correct path.")
        return

    model = YOLO(str(weights_path))
    onnx_path = model.export(format="onnx", imgsz=imgsz)
    print(f"Exported ONNX model to {onnx_path}")

    # Save labels alongside
    labels_path = OUTPUT_DIR / "labels.txt"
    labels_path.write_text("\n".join(CLASS_NAMES) + "\n")
    print(f"Labels written to {labels_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Train YOLO11 fish detector")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--imgsz", type=int, default=320)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--model", type=str, default="yolo11n",
                        help="YOLO variant: yolo11n, yolo11s, yolov8n, etc.")
    parser.add_argument("--export-only", action="store_true",
                        help="Skip training, just export existing best.pt to ONNX")
    args = parser.parse_args()

    if args.export_only:
        export_onnx()
    else:
        train(args)


if __name__ == "__main__":
    main()
