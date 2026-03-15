# Guided Ocean Observation and Navigation Exploration Rover (GOONER)

## Introduction

Hello guys! This Devpost page shows all of our documentation for the SMathHacks
2026 hackathon! The project we created is called Guided Ocean Observation and
Navigation Exploration Rover (GOONER), and we decided to go the hardware track
for this hackathon. GOONER utilizes an Arduino Uno R3 and ESP32 Feather to
create a small submersible that records images through cameras and sensors,
allowing us to detect invasive species in coral reefs.

This project is brought to you by four students attending the North Carolina
School of Science and Mathematics (NCSSM). Our team members include Michael
Chen, Anderson Lam, Bryan Zhong, and Linda Duong!

## Abstract

Guided Ocean Observation and Navigation Exploration Rover (GOONER) is a
controllable submersible that allows researchers to collect diagnostic data and
monitor coral reef health.

GOONER is able to be placed completely underwater without damage to components.
It features a Total Dissolved Solids (TDS) sensor and a temperature sensor,
allowing us to monitor water conditions at different locations. Two ESP32-CAM
cameras on the submersible provide the ability to capture underwater images for
both navigation and identification of invasive species. We also used two pumps
to ensure this submersible could stay in and move in water.

Our project also includes a custom YOLO image classification model for instant
identification of invasive species and a website frontend that allows users to
control the rover and see live video along with fish classification.



## Rationale

Talk about why we did this project, and why it’s important (invasive species,
conversation with Dr. Love)

One of the biggest issues coral reefs face is the addition of invasive species.
For example, researchers have found that a single lionfish living on a coral
reef can reduce recruitment of native reef fish by 79 percent. Current solutions
include incentivizing fishermen to catch invasive species or using biodegradable
compounds to kill invasive species, but these can be inefficient or harmful to
other reef wildlife. Submersibles have entered the limelight as a non-invasive
method of monitoring or even removing invasive species due to their small size
and maneuverability. As a result, we wanted to construct a submersible that
could both monitor environmental factors that could affect reef health and
search for invasive species.

Part of this project was greatly encouraged by Dr. Love, the NCSSM dean of
engineering and computer science. This faculty member spoke to us while
brainstorming and encouraged us to look into Colin Angle, his previous classmate
at MIT and cofounder and CEO of iRobot. Colin and his wife, Erika Angle, founded
a nonprofit called Robots in Service of the Environment (RSE) whose mission is
to solve environmental issues through robotics. They have been working on a
submersible robot, Guardian LF1, that targets lionfish, an invasive species that
is native to the Indian and Pacific Oceans but have been invading Atlantic
waters. With no natural predators here, their population is continuously
expanding and consuming ocean life, bringing harm to coral reef systems.
Guardian LF1 is working to kill these invasive fish through submersibles that
capture and kill the lionfish by zapping them with electricity.

After doing research on these lionfish-targeting robots, we decided to do
something similar. We wanted to both monitor the water and identify whether or
not invasive species were present. Not only would this allow us to find if there
are lionfish present, similar to the Angle's Guardian LF1, but would also
provide up-to-date information about water quality that can determine if coral
reefs are in danger.

In order to make it easier for researchers to control the submersible, we design
a website frontend that displays video from the submersible camera, indicators
from sensor modules, and allows for keyboard input to control submersible
propulsion.

We also train an image classification model to identify and draw bounding boxes
around fish. This serves as a proof-of-concept for an automated invasive fish
identifier.

We discuss the integration of these components in the sections below.

## High Level Overview

GOONER consists of three main parts: Submersible hardware and code, invasive
fish image classification model, and a website that incorporates a flask backend
with HTML/CSS/JS frontend.

// TODO: create and insert diagram

## Frontend

The frontend is a minimal HTML/CSS/JS interface designed to give the operator a
live view of the underwater camera. It consists of two files: `home.html` and
`home.js`, served as static assets by the Flask backend.

`home.html` renders a single `<img>` element pointing at the `/video_feed`
endpoint. We use CSS to set the image to fill the entire viewport, which
creates a fullscreen view.

`home.js` handles keyboard input for motor control. It maintains a `Set` of
currently pressed keys to track multi-key state. On `keydown`, if the key is one
of W/A/S/D and not already held, it sends a `POST /command` to the backend.
On `keyup`, it removes the key from the set and only sends a
`"stop"` command when all keys have been released. This means the rover keeps
moving as long as any directional key is held, and only stops when the operator
lifts all fingers.

## Backend

The backend is a Flask application (`app.py`). It has three responsibilities:
serving the video stream, forwarding motor commands, and
running the YOLO detection model.

**Video streaming:** A background thread (`capture_loop`) grabs
MJPEG (motion JPEG) frames from the ESP32-CAM using OpenCV's `VideoCapture`.
When the browser requests `/video_feed`, the backend reads each frame, runs
the YOLO classification model on it, draws bounding boxes, converts result to JSON,
and sends it to the frontend as a MJPEG stream. This gives the frontend access
to all future camera updates.

**Motor control:** The `/command` POST endpoint receives JSON from the
frontend keyboard handler. It maps key names to ASCII commands
(`w`→`F`, `a`→`L`, `s`→`B`, `d`→`R`) and sends them to the Arduino
via the `ArduinoController` class (defined in `input.py`). The Arduino reads
these bytes and drives the motors accordingly. The serial connection runs at
115200 baud.

**Detection model integration:** At startup, `app.py` loads the YOLO .ONNX model
from `machine-learning/output-yolo/best.onnx`, which is the best model from
training (see section below). Every frame in the MJPEG
stream passes through `detect()` and `draw_detections()` before being sent to
the browser. Invasive species (lionfish) are highlighted with red bounding
boxes; all other detected fish get green boxes.

## Fish Detection Classification Model (YOLO)

We built a fish detection model that identifies 14 species of reef fish from
live underwater camera frames. The model produces bounding boxes and class
labels for every fish visible in a frame, which the Flask backend draws onto
the video stream before sending it to the frontend. We chose a lightweight
architecture so the model can run in real time on a laptop CPU, with the goal
of eventually migrating inference to a Raspberry Pi onboard the submersible.

### Classes (14)

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

### Architecture

The model uses **YOLO11n** (nano), the smallest variant in the Ultralytics
YOLO11 family. It takes 320x320 RGB input and produces a list of detections,
each with bounding box coordinates, a class ID, and a confidence score.
It is small enough to run CPU-only on a laptop or Raspberry Pi (see future work).

YOLO11n is a single-stage anchor-free detector, meaning it processes the full
image in one forward pass and outputs all detections simultaneously.
This makes YOLO a good choice for live image labeling.

We originally trained a MobileNetV2 classifier (`train.py` / `about.md`), but
that approach only outputs one class label per image — it cannot locate fish
within a frame or handle multiple fish at once. Switching to YOLO gave us
bounding box coordinates for every fish in the frame, which is what the
frontend needs to draw detection overlays.

We use 320px input rather than the default 640px because the ESP32-CAM only
captures at 640x480, and underwater conditions already limit fine detail.
Halving the resolution reduces inference time by roughly 4x while retaining
enough spatial information for reliable detection.

### Dataset

The primary dataset comes from [Roboflow Fish Detection](https://universe.roboflow.com/zehra-acer/fish-detection-fztlb/dataset/5),
which provides YOLO-format bounding box annotations on 640x640 images.

Because the Roboflow dataset did not include any lionfish examples, we
supplemented it with a [lionfish-only classification dataset](https://images.cv/dataset/lionfish-image-classification-dataset).
Those images had no bounding box annotations, so `merge_lionfish.py` assigns
each one a full-image bounding box (`0.5 0.5 1.0 1.0`) as class 13 while merging
the two datasets.
The images in this set are all centered with the lionfish filling most of the frame,

The combined dataset is split as follows:

| Split | Images | Labels |
|-------|--------|--------|
| Train | 7,606 | 7,606 |
| Validation | 837 | 837 |
| Test | 1,098 | 1,098 |

![Label Distribution](https://github.com/bryanz35/smathhacks-gooners/blob/master/doc-images/label_histogram.png?raw=true)

### Training

Training is handled by `train_yolo.py`, which wraps the Ultralytics training
API. We fine-tuned from a YOLO11n checkpoint pretrained on COCO, training for
50 epochs at 320x320 input with a batch size of 16.

An example training batch is shown below:
![Training batch](https://github.com/bryanz35/smathhacks-gooners/blob/master/doc-images/train_batch19040.jpg?raw=true)

During the training process, we track model training/validation loss, precision,
and recall. Below shows the training logs of our model:
![Training Logs](https://github.com/bryanz35/smathhacks-gooners/blob/master/doc-images/training_curves.png?raw=true)
### Output

Training produces the following artifacts in `machine-learning/output-yolo/`:

| File | Description |
|------|-------------|
| `best.pt` | Best YOLO weights (selected by validation mAP) |
| `best.onnx` | ONNX export used by the Flask backend at runtime |
| `labels.txt` | Class names, one per line |
| `history.json` | Per-epoch metrics for custom graphing |
| `training_curves.png` | 4-panel loss/mAP/precision/recall plot |
| `data.yaml` | Dataset config with absolute paths |
| `train/` | Full Ultralytics output (weights, plots, results.csv) |

![Confusion Matrix](https://raw.githubusercontent.com/bryanz35/smathhacks-gooners/refs/heads/master/doc-images/confusion_matrix.png)
The deployed model is `best.onnx`, which the backend loads via OpenCV DNN so
that neither PyTorch nor Ultralytics are needed at runtime.

### Design choices

We made several design choices when building our model:

We chose YOLO over a traditional classifier because the frontend needs to draw
bounding boxes around individual fish. A classifier can only label the whole
frame, while YOLO outputs coordinates and labels for every detected object.
Within the YOLO family, we selected YOLO11n (nano) for its small size (~2.6M
parameters) and single-pass inference, both of which are important for
maintaining low latency on the live video feed. YOLO11 also improves on YOLOv8
with better feature extraction at similar model sizes.

The full-image bounding boxes assigned to lionfish images are a
limitation because the supplemental lionfish dataset had no annotations.
`merge_lionfish.py` assigns each image a full-frame box, so the model learns
lionfish as a large centered object. This is acceptable for now since the rover
is still human-operated, but in the future we would add synthetic variation to
improve detection at different scales and positions.

We export the final model to ONNX so the Flask backend can load it through
OpenCV DNN without requiring PyTorch or Ultralytics at runtime, which reduces
the deployment footprint.

## Sensors and capabilities

talk about the sensors on it, what they can measure (tuff ahh table) and then
how the thing is controlled maybe idek. The parts we used

| Hardware | Model | Parameters Measured | Communication |
| --------------------- | ------------------- | ------------------------ | ------------------ |
| Temperature Sensor | DS18B20 | Temperature (°C) | Digital |
| Total Dissolved Solids Sensor | DFRobot Gravity: Analog TDS Meter 1.0 | Parts per Million (ppm)| Analog |
| Cameras | ESP32-CAM | Detection of Invasive Species | Digital |


With the temperature sensor on our project, we are able to detect the
temperature of water. As coral reefs tend to have a low tolerance for
temperature variations, especially without time to adjust, we can provide early
warnings for when reefs could become vulnerable to heat stress and coral
bleaching, which can eventually lead to coral reef deaths.

The TDS sensor on GOONER measures the materials dissolved in water that are not
pure H2O molecules. In GOONER, the TDS sensor monitors the water quality in
parts per million, which tells us if there are contaminants present in specific
areas that could have coral bleaching. This would typically include aquariums
and reef tanks, which would ideally have a value of zero. Having low water
quality can stunt coral growth or damage it, but GOONER is able to identify
these water quality levels and can tell us when there are too many contaminants
in the water before it becomes too late.

GOONER uses two ESP32-CAM cameras. With these cameras, we are able to not only
take and save underwater images, but we can also look at the area around coral
reefs specifically. Our cameras are used to detect varying species' of fish and
can identify invasive species, like Lionfish. More details will be provided
later in this documentation.

Connecting everything together is an Arduino Uno, with a shield for expanded
capabilities. The Arduino connects and manages all of the sensors and motors
involved in the project, while the cameras are connected to a laptop. Some of
the other things in our project include pumps to ensure our submersible stays in
the water, an Adafruit Feather for Wi-Fi purposes, and a battery pack for power.

## Electrical Engineering

Below is KiCad render of our wiring diagram:
![Wiring diagram](https://github.com/bryanz35/smathhacks-gooners/blob/master/doc-images/wiring.png?raw=true)


## Impact

ROV’s impact, positive benefits to society


Coral reefs provide homes to more than 25% of marine life on Earth. With this
project, we want to not only improve underwater life, but we also ensure the
entire world and the people in it are not at risk from the lack of coral reefs.
After all, coral reefs also protect carbon dioxide-absorbing habitats, reduce
impact from severe weather, and help provide millions of people with food and
jobs.

Part of keeping coral reefs alive and thriving is understanding what harms them
in the first place, so one of our main goals is to detect invasive species on
coral reefs.


## Future Work

Future work focuses on improving user control of the rover by adding more
propulsion sources, which would allow for up-down turning instead of only
left-right turning. We hope to improve our rover speed by switching out the
tupperware case with a sleeker design (see reference sketch) and improving the
output of our propulsion system.

Additionally, we hope to move the image classification model along with camera
input handling to a raspberry pi, which will sit inside the submersible and
communicate with both the arduino and laptop/web server for key input.

We also have room for additional diagnostic modules on the submersible to better
measure coral reef health. These would include a water pH sensor, a pump for
water quality sampling, and a flashlight module for nighttime/cave exploration.

There is currently no solution for long-distance wireless underwater
communication. Technology is currently being developed by MIT researchers, but
we anticipate several years of research before a fully wireless rover is
feasible.

// TODO: add image caption and markdown embed
