# Arduino serial controller (runs on laptop)
# Receives motor commands from main.py and sends to Arduino over serial

import serial
import serial.tools.list_ports

BAUD_RATE = 115200

# key -> serial command byte
KEY_MAP = {
    ord("w"): b"F",  # forward
    ord("s"): b"B",  # backward
    ord("a"): b"L",  # left
    ord("d"): b"R",  # right
}
STOP_CMD = b"S"


def find_arduino(preferred_port: str | None = None) -> str | None:
    """Return the serial port for an Arduino, or preferred_port if given."""
    if preferred_port:
        return preferred_port
    for port in serial.tools.list_ports.comports():
        if "Arduino" in (port.description or "") or "ttyACM" in (port.device or ""):
            return port.device
    return None


class ArduinoController:
    """Manages serial connection and translates commands to motor signals."""

    def __init__(self, port: str | None = None):
        self.ser = None
        device = find_arduino(port)
        if device is None:
            print("Warning: no Arduino found — running without motor control")
            return
        self.ser = serial.Serial(device, BAUD_RATE, timeout=1)
        print(f"Connected to Arduino on {device}")

    def send(self, cmd: bytes):
        if self.ser and self.ser.is_open:
            self.ser.write(cmd)

    def handle_key(self, key: int):
        """Send the matching motor command for a key press, or stop."""
        cmd = KEY_MAP.get(key)
        if cmd:
            self.send(cmd)

    def stop(self):
        """Send stop command."""
        self.send(STOP_CMD)

    def close(self):
        if self.ser and self.ser.is_open:
            self.stop()
            self.ser.close()
