# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Underwater ROV for detecting invasive coral reef species. The system has three components:
- **Python** (`python/`): Tkinter GUI on the laptop for viewing the video feed and sending WASD commands over the network to the Raspberry Pi
- **Raspberry Pi** (`raspberrypi/`): Runs on the Pi — captures camera, runs OpenCV DNN-based species detection, streams annotated video to the laptop, and controls the Arduino over serial
- **Arduino** (`arduino/`): Motor driver firmware for Arduino Uno R3, controlled via serial commands from the Raspberry Pi

## Setup & Run

### Laptop (Python GUI)

```bash
# activate the venv and install deps
source .env/bin/activate
pip install -r python/requirements.txt

# run the GUI (connects to Raspberry Pi)
python python/main.py
```

### Raspberry Pi

```bash
pip install -r raspberrypi/requirements.txt

# run the Pi server (captures camera, streams video, controls Arduino)
python raspberrypi/main.py
```

The Arduino sketch (`arduino/arduino.ino`) is uploaded via the Arduino IDE.

## Architecture

The laptop and Raspberry Pi communicate over TCP:
- **Video stream** (port 5000): Pi sends length-prefixed JPEG frames to the laptop
- **Command stream** (port 5001): Laptop sends single ASCII command bytes to the Pi

### Laptop (`python/`)
- **main.py** — Tkinter GUI that receives video frames from the Pi and displays them. Captures WASD keypresses and sends motor commands (`F`/`B`/`L`/`R`/`S`) to the Pi over TCP.

### Raspberry Pi (`raspberrypi/`)
1. **main.py** — entry point: starts the video server and command server, loads the detection model, initializes the Arduino controller
2. **model.py** — loads an OpenCV Caffe DNN model (`model.caffemodel`, `model.prototxt`, `labels.txt`) and provides `detect()` / `draw_detections()` for identifying invasive species in camera frames
3. **input.py** — `ArduinoController` class that auto-detects the Arduino serial port and forwards motor commands over serial

### Arduino (`arduino/`)
- **arduino.ino** — reads serial commands and drives 4 PWM motor pins (3, 5, 6, 9) for left/right forward/backward

## Serial Protocol

Raspberry Pi sends single ASCII bytes to Arduino over 9600 baud: `F`=forward, `B`=backward, `L`=left, `R`=right, `S`=stop.

## Network Protocol

The laptop and Pi are connected via a direct Ethernet cable with static IPs:
- Laptop: `192.168.1.1`
- Raspberry Pi: `192.168.1.2`

Change `PI_HOST` in `python/main.py` if using a different IP. See `raspberrypi/setup_network.sh` for Pi-side network configuration.
