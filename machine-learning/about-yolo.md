# Fish Detection Model (YOLO)

## Purpose

Detect and classify 14 species of reef fish from underwater camera frames, producing bounding boxes and class labels for each fish in the frame. Built for real-time inference on the GOONER ROV, enabling the frontend to draw detection overlays on the video feed.

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

**YOLO11n** (nano) — the smallest variant in the Ultralytics YOLO11 family.

- Input: 320x320 RGB
- Output: per-image list of detections, each with bounding box coordinates (x1, y1, x2, y2), class ID, and confidence score
- Parameters: ~2.6M
- FLOPs: ~6.5G (at 640px; lower at 320px)

YOLO11n is a single-stage anchor-free detector. It processes the full image in one forward pass and outputs all detections simultaneously, unlike two-stage detectors that propose regions first. The nano variant prioritizes speed over accuracy, making it suitable for CPU-only real-time inference on the ROV laptop.

### Why YOLO11n over the MobileNetV2 classifier

The previous model (`train.py` / `about.md`) is a classifier — it takes a single image and outputs one class label. It cannot locate fish within a frame or handle multiple fish at once. YOLO11n is an object detector: it outputs bounding box coordinates and class labels for every fish in the frame, which is what the frontend needs to draw detection overlays.

### Why 320px input

The source images are 640x640, but the ESP32-CAM captures at 640x480. Using 320px input:
- Reduces inference time by ~4x compared to 640px (input area is quartered)
- Matches the limited detail available from the ESP32-CAM at underwater distances
- Still large enough for the model to detect fish that occupy a reasonable portion of the frame

## Dataset

Source: [Roboflow Fish Detection](https://universe.roboflow.com/zehra-acer/fish-detection-fztlb/dataset/5) (CC BY 4.0) — YOLO object detection format with bounding box annotations on 640x640 images.

An additional lionfish-only classification dataset (`lionfish-dataset.zip`) was merged in using `merge_lionfish.py`. Since those images had no bounding box annotations, each was assigned a full-image bounding box (`0.5 0.5 1.0 1.0`) as class 13.

### Split sizes

| Split | Images | Labels |
|-------|--------|--------|
| Train | 7,606 | 7,606 |
| Valid | 837 | 837 |
| Test | 1,098 | 1,098 |

### Label format

Each `.txt` label file contains one line per object: `class_id cx cy w h` in YOLO normalized coordinates (0-1 relative to image dimensions). Unlike the classifier pipeline, the YOLO detector uses these bounding boxes directly — no cropping is needed.

## Training

```bash
pip install ultralytics matplotlib
python train_yolo.py                        # train with defaults (50 epochs, 320px, yolo11n)
python train_yolo.py --epochs 100           # more epochs
python train_yolo.py --model yolo11s        # larger model variant
python train_yolo.py --imgsz 640            # train at full resolution
python train_yolo.py --export-only          # export existing best.pt to ONNX
```

### Training details

- Base model: YOLO11n pretrained on COCO
- Input size: 320x320
- Batch size: 16
- Default epochs: 50
- Augmentation: Ultralytics built-in (mosaic, mixup, HSV jitter, flips, scaling, translation)
- Validation: runs every epoch

### Tracked metrics

The training script parses the Ultralytics `results.csv` and saves a `history.json` with per-epoch values for:

| Metric | Description |
|--------|-------------|
| `train_box_loss` | Bounding box regression loss (train) |
| `train_cls_loss` | Classification loss (train) |
| `train_dfl_loss` | Distribution focal loss (train) |
| `val_box_loss` | Bounding box regression loss (val) |
| `val_cls_loss` | Classification loss (val) |
| `val_dfl_loss` | Distribution focal loss (val) |
| `mAP50` | Mean average precision at IoU=0.50 |
| `mAP50-95` | Mean average precision at IoU=0.50:0.95 |
| `precision` | Detection precision |
| `recall` | Detection recall |

A 4-panel `training_curves.png` is generated with: training loss, validation loss, mAP, and precision/recall over epochs.

Ultralytics also auto-generates its own plots in `output-yolo/train/`, including confusion matrix, PR curve, F1 curve, and per-class results.

## Output files

All outputs are saved to `output-yolo/`:

| File | Description |
|------|-------------|
| `best.pt` | Best YOLO weights (by val mAP) |
| `best.onnx` | ONNX export for deployment |
| `labels.txt` | Class names, one per line |
| `history.json` | Per-epoch metrics for custom graphing |
| `training_curves.png` | 4-panel loss/mAP/precision/recall plot |
| `data.yaml` | Dataset config with absolute paths |
| `train/` | Full Ultralytics output (weights, plots, results.csv) |

## Evaluation

After training, Ultralytics reports mAP@50 and mAP@50-95 on the validation set each epoch. To run evaluation separately:

```python
from ultralytics import YOLO
model = YOLO("output-yolo/best.pt")
metrics = model.val(data="output-yolo/data.yaml", imgsz=320)
```

## Design choices

1. **Detection over classification**: The frontend needs to draw bounding boxes around fish in the video feed. A classifier can only label the whole frame; a detector outputs box coordinates for each fish, supporting multi-fish scenes and spatial overlays.

2. **YOLO11n**: The nano variant has ~2.6M parameters — small enough for real-time CPU inference on the ROV laptop. YOLO11 improves on YOLOv8 with better feature extraction at similar model sizes.

3. **320px input resolution**: Halving the default 640px cuts inference time ~4x while retaining enough spatial resolution for the ESP32-CAM feed. The camera captures at 640x480 in challenging underwater conditions where fine detail is already limited by water clarity.

4. **Single-stage anchor-free design**: YOLO11 is anchor-free, removing the need to tune anchor box priors for fish-shaped objects. It predicts box offsets and class probabilities in a single pass, keeping latency low.

5. **Full-image bounding boxes for lionfish**: The lionfish dataset had no annotations, so `merge_lionfish.py` assigns each image a full-frame bounding box. For YOLO training this means the model learns lionfish as a large centered object — acceptable because those images are already tightly framed around the subject, and it teaches the model the lionfish appearance even if the box isn't tight.

6. **ONNX export**: The trained model is exported to ONNX for deployment with OpenCV DNN, keeping the inference stack lightweight (no PyTorch or Ultralytics needed at runtime).
