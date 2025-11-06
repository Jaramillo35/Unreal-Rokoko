#!/usr/bin/env python3
"""
Thorax axis check (Pitch / Roll / Yaw).

CSV channels:
  Thorax_extension                  → /bone/spine_03/pitch
  Thorax_lateral_flexion_rotation   → /bone/spine_03/roll
  Thorax_axial_rotation             → /bone/spine_03/yaw

We assume +angles should look like:
  +Pitch  = Thorax flexes FORWARD (spine bends forward, sagittal plane)
  +Roll   = Thorax tilts LEFT (lateral bend, coronal plane)
  +Yaw    = Thorax twists LEFT (rotation, transverse plane)
"""

import time, json
from pythonosc.udp_client import SimpleUDPClient

# ---- Settings ---------------------------------------------------------------
IP = "127.0.0.1"
PORT = 9000
RATE = 30.0           # Hz
ANGLE = 30.0          # degrees to test
HOLD_POS_SECS = 2.0   # seconds at +ANGLE
HOLD_ZERO_SECS = 1.0  # seconds back at 0
INITIAL_DELAY = 3.0   # delay before first move
BETWEEN_TESTS = 1.0   # pause between axes
OUT_JSON = "thorax_axis_check.json"

# OSC addresses
ADDR = {
    "Pitch": "/bone/spine_03/pitch",
    "Roll":  "/bone/spine_03/roll",
    "Yaw":   "/bone/spine_03/yaw",
}

ORDER = ["Pitch","Roll","Yaw"]

EXPECTED = {
    "Pitch": "FLEXION — thorax bends FORWARD (sagittal plane)",
    "Roll":  "LATERAL FLEXION — thorax tilts LEFT (coronal plane)",
    "Yaw":   "AXIAL ROTATION — thorax twists LEFT (transverse plane)",
}

# ---- Helpers ----------------------------------------------------------------
def zero_pose():
    return {k: 0.0 for k in ADDR.keys()}

def send_pose(client, pose: dict, secs: float):
    dt = 1.0 / RATE
    frames = int(secs * RATE)
    for _ in range(frames):
        for key, addr in ADDR.items():
            client.send_message(addr, float(pose.get(key, 0.0)))
        time.sleep(dt)

def ask_yes_no(prompt: str) -> bool:
    ans = input(prompt + " [y/n]> ").strip().lower()
    return ans in ("y","yes")

# ---- Main -------------------------------------------------------------------
def main():
    client = SimpleUDPClient(IP, PORT)
    results = {}

    print(f"[✓] Streaming to {IP}:{PORT} at {RATE:.1f} Hz")
    print(f"Initial delay {INITIAL_DELAY:.1f}s … focus the Unreal viewport.")
    time.sleep(INITIAL_DELAY)

    print("Zeroing…")
    send_pose(client, zero_pose(), 0.5)

    for key in ORDER:
        exp = EXPECTED[key]
        print("\n" + "-"*64)
        print(f"Testing Thorax {key}: +{ANGLE:.0f}° expected → {exp}")

        pose = zero_pose()
        pose[key] = ANGLE
        send_pose(client, pose, HOLD_POS_SECS)

        send_pose(client, zero_pose(), HOLD_ZERO_SECS)

        ok = ask_yes_no(f"Did +{ANGLE:.0f}° on Thorax {key} LOOK LIKE: {exp}?")
        results[key] = {"expected": exp, "matches": bool(ok)}

        time.sleep(BETWEEN_TESTS)

    send_pose(client, zero_pose(), 0.5)

    print("\n=== SUMMARY ===")
    for key in ORDER:
        print(f"{key:>5s}: matches={results[key]['matches']} | expected={results[key]['expected']}")

    with open(OUT_JSON, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved → {OUT_JSON}")

if __name__ == "__main__":
    main()