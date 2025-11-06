#!/usr/bin/env python3
"""
Interactive tester — Left Thumb only.

Sequence:
  • Thumb_01_l → Pitch, Roll, Yaw
  • Thumb_02_l → Pitch, Roll, Yaw
  • Thumb_03_l → Pitch, Roll, Yaw

Each step:
  • Sends +ANGLE
  • Holds
  • Returns to zero
  • Waits for Enter to continue
"""

import time
from pythonosc.udp_client import SimpleUDPClient

# ---- Settings ---------------------------------------------------------------
IP = "127.0.0.1"
PORT = 9000
RATE = 30.0  # Hz

ANGLES = {"pitch": -20.0, "roll": 20.0, "yaw": -20.0}
HOLD_POS_SECS = 1.5
HOLD_ZERO_SECS = 0.8
INITIAL_DELAY = 1.0

JOINTS  = ["01", "02", "03"]
AXES_ORDER = ["pitch", "roll", "yaw"]

CUES = {
    "pitch": "Flexion — thumb bends across the palm (toward wrist/palm).",
    "roll":  "Axial twist — thumbnail rotates toward/away from palm.",
    "yaw":   "Sideways sweep — thumb moves toward or away from index (adduction/abduction).",
}

# ---- Helpers ----------------------------------------------------------------
def addr(joint: str, axis: str) -> str:
    return f"/bone/thumb_{joint}_l/{axis}"

def send_pose(client: SimpleUDPClient, pose: dict, secs: float):
    dt = 1.0 / RATE
    frames = max(1, int(secs * RATE))
    for _ in range(frames):
        for a, v in pose.items():
            client.send_message(a, float(v))
        time.sleep(dt)

def zero_for_joint(joint: str) -> dict:
    return {addr(joint, ax): 0.0 for ax in AXES_ORDER}

# ---- Main -------------------------------------------------------------------
def main():
    client = SimpleUDPClient(IP, PORT)
    print(f"[✓] Streaming to {IP}:{PORT} at {RATE:.1f} Hz")
    time.sleep(INITIAL_DELAY)

    for joint in JOINTS:
        print(f"\n=== Thumb_{joint} ===")
        send_pose(client, zero_for_joint(joint), 0.25)

        for axis in AXES_ORDER:
            a = addr(joint, axis)
            cue = CUES[axis]
            print(f"\n→ Thumb_{joint} {axis.upper()} {ANGLES[axis]:+.0f}°")
            print(f"   Cue: {cue}")
            print(f"   Address: {a}")

            # Send motion
            send_pose(client, {a: ANGLES[axis]}, HOLD_POS_SECS)
            send_pose(client, {a: 0.0}, HOLD_ZERO_SECS)

            input("   Looks right? Press Enter to continue…")

    print("\nThumb 01–03 tested. Done.")

if __name__ == "__main__":
    main()