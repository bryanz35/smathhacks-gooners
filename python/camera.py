import serial
import cv2
import numpy as np
import struct
import time

PORT = '/dev/cu.usbserial-2130'
BAUD = 115200

ser = serial.Serial(PORT, BAUD)
print("Connected, flushing buffer...")
time.sleep(2)
ser.reset_input_buffer()
print("Waiting for frames...")

while True:
    # Read 4 bytes for frame length
    raw_len = ser.read(4)
    frame_len = struct.unpack('<I', raw_len)[0]
    
    print(f"Frame size: {frame_len} bytes")
    
    if frame_len > 100000 or frame_len < 100:
        print("Bad frame size, skipping...")
        ser.reset_input_buffer()
        continue
    
    # Read the frame data
    frame_data = ser.read(frame_len)
    
    # Decode JPEG
    np_arr = np.frombuffer(frame_data, dtype=np.uint8)
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    
    if img is not None:
        cv2.imshow('ESP32-CAM', img)
        print("Frame displayed!")
    else:
        print("Failed to decode frame")
    
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

ser.close()
cv2.destroyAllWindows()