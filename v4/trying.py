import time
from pythonosc import udp_client
import numpy as np

# ====== SETTINGS ======
IP = "127.0.0.1"        # Unreal OSC server IP
PORT = 9000             # Unreal OSC server port (match your blueprint)
OSC_ADDRESS = "/bone/upperarm_l/pitch"   # OSC path expected in Unreal

# Value range for LeftShoulder_flexion
MIN_VAL = -30.51454
MAX_VAL = 49.09228
STEP_COUNT = 200        # Number of steps for smooth transition
DELAY = 0.05            # Seconds between steps (0.05 → ~5 sec sweep)

# ====== CLIENT ======
client = udp_client.SimpleUDPClient(IP, PORT)

# ====== SWEEP LOOP ======
values = np.linspace(MIN_VAL, MAX_VAL, STEP_COUNT)
print(f"Sending {STEP_COUNT} values from {MIN_VAL:.2f} to {MAX_VAL:.2f}")

for v in values:
    client.send_message(OSC_ADDRESS, float(v))
    print(f"Sent {OSC_ADDRESS}: {v:.3f}")
    time.sleep(DELAY)

print("Sweep complete.")