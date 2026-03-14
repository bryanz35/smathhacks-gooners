# Guide Ocean Observation and Navigation Explorer Rover (GOONER)

Project: small submersible that takes images and detects invasive
species in coral reefs.

Setup:
Laptop: Runs main python script, opens gui and allows user keyboard control.
Communicates with raspberry pi
Raspberry PI: Runs opencv image detection and controls arduino. Communicates with
cameras.
Arduino uno: manages sensors and motors (but not cameras)
