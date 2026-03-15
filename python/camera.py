import cv2
import numpy as np
import serial
import sys

SERIAL_PORT = "/dev/cu.usbserial-110"
BAUD_RATE = 115200

def main():
    port = sys.argv[1] if len(sys.argv) > 1 else SERIAL_PORT
    print(f"Opening ESP32-CAM on {port} ...")
    
    ser = serial.Serial(port, BAUD_RATE, timeout=5)
    print("Connected. Press 'q' to quit.")

    while True:
        # Read 4-byte frame length
        raw_len = ser.read(4)
        if len(raw_len) < 4:
            print("Timeout waiting for frame length")
            continue
        
        frame_len = int.from_bytes(raw_len, byteorder='little')
        
        # Sanity check — reject obviously wrong sizes
        if frame_len < 100 or frame_len > 100_000:
            print(f"Bad frame length: {frame_len}, resyncing...")
            ser.reset_input_buffer()
            continue
        
        # Read the JPEG data
        jpeg_data = ser.read(frame_len)
        if len(jpeg_data) < frame_len:
            print("Incomplete frame, skipping")
            continue

        # Decode and display
        frame = cv2.imdecode(np.frombuffer(jpeg_data, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            print("Failed to decode frame")
            continue

        cv2.imshow("ESP32-CAM", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    ser.close()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()