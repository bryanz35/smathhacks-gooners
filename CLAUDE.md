# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**GOONER** (Guided Ocean Observation and Navigation Explorer Rover) — an underwater ROV that detects invasive coral reef species (lionfish, crown-of-thorns starfish). Three active subsystems:

- **Python** (`python/`): Laptop-side Flask web server — MJPEG video from ESP32-CAM with real-time YOLO object detection, browser WASD motor control via Arduino serial
- **Arduino** (`arduino/`): `goonarduino/goonarduino.ino` is the unified sketch (motors + TDS + temperature sensors). `arduino.ino` is a simpler motor-only sketch. `goonsenses/goonsenses.ino` is a sensors-only sketch with dual pumps.
- **Machine Learning** (`machine-learning/`): YOLO model training pipeline. The deployed model is `machine-learning/output-yolo/best.onnx` with `labels.txt` in the same directory.

`raspberrypi (deprecated)/` and `python/main.py` (old Tkinter GUI) are legacy — not active.

## Setup & Run

```bash
source .env/bin/activate
pip install -r python/requirements.txt
# requirements.txt only lists flask and Pillow; you also need:
# pip install opencv-python pyserial numpy

python python/app.py
# serves on http://localhost:8080 — WASD keys control motors, video streams with YOLO detections
```

Arduino sketches are uploaded via Arduino IDE. `goonarduino/` requires OneWire, DallasTemperature, and Adafruit Motor Shield V3 libraries.

## Architecture

### Data flow

```
Browser (home.html + home.js)
  ├── GET /video_feed ← MJPEG stream ← capture_loop() ← ESP32-CAM (OpenCV VideoCapture)
  │                      with YOLO detections drawn per-frame (model.py detect + draw_detections)
  └── POST /command {key} → app.py → ArduinoController.send() → serial byte → Arduino
```

### Hardcoded ports (must change per system)

- **Serial port**: `SERIAL_PORT` in `app.py` line 12 and `ArduinoController(port=...)` call on line 108 — currently `/dev/cu.usbmodem1101` (macOS)
- **Camera port**: `capture_loop()` is called with a port/index — currently hardcoded in `app.py`

### Serial protocol

Single ASCII bytes at 115200 baud: `F`=forward, `B`=backward, `L`=left, `R`=right, `S`=stop.

### YOLO detection model (`python/model.py`)

Loads `machine-learning/output-yolo/best.onnx` via OpenCV DNN. Runs per-frame in `generate_frames()`. Detection thresholds: confidence 0.5, NMS 0.45, input size 320x320. Invasive species (lionfish) get red bounding boxes; others get green.

### Frontend (`python/frontend/`)

`home.html` + `home.js` — fullscreen video with WASD keypress handling. Key-down sends the direction, key-up sends "stop" only when all keys are released (supports holding multiple keys).

### ML training (`machine-learning/`)

- `train_yolo.py` / `train.py` — training scripts
- `merge_lionfish.py` — dataset merging utility
- `conf_matrix_gen.py` / `label_histogram.py` — evaluation visualization
- Training data goes in `machine-learning/data/` (gitignored)
- Trained output in `machine-learning/output-yolo/` (best.onnx, labels.txt, metrics)
