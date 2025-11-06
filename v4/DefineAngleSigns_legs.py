#!/usr/bin/env python3
"""
Legs axis check (positive-only).

For each axis on Left and Right legs:
  • Wait 3s (so you can focus Unreal)
  • Apply +ANGLE for HOLD_POS_SECS seconds (default +30° for 2s)
  • Return to 0° for 1s
  • Ask: "Did it look like: <expected motion> ? [y/n]"

Axis semantics we expect for +angles (matching your streamer mapping):
  THIGH  : +Pitch = ABDUCTION (thigh moves OUT to the side)
           +Yaw   = FLEXION   (thigh moves FORWARD)
           +Roll  = EXTERNAL ROTATION (knee points OUTWARD)
  CALF   : +Pitch = KNEE FLEXION (lower leg bends backward)
           (Yaw/Roll not tested by default)
  FOOT   : +Pitch = ANKLE FLEXION (toes move DOWN/forward — plantarflexion)
           +Yaw   = INVERSION/EVERSION around long axis (medial/lateral tilt)
           +Roll  = AXIAL ROTATION (toe-out is positive)
  BALL   : +Pitch = TOE FLEXION (ball/toes press DOWN)
           (Yaw/Roll not tested by default)

Use the answers later to decide if any axis needs a sign flip in your streamer.
"""

import time, json
from pythonosc.udp_client import SimpleUDPClient

# ---- Settings ---------------------------------------------------------------
IP = "127.0.0.1"
PORT = 9000
RATE = 30.0          # Hz
ANGLE = +30.0        # degrees (+ only)
HOLD_POS_SECS = 2.0  # seconds at +ANGLE
HOLD_ZERO_SECS = 1.0 # seconds to settle at 0
INITIAL_DELAY = 3.0  # seconds before the very first test
BETWEEN_TESTS = 1.0  # short pause between axes
OUT_JSON = "legs_axis_check_positive.json"

# If you mapped additional axes for calf/ball, flip these to True.
TEST_CALF_YAW  = False
TEST_CALF_ROLL = False
TEST_BALL_YAW  = False
TEST_BALL_ROLL = False

# ---- OSC addresses (must match your Blueprint switch) -----------------------
ADDR = {
    # THIGH (hip)
    "LeftThighPitch":  "/bone/thigh_l/pitch",
    "LeftThighYaw":    "/bone/thigh_l/yaw",
    "LeftThighRoll":   "/bone/thigh_l/roll",
    "RightThighPitch": "/bone/thigh_r/pitch",
    "RightThighYaw":   "/bone/thigh_r/yaw",
    "RightThighRoll":  "/bone/thigh_r/roll",

    # CALF (knee) — Pitch only by default
    "LeftCalfPitch":   "/bone/calf_l/pitch",
    "RightCalfPitch":  "/bone/calf_r/pitch",

    # FOOT (ankle)
    "LeftFootPitch":   "/bone/foot_l/pitch",
    "LeftFootYaw":     "/bone/foot_l/yaw",
    "LeftFootRoll":    "/bone/foot_l/roll",
    "RightFootPitch":  "/bone/foot_r/pitch",
    "RightFootYaw":    "/bone/foot_r/yaw",
    "RightFootRoll":   "/bone/foot_r/roll",

    # BALL (toes) — Pitch only by default
    "LeftBallPitch":   "/bone/ball_l/pitch",
    "RightBallPitch":  "/bone/ball_r/pitch",
}

# ---- Order of tests ---------------------------------------------------------
ORDER = [
    # LEFT
    "LeftThighPitch","LeftThighYaw","LeftThighRoll",
    "LeftCalfPitch",
    "LeftFootPitch","LeftFootYaw","LeftFootRoll",
    "LeftBallPitch",
    # RIGHT
    "RightThighPitch","RightThighYaw","RightThighRoll",
    "RightCalfPitch",
    "RightFootPitch","RightFootYaw","RightFootRoll",
    "RightBallPitch",
]

# Optionally add calf/ball yaw/roll if you’ve mapped them
if TEST_CALF_YAW:
    ADDR["LeftCalfYaw"]  = "/bone/calf_l/yaw"
    ADDR["RightCalfYaw"] = "/bone/calf_r/yaw"
    ORDER.insert(4, "LeftCalfYaw")
    ORDER.insert(12, "RightCalfYaw")
if TEST_CALF_ROLL:
    ADDR["LeftCalfRoll"]  = "/bone/calf_l/roll"
    ADDR["RightCalfRoll"] = "/bone/calf_r/roll"
    ORDER.insert(5 if TEST_CALF_YAW else 4, "LeftCalfRoll")
    # position after RightCalfYaw if present
    right_insertion = 13 if TEST_CALF_YAW else 12
    ORDER.insert(right_insertion, "RightCalfRoll")
if TEST_BALL_YAW:
    ADDR["LeftBallYaw"]  = "/bone/ball_l/yaw"
    ADDR["RightBallYaw"] = "/bone/ball_r/yaw"
    ORDER.insert(7, "LeftBallYaw")
    ORDER.insert(15, "RightBallYaw")
if TEST_BALL_ROLL:
    ADDR["LeftBallRoll"]  = "/bone/ball_l/roll"
    ADDR["RightBallRoll"] = "/bone/ball_r/roll"
    ORDER.insert(8 if TEST_BALL_YAW else 7, "LeftBallRoll")
    ORDER.insert(16 if TEST_BALL_YAW else 15, "RightBallRoll")

# ---- Expected motion text for +ANGLE ---------------------------------------
EXPECTED = {
    # THIGH
    "LeftThighPitch":   "HIP ABDUCTION — left thigh moves OUT to the SIDE",
    "LeftThighYaw":     "HIP FLEXION — left thigh moves FORWARD",
    "LeftThighRoll":    "EXTERNAL ROTATION — left knee points OUTWARD",
    "RightThighPitch":  "HIP ABDUCTION — right thigh moves OUT to the SIDE",
    "RightThighYaw":    "HIP FLEXION — right thigh moves FORWARD",
    "RightThighRoll":   "EXTERNAL ROTATION — right knee points OUTWARD",

    # CALF (knee)
    "LeftCalfPitch":    "KNEE FLEXION — left lower leg bends BACKWARD (heel toward butt)",
    "RightCalfPitch":   "KNEE FLEXION — right lower leg bends BACKWARD (heel toward butt)",
    "LeftCalfYaw":      "KNEE VARUS/VALGUS — lower leg tilts MEDIAL/LATERAL (if mapped)",
    "RightCalfYaw":     "KNEE VARUS/VALGUS — lower leg tilts MEDIAL/LATERAL (if mapped)",
    "LeftCalfRoll":     "TIBIAL EXTERNAL ROTATION — shin twists OUTWARD (if mapped)",
    "RightCalfRoll":    "TIBIAL EXTERNAL ROTATION — shin twists OUTWARD (if mapped)",

    # FOOT (ankle)
    "LeftFootPitch":    "ANKLE FLEXION — toes move DOWN/forward (plantarflexion)",
    "LeftFootYaw":      "ANKLE INVERSION/EVERSION — sole tilts MEDIAL/LATERAL",
    "LeftFootRoll":     "ANKLE AXIAL ROTATION — foot yaws so toes point OUTWARD",
    "RightFootPitch":   "ANKLE FLEXION — toes move DOWN/forward (plantarflexion)",
    "RightFootYaw":     "ANKLE INVERSION/EVERSION — sole tilts MEDIAL/LATERAL",
    "RightFootRoll":    "ANKLE AXIAL ROTATION — foot yaws so toes point OUTWARD",

    # BALL (toes)
    "LeftBallPitch":    "TOE FLEXION — ball/toes press DOWN",
    "RightBallPitch":   "TOE FLEXION — ball/toes press DOWN",
    "LeftBallYaw":      "TOE TILT — ball tilts MEDIAL/LATERAL (if mapped)",
    "RightBallYaw":     "TOE TILT — ball tilts MEDIAL/LATERAL (if mapped)",
    "LeftBallRoll":     "TOE AXIAL ROTATION — toes rotate OUTWARD (if mapped)",
    "RightBallRoll":    "TOE AXIAL ROTATION — toes rotate OUTWARD (if mapped)",
}

# ---- Helpers ----------------------------------------------------------------
def zero_pose():
    return {k: 0.0 for k in ADDR.keys()}

def send_pose(client, pose: dict, secs: float):
    dt = 1.0 / RATE
    frames = max(1, int(round(secs * RATE)))
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
        exp = EXPECTED.get(key, "(no description)")
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
        m = results.get(key, {}).get("matches", None)
        print(f"{key:>16s}: matches={m}  | expected={EXPECTED.get(key,'')}")

    with open(OUT_JSON, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved → {OUT_JSON}")
    print("Any axis with matches=False likely needs a sign flip (invert the values) in your streamer.")

if __name__ == "__main__":
    main()