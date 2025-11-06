# pip install python-osc
import time
from pythonosc import udp_client

IP = "127.0.0.1"              # Unreal OSC server IP
PORT = 9000                   # Unreal OSC server port
OSC_ADDR = "/bone/upperarm_l/pitch"

# Pick a broad, safe test set (degrees). Adjust if your rig uses another span.
TEST_ANGLES = [-150,-135,-120,-105,-90, -75 ,-60, -30, -15, 0, 15, 30, 45, 60, 75, 90, 105, 120, 135, 150]

STEP_HOLD_SEC = 1.0           # how long to hold each angle before asking
client = udp_client.SimpleUDPClient(IP, PORT)

print("\nLeft Arm Pitch Calibrator")
print("Sending angles to:", OSC_ADDR)
print("For each angle, look at the pose in Unreal and type:")
print("  s  → 'side of body' (arm out to the side)")
print("  u  → 'upward to the sky'")
print("  Enter to skip\n")

side_angle = None
up_angle = None

for ang in TEST_ANGLES:
    client.send_message(OSC_ADDR, float(ang))
    print(f"\nAngle sent: {ang:.1f}°  (holding {STEP_HOLD_SEC:.1f}s...)")
    time.sleep(STEP_HOLD_SEC)

    resp = input("Mark this angle? [s=side, u=up, Enter=skip] ").strip().lower()
    if resp == "s":
        side_angle = ang
        print(f"→ Recorded SIDE angle = {ang:.1f}°")
    elif resp == "u":
        up_angle = ang
        print(f"→ Recorded UP angle = {ang:.1f}°")
    else:
        print("→ Skipped")

print("\nCalibration results:")
print(f"  Side-of-body angle: {side_angle if side_angle is not None else 'not marked'}")
print(f"  Upward (to the sky) angle: {up_angle if up_angle is not None else 'not marked'}")

# Optional: return to neutral at the end
if 0 in TEST_ANGLES:
    client.send_message(OSC_ADDR, 0.0)