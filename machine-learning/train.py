"""
Lightweight fish classification model using MobileNetV2.

Converts the YOLO detection dataset (data/) into classification crops,
then trains a MobileNetV2 classifier (14 classes). The final model is
exported to ONNX for easy deployment with OpenCV DNN on the Raspberry Pi.

Usage:
    pip install torch torchvision
    python train.py                  # train with defaults
    python train.py --epochs 30      # customize epochs
    python train.py --export-only    # just export a trained checkpoint to ONNX
"""

import argparse
import json
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms, models
from PIL import Image

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DATA_DIR = Path(__file__).parent / "data"
OUTPUT_DIR = Path(__file__).parent / "output"
IMG_SIZE = 128  # small input for fast inference on Pi
NUM_CLASSES = 14
CLASS_NAMES = [
    "AngelFish", "BlueTang", "ButterflyFish", "ClownFish", "GoldFish",
    "Gourami", "MorishIdol", "PlatyFish", "RibbonedSweetlips",
    "ThreeStripedDamselfish", "YellowCichlid", "YellowTang", "ZebraFish",
    "Lionfish",
]

# ---------------------------------------------------------------------------
# Dataset — crops bounding boxes from YOLO labels on the fly
# ---------------------------------------------------------------------------
class FishCropDataset(Dataset):
    """Reads YOLO-format labels and yields one crop per bounding box."""

    def __init__(self, split_dir: Path, transform=None):
        self.transform = transform
        self.samples = []  # list of (image_path, class_id, cx, cy, w, h)

        img_dir = split_dir / "images"
        lbl_dir = split_dir / "labels"
        if not img_dir.exists():
            return

        for lbl_path in sorted(lbl_dir.glob("*.txt")):
            # find matching image (try common extensions)
            stem = lbl_path.stem
            img_path = None
            for ext in (".jpg", ".jpeg", ".png"):
                candidate = img_dir / f"{stem}{ext}"
                if candidate.exists():
                    img_path = candidate
                    break
            if img_path is None:
                continue

            for line in lbl_path.read_text().strip().splitlines():
                parts = line.strip().split()
                if len(parts) < 5:
                    continue
                cls_id = int(parts[0])
                cx, cy, w, h = map(float, parts[1:5])
                self.samples.append((img_path, cls_id, cx, cy, w, h))

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        img_path, cls_id, cx, cy, bw, bh = self.samples[idx]
        img = Image.open(img_path).convert("RGB")
        iw, ih = img.size

        # convert YOLO normalized coords to pixel coords
        x1 = max(0, int((cx - bw / 2) * iw))
        y1 = max(0, int((cy - bh / 2) * ih))
        x2 = min(iw, int((cx + bw / 2) * iw))
        y2 = min(ih, int((cy + bh / 2) * ih))

        crop = img.crop((x1, y1, x2, y2))
        if self.transform:
            crop = self.transform(crop)
        return crop, cls_id


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------
def build_model() -> nn.Module:
    """MobileNetV2 with a custom classification head."""
    model = models.mobilenet_v2(weights=models.MobileNet_V2_Weights.DEFAULT)
    model.classifier = nn.Sequential(
        nn.Dropout(p=0.2),
        nn.Linear(model.last_channel, NUM_CLASSES),
    )
    return model


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------
def train(args):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    # transforms
    train_tf = transforms.Compose([
        transforms.RandomResizedCrop(IMG_SIZE, scale=(0.8, 1.0)),
        transforms.RandomHorizontalFlip(),
        transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
    val_tf = transforms.Compose([
        transforms.Resize((IMG_SIZE, IMG_SIZE)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])

    train_ds = FishCropDataset(DATA_DIR / "train", transform=train_tf)
    val_ds = FishCropDataset(DATA_DIR / "valid", transform=val_tf)
    print(f"Train samples: {len(train_ds)}  |  Val samples: {len(val_ds)}")

    train_loader = DataLoader(
        train_ds, batch_size=args.batch_size, shuffle=True,
        num_workers=args.workers, pin_memory=True,
    )
    val_loader = DataLoader(
        val_ds, batch_size=args.batch_size, shuffle=False,
        num_workers=args.workers, pin_memory=True,
    )

    model = build_model().to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)
    criterion = nn.CrossEntropyLoss()

    OUTPUT_DIR.mkdir(exist_ok=True)
    best_acc = 0.0
    history = {"train_loss": [], "val_loss": [], "train_acc": [], "val_acc": []}

    for epoch in range(1, args.epochs + 1):
        # --- train ---
        model.train()
        running_loss, correct, total = 0.0, 0, 0
        for images, labels in train_loader:
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()

            running_loss += loss.item() * images.size(0)
            correct += (outputs.argmax(1) == labels).sum().item()
            total += labels.size(0)

        train_loss = running_loss / total
        train_acc = correct / total

        # --- validate ---
        model.eval()
        val_running_loss, val_correct, val_total = 0.0, 0, 0
        with torch.no_grad():
            for images, labels in val_loader:
                images, labels = images.to(device), labels.to(device)
                outputs = model(images)
                val_running_loss += criterion(outputs, labels).item() * images.size(0)
                val_correct += (outputs.argmax(1) == labels).sum().item()
                val_total += labels.size(0)

        val_loss = val_running_loss / val_total
        val_acc = val_correct / val_total
        scheduler.step()

        history["train_loss"].append(train_loss)
        history["val_loss"].append(val_loss)
        history["train_acc"].append(train_acc)
        history["val_acc"].append(val_acc)

        print(f"Epoch {epoch:3d}/{args.epochs}  "
              f"loss={train_loss:.4f}  val_loss={val_loss:.4f}  "
              f"train_acc={train_acc:.3f}  val_acc={val_acc:.3f}")

        if val_acc > best_acc:
            best_acc = val_acc
            torch.save(model.state_dict(), OUTPUT_DIR / "best.pt")
            print(f"  -> saved best model (val_acc={best_acc:.3f})")

    # save history and plots
    (OUTPUT_DIR / "history.json").write_text(json.dumps(history, indent=2))
    plot_history(history)

    print(f"\nTraining complete. Best val accuracy: {best_acc:.3f}")
    print(f"Checkpoint saved to {OUTPUT_DIR / 'best.pt'}")

    # export to ONNX
    export_onnx(model, device)


def plot_history(history: dict):
    """Save loss and accuracy curves to output/training_curves.png."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    epochs = range(1, len(history["train_loss"]) + 1)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    ax1.plot(epochs, history["train_loss"], label="Train Loss")
    ax1.plot(epochs, history["val_loss"], label="Val Loss")
    ax1.set_xlabel("Epoch")
    ax1.set_ylabel("Loss")
    ax1.set_title("Loss")
    ax1.legend()
    ax1.grid(True)

    ax2.plot(epochs, history["train_acc"], label="Train Acc")
    ax2.plot(epochs, history["val_acc"], label="Val Acc")
    ax2.set_xlabel("Epoch")
    ax2.set_ylabel("Accuracy")
    ax2.set_title("Accuracy")
    ax2.legend()
    ax2.grid(True)

    fig.tight_layout()
    path = OUTPUT_DIR / "training_curves.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"Saved training curves to {path}")


def export_onnx(model=None, device=None):
    """Export the model to ONNX for OpenCV DNN inference."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    if model is None:
        device = torch.device("cpu")
        model = build_model()
        model.load_state_dict(torch.load(OUTPUT_DIR / "best.pt", map_location=device))

    model.eval().to(device or "cpu")
    dummy = torch.randn(1, 3, IMG_SIZE, IMG_SIZE, device=device or "cpu")
    onnx_path = OUTPUT_DIR / "fish_classifier.onnx"
    torch.onnx.export(
        model, dummy, str(onnx_path),
        input_names=["input"], output_names=["output"],
        dynamic_axes={"input": {0: "batch"}, "output": {0: "batch"}},
        opset_version=11,
    )
    # save class names alongside
    (OUTPUT_DIR / "labels.txt").write_text("\n".join(CLASS_NAMES) + "\n")
    print(f"Exported ONNX model to {onnx_path}")
    print(f"Labels written to {OUTPUT_DIR / 'labels.txt'}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Train fish classifier")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--export-only", action="store_true",
                        help="Skip training, just export existing checkpoint to ONNX")
    args = parser.parse_args()

    if args.export_only:
        export_onnx()
    else:
        train(args)


if __name__ == "__main__":
    main()
