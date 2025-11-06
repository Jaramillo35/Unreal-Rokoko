#!/usr/bin/env python3
"""
UpperArm L/R axis check (positive-only).

For each axis (Pitch, Yaw, Roll) on Left and Right upperarms:
  • Wait 3s (so you can focus Unreal)
  • Apply +ANGLE for HOLD_POS_SECS seconds (default +30° for 2s)
  • Return to 0° for 1s
  • Ask: "Did it look like: <expected motion> ? [y/n]"
We assume the following desired semantics for +angles:
  - +Pitch  = ABduction  (arm raises out to the SIDE, coronal plane)
  - +Yaw    = FLEXION    (arm raises FORWARD, sagittal plane)
  - +Roll   = EXTERNAL ROTATION (axial twist: biceps/elbow pit turns OUTWARD)

Answers are saved to JSON for later use when deciding which axes need an inversion.
"""

import time, json
from pythonosc.udp_client import SimpleUDPClient

# ---- Settings ---------------------------------------------------------------
IP = "127.0.0.1"
PORT = 9000
RATE = 30.0          # Hz
ANGLE = -30.0         # degrees (+ only)
HOLD_POS_SECS = 2.0  # seconds at +ANGLE
HOLD_ZERO_SECS = 1.0 # seconds to settle at 0
INITIAL_DELAY = 3.0  # seconds before the very first test
BETWEEN_TESTS = 1.0  # short pause between axes
OUT_JSON = "upperarm_axis_check_positive.json"

# OSC addresses (must match your Blueprint switch)
ADDR = {
    "LeftPitch":  "/bone/upperarm_l/pitch",
    "LeftYaw":    "/bone/upperarm_l/yaw",
    "LeftRoll":   "/bone/upperarm_l/roll",
    "RightPitch": "/bone/upperarm_r/pitch",
    "RightYaw":   "/bone/upperarm_r/yaw",
    "RightRoll":  "/bone/upperarm_r/roll",
}

# Order of tests
ORDER = ["LeftPitch","LeftYaw","LeftRoll","RightPitch","RightYaw","RightRoll"]

# Expected motion descriptions for +ANGLE on each axis
EXPECTED = {
    "LeftPitch":  "ABDUCTION — left arm lifts OUT to the SIDE",
    "LeftYaw":    "FLEXION — left arm lifts FORWARD in front of torso",
    "LeftRoll":   "EXTERNAL ROTATION — left upperarm twists so elbow pit/biceps turn OUTWARD",
    "RightPitch": "ABDUCTION — right arm lifts OUT to the SIDE",
    "RightYaw":   "FLEXION — right arm lifts FORWARD in front of torso",
    "RightRoll":  "EXTERNAL ROTATION — right upperarm twists so elbow pit/biceps turn OUTWARD",
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
    return ans in ("y", "yes")

# ---- Main -------------------------------------------------------------------
def main():
    client = SimpleUDPClient(IP, PORT)
    results = {}

    print(f"[✓] Streaming to {IP}:{PORT} at {RATE:.1f} Hz")
    print(f"Initial delay {INITIAL_DELAY:.1f}s…")
    time.sleep(INITIAL_DELAY)

    # Zero everything first
    print("Zeroing …")
    send_pose(client, zero_pose(), 0.5)

    for key in ORDER:
        exp = EXPECTED[key]
        print("\n" + "-"*64)
        print(f"Testing {key}: +{ANGLE:.0f}° expected → {exp}")

        # apply +ANGLE on this axis only
        pose = zero_pose()
        pose[key] = ANGLE
        send_pose(client, pose, HOLD_POS_SECS)

        # return to 0
        send_pose(client, zero_pose(), HOLD_ZERO_SECS)

        ok = ask_yes_no(f"Did +{ANGLE:.0f}° on {key} LOOK LIKE: {exp}?")
        results[key] = {"expected": exp, "matches": bool(ok)}

        time.sleep(BETWEEN_TESTS)

    # settle to zero
    send_pose(client, zero_pose(), 0.5)

    # Summary
    print("\n=== SUMMARY ===")
    for key in ORDER:
        print(f"{key:>10s}: matches={results[key]['matches']}  | expected={results[key]['expected']}")

    with open(OUT_JSON, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved → {OUT_JSON}")
    print("Any axis with matches=False likely needs a sign flip (invert the values) in your streamer.")

if __name__ == "__main__":
    main()