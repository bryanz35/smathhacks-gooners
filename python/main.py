# Main script (runs on laptop)
"""
Functionality:
 - GUI (receives video stream from Raspberry Pi)
 - Keyboard input - WASD sent to Raspberry Pi over network
"""

import socket
import struct
import threading
import tkinter as tk
from PIL import Image, ImageTk
import io

UPDATE_MS = 30  # milliseconds between frame updates
PI_HOST = "192.168.1.2"  # static IP of the Raspberry Pi (wired Ethernet)
VIDEO_PORT = 5000
CMD_PORT = 5001


def main():
    root = tk.Tk()
    root.title("Coral Reef Monitor")
    video_label = tk.Label(root)
    video_label.pack()

    status_label = tk.Label(root, text="Connecting to Raspberry Pi...", fg="orange")
    status_label.pack()

    latest_frame = [None]
    connected = [False]

    # --- video receiver thread ---
    def receive_video():
        while True:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((PI_HOST, VIDEO_PORT))
                connected[0] = True
                buf = b""
                while True:
                    # read 4-byte length prefix
                    while len(buf) < 4:
                        chunk = sock.recv(4096)
                        if not chunk:
                            raise ConnectionError("lost connection")
                        buf += chunk
                    length = struct.unpack(">I", buf[:4])[0]
                    buf = buf[4:]

                    # read JPEG frame
                    while len(buf) < length:
                        chunk = sock.recv(65536)
                        if not chunk:
                            raise ConnectionError("lost connection")
                        buf += chunk
                    jpg_data = buf[:length]
                    buf = buf[length:]

                    img = Image.open(io.BytesIO(jpg_data))
                    latest_frame[0] = img
            except Exception as e:
                connected[0] = False
                print(f"Video connection error: {e}, retrying...")
                import time
                time.sleep(2)

    video_thread = threading.Thread(target=receive_video, daemon=True)
    video_thread.start()

    # --- command socket ---
    cmd_sock = [None]

    def ensure_cmd_connection():
        if cmd_sock[0] is None:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect((PI_HOST, CMD_PORT))
                cmd_sock[0] = s
            except Exception as e:
                print(f"Command connection error: {e}")

    def send_command(cmd: str):
        try:
            ensure_cmd_connection()
            if cmd_sock[0]:
                cmd_sock[0].sendall(cmd.encode("ascii"))
        except Exception:
            cmd_sock[0] = None

    # --- GUI update loop ---
    def update_frame():
        if latest_frame[0] is not None:
            img = ImageTk.PhotoImage(latest_frame[0])
            video_label.configure(image=img)
            video_label.image = img
            status_label.configure(text="Connected", fg="green")
        elif not connected[0]:
            status_label.configure(text="Connecting to Raspberry Pi...", fg="orange")

        root.after(UPDATE_MS, update_frame)

    # --- keyboard handling ---
    KEY_MAP = {
        "w": "F",
        "s": "B",
        "a": "L",
        "d": "R",
    }

    def on_key(event):
        if event.char == "q":
            root.destroy()
            return
        cmd = KEY_MAP.get(event.char)
        if cmd:
            send_command(cmd)

    def on_key_release(event):
        if event.char in KEY_MAP:
            send_command("S")

    root.bind("<KeyPress>", on_key)
    root.bind("<KeyRelease>", on_key_release)
    update_frame()
    root.mainloop()

    if cmd_sock[0]:
        cmd_sock[0].close()


if __name__ == "__main__":
    main()
