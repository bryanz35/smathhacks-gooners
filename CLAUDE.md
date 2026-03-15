# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**GOONER** (Guided Ocean Observation and Navigation Explorer Rover) — an underwater ROV that detects invasive coral reef species (lionfish, crown-of-thorns starfish). The system has two active subsystems plus a machine learning pipeline:

- **Python** (`python/`): Runs on the laptop — Flask web server with MJPEG video feed from an ESP32-CAM, browser-based WASD control, and Arduino serial motor commands
- **Arduino** (`arduino/`): Two sketches — `arduino.ino` for motor control via serial, `goonsenses/goonsenses.ino` for water quality monitoring (TDS + temperature sensors + dual pumps via Adafruit Motor Shield V3)
- **Machine Learning** (`machine-learning/`): TFLite model training data (lionfish images in train/test/valid splits). The exported model is `fish_model.tflite` at the repo root.

The `raspberrypi (deprecated)/` directory contains the old Pi-based architecture and is no longer active.

## Setup & Run

```bash
# activate the venv and install deps
source .env/bin/activate
pip install -r python/requirements.txt

# run the Flask web UI (connects to ESP32-CAM + Arduino over USB)
python python/app.py
# opens on http://localhost:8080 — WASD keys control motors, video streams in the browser
```

`python/main.py` is an older Tkinter-based GUI that connects to a Raspberry Pi over TCP (ports 5000/5001). Use `app.py` for the current Flask-based setup.

`python/camera.py` is a standalone utility to test ESP32-CAM video capture.

Arduino sketches are uploaded via the Arduino IDE. `goonsenses/` requires the OneWire, DallasTemperature, and Adafruit Motor Shield libraries.

## Architecture

### Flask app (`python/app.py`) — current primary interface

The laptop connects directly to hardware over USB:
- **ESP32-CAM**: OpenCV `VideoCapture` grabs MJPG frames, served as MJPEG stream at `/video_feed`
- **Arduino**: `ArduinoController` (`python/input.py`) sends single-byte serial commands over USB at 115200 baud
- **Browser frontend** (`python/frontend/`): `home.html` + `home.js` — fullscreen video feed with WASD keypress handling via `POST /command`

### Serial Protocol

Single ASCII bytes at 115200 baud (Flask app) or 9600 baud (old `arduino.ino`): `F`=forward, `B`=backward, `L`=left, `R`=right, `S`=stop.

**Important**: The serial port is hardcoded in `app.py` as `/dev/cu.usbmodem1101` (macOS). Change `SERIAL_PORT` and the `ArduinoController(port=...)` call for your system.

### Detection model (`python/model.py`)

OpenCV Caffe DNN — expects `model.caffemodel`, `model.prototxt`, and `labels.txt` in the `python/` directory. Not currently wired into `app.py`; the detect/draw pipeline is ready but needs integration.

### Network Protocol (legacy, `python/main.py` only)

The old Tkinter GUI connects to a Raspberry Pi over a direct Ethernet cable:
- Laptop: `192.168.1.1`, Pi: `192.168.1.2`
- Video stream (port 5000): length-prefixed JPEG frames
- Command stream (port 5001): single ASCII command bytes
