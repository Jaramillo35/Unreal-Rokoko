#!/usr/bin/env python3
"""
Neck axis check (Pitch / Roll / Yaw)

CSV → Unreal mapping you’re using:
  Neck_flexion            → /bone/neck_01/pitch
  Neck_left-ward_tilt     → /bone/neck_01/roll
  Neck_right-ward_rotation→ /bone/neck_01/yaw

+Angle expectations:
  +Pitch = FLEXION — chin toward chest (sagittal)
  +Roll  = LEFT TILT — left ear toward left shoulder (coronal)
  +Yaw   = LEFT ROTATION — look left (transverse)
"""

import time, json
from pythonosc.udp_client import SimpleUDPClient

# ---- Settings ---------------------------------------------------------------
IP = "127.0.0.1"
PORT = 9000
RATE = 30.0          # Hz
ANGLE = 20.0         # degrees for the test step
HOLD_POS_SECS = 2.0  # hold +ANGLE
HOLD_ZERO_SECS = 1.0 # hold 0 after each test
INITIAL_DELAY = 3.0
BETWEEN_TESTS = 1.0
OUT_JSON = "neck_axis_check.json"

# OSC addresses (must match your Blueprint switch)
ADDR = {
    "Pitch": "/bone/neck_01/pitch",
    "Roll":  "/bone/neck_01/roll",
    "Yaw":   "/bone/neck_01/yaw",
}

ORDER = ["Pitch", "Roll", "Yaw"]

EXPECTED = {
    "Pitch": "FLEXION — chin moves DOWN toward chest (sagittal plane)",
    "Roll":  "LEFT TILT — left ear moves toward left shoulder (coronal plane)",
    "Yaw":   "LEFT ROTATION — head turns LEFT (transverse plane)",
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

    print(f"[✓] Streaming to {IP}:{PORT} @ {RATE:.1f} Hz")
    print(f"Initial delay {INITIAL_DELAY:.1f}s — focus Unreal viewport.")
    time.sleep(INITIAL_DELAY)

    print("Zeroing…")
    send_pose(client, zero_pose(), 0.5)

    for key in ORDER:
        exp = EXPECTED[key]
        print("\n" + "-"*64)
        print(f"Testing Neck {key}: +{ANGLE:.0f}° expected → {exp}")

        pose = zero_pose()
        pose[key] = ANGLE
        send_pose(client, pose, HOLD_POS_SECS)

        send_pose(client, zero_pose(), HOLD_ZERO_SECS)

        ok = ask_yes_no(f"Did +{ANGLE:.0f}° on Neck {key} LOOK LIKE: {exp}?")
        results[key] = {"expected": exp, "matches": bool(ok)}

        time.sleep(BETWEEN_TESTS)

    send_pose(client, zero_pose(), 0.5)

    print("\n=== SUMMARY ===")
    for key in ORDER:
        print(f"{key:>5s}: matches={results[key]['matches']} | expected={results[key]['expected']}")

    with open(OUT_JSON, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved → {OUT_JSON}\nTip: If an axis is inverted, re-run with ANGLE = -{abs(ANGLE)} or flip the sign at your source/CR.")

if __name__ == "__main__":
    main()