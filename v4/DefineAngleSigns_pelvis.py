#!/usr/bin/env python3
"""
Pelvis axis check (Pitch / Yaw / Roll).

For each pelvis channel we:
  • Wait INITIAL_DELAY seconds so you can focus Unreal.
  • Drive +ANGLE for HOLD_POS_SECS, then back to 0 for HOLD_ZERO_SECS.
  • Ask if what you saw matches the expected anatomical motion:
      - +Pitch  = pelvis tips FORWARD (anterior tilt, sagittal plane)
      - +Yaw    = pelvis TWISTS (turns) around the vertical axis (transverse)
      - +Roll   = pelvis tilts to the SIDE (one hip drops, coronal)

If something looks inverted, rerun with ANGLE = -ANGLE or note it in the JSON.
"""

import time, json
from pythonosc.udp_client import SimpleUDPClient

# ------------- Settings ------------------------------------------------------
IP   = "127.0.0.1"
PORT = 9000
RATE = 30.0         # Hz
ANGLE = 30.0        # degrees to test (use negative if you want to probe sign)
HOLD_POS_SECS  = 2.0
HOLD_ZERO_SECS = 1.0
INITIAL_DELAY  = 2.5
BETWEEN_TESTS  = 0.8
OUT_JSON = "pelvis_axis_check.json"

# OSC addresses (must match your ABP/CR switch cases)
ADDR = {
    "Pelvis_Pitch": "/bone/pelvis/pitch",
    "Pelvis_Yaw"  : "/bone/pelvis/yaw",
    "Pelvis_Roll" : "/bone/pelvis/roll",
}

ORDER = ["Pelvis_Pitch", "Pelvis_Yaw", "Pelvis_Roll"]

# What we expect when we send a POSITIVE angle on each channel
EXPECTED = {
    "Pelvis_Pitch": "FORWARD tip (anterior tilt) — sagittal plane",
    "Pelvis_Yaw"  : "TWIST / TURN around vertical — transverse plane",
    "Pelvis_Roll" : "SIDE tilt (one hip drops) — coronal plane",
}

# ------------- Helpers -------------------------------------------------------
def zero_pose():
    return {k: 0.0 for k in ADDR.keys()}

def send_pose(client, pose: dict, secs: float):
    dt = 1.0 / RATE
    frames = max(1, int(secs * RATE))
    for _ in range(frames):
        for key, addr in ADDR.items():
            client.send_message(addr, float(pose.get(key, 0.0)))
        time.sleep(dt)

def ask_yes_no(prompt: str) -> bool:
    ans = input(prompt + " [y/n]> ").strip().lower()
    return ans in ("y", "yes")

# ------------- Main ----------------------------------------------------------
def main():
    client = SimpleUDPClient(IP, PORT)
    results = {}

    print(f"[✓] Pelvis axis test streaming to {IP}:{PORT} at {RATE:.1f} Hz")
    print(f"Initial delay {INITIAL_DELAY:.1f}s… focus the Unreal viewport/PIE.")
    time.sleep(INITIAL_DELAY)

    # Zero first
    send_pose(client, zero_pose(), 0.5)

    for key in ORDER:
        exp = EXPECTED[key]
        print("\n" + "-" * 60)
        print(f"Testing {key}: +{ANGLE:.1f}°  (expected: {exp})")

        pose = zero_pose()
        pose[key] = ANGLE
        send_pose(client, pose, HOLD_POS_SECS)

        # Back to zero to settle
        send_pose(client, zero_pose(), HOLD_ZERO_SECS)

        ok = ask_yes_no(f"Did +{ANGLE:.1f}° on {key} LOOK LIKE: {exp}?")
        results[key] = {
            "expected": exp,
            "matches_positive": bool(ok),
            "angle_tested_deg": ANGLE,
        }

        time.sleep(BETWEEN_TESTS)

    # Final settle
    send_pose(client, zero_pose(), 0.5)

    # Summary
    print("\n=== SUMMARY ===")
    for key in ORDER:
        m = "OK" if results[key]["matches_positive"] else "NO"
        print(f"{key:>12s}: {m}  | {results[key]['expected']}")

    with open(OUT_JSON, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved → {OUT_JSON}")
    print("Tip: If an axis is inverted, rerun with ANGLE set to the negative value, "
          "or flip that channel’s sign at the source/graph.")

if __name__ == "__main__":
    main()