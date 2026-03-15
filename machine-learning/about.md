# Fish Classification Model

## Purpose

Classify 14 species of reef fish from underwater camera frames to identify invasive species (primarily lionfish). Built for real-time inference on the GOONER ROV.

## Classes (14)

| ID | Species | Invasive? |
|----|---------|-----------|
| 0 | AngelFish | No |
| 1 | BlueTang | No |
| 2 | ButterflyFish | No |
| 3 | ClownFish | No |
| 4 | GoldFish | No |
| 5 | Gourami | No |
| 6 | MorishIdol | No |
| 7 | PlatyFish | No |
| 8 | RibbonedSweetlips | No |
| 9 | ThreeStripedDamselfish | No |
| 10 | YellowCichlid | No |
| 11 | YellowTang | No |
| 12 | ZebraFish | No |
| 13 | Lionfish | Yes |

## Architecture

**MobileNetV2** (ImageNet-pretrained) with a replaced classification head:

```
MobileNetV2 backbone (frozen ImageNet features)
  -> Dropout(0.2)
  -> Linear(1280, 14)
```

- Input: 128x128 RGB, normalized with ImageNet mean/std
- Output: 14-class softmax logits
- Designed for fast inference on resource-constrained hardware (Raspberry Pi / laptop CPU)

## Dataset

Source: [Roboflow Fish Detection](https://universe.roboflow.com/zehra-acer/fish-detection-fztlb/dataset/5) (CC BY 4.0) — a YOLO object detection dataset with bounding box annotations on 640x640 images.

An additional lionfish-only classification dataset (`lionfish-dataset.zip`) was merged in using `merge_lionfish.py`. Since those images had no bounding boxes, each was assigned a full-image bounding box (`0.5 0.5 1.0 1.0`) as class 13.

### Split sizes

| Split | Images | Labels |
|-------|--------|--------|
| Train | 7,606 | 7,606 |
| Valid | 837 | 837 |
| Test | 1,098 | 1,098 |

### Detection-to-classification conversion

The dataset is YOLO detection format (images + per-image `.txt` label files with `class cx cy w h`). At training time, `FishCropDataset` in `train.py` crops each bounding box on the fly and yields individual crops as classification samples. No pre-cropped dataset is stored on disk.

## Training

```bash
pip install torch torchvision matplotlib
python train.py                  # train with defaults (20 epochs)
python train.py --epochs 30      # customize
python train.py --export-only    # export existing checkpoint to ONNX
```

- Optimizer: Adam, lr=1e-3
- Scheduler: CosineAnnealingLR over the full epoch count
- Batch size: 64
- Augmentation (train only): RandomResizedCrop, horizontal flip, color jitter

Training saves `output/best.pt` (best validation accuracy checkpoint), `output/training_curves.png`, and `output/history.json`.

## Export formats

| File | Format | Size | Use case |
|------|--------|------|----------|
| `output/best.pt` | PyTorch state dict | ~9 MB | Resume training |
| `output/fish_classifier.onnx` + `.onnx.data` | ONNX (opset 11) | ~9 MB | OpenCV DNN inference |
| `fish_model.tflite` (repo root) | TFLite | ~9 MB | Edge deployment |

The ONNX export is done automatically at the end of training. `output/labels.txt` is written alongside it for inference-time class name lookup.

## Evaluation

```bash
pip install opencv-python numpy onnxruntime
python test_model.py                     # validate on valid split
python test_model.py --split test        # evaluate on test split
```

Uses only OpenCV + NumPy + ONNX Runtime (no PyTorch), so it can run on the Pi.

Outputs per-class accuracy and a confusion matrix saved to `output/confusion_matrix.csv`.

### Validation results (from confusion matrix)

Most classes achieve very high accuracy. Notable observations:
- **ZebraFish** has the most confusion — 25 of 259 samples misclassified, mostly as Gourami (14) or GoldFish (6)
- **YellowCichlid** is sometimes confused with ButterflyFish (9 of 95)
- **Lionfish** classifies well: 136/137 correct (99.3%)

## Design choices

1. **Classification over detection**: The ROV camera produces a single centered subject per frame in practice. A lightweight classifier is faster and simpler than running a full object detector at inference time. The YOLO bounding boxes are only used during training to crop training samples.

2. **MobileNetV2**: Chosen for its low parameter count (~3.4M) and fast inference, suitable for CPU-only deployment on a Raspberry Pi or laptop without a GPU.

3. **128x128 input resolution**: Smaller than the typical 224x224 to further reduce inference latency. Acceptable because fish crops from 640x640 source images retain enough detail at this size.

4. **On-the-fly cropping**: Rather than pre-generating a cropped dataset, `FishCropDataset` crops bounding boxes at load time. This avoids storing a second copy of the data and makes it easy to re-run with different augmentations.

5. **Full-image bounding boxes for lionfish**: The lionfish dataset had no annotations, so `merge_lionfish.py` assigns each image a full-frame bounding box. This works because those images are already tightly framed around the subject.
