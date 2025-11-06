#!/usr/bin/env python3
"""
Send baseline (neutral sitting, hands-forward) pose to Unreal via OSC.

- Uses your Blueprint addresses like /bone/upperarm_l/pitch etc.
- Sends a smooth ramp from 0 -> baseline over --ramp seconds (default 1.5s).
- Then holds the exact baseline for --hold seconds (default 2s).

Usage:
  python send_baseline_pose.py --ip 127.0.0.1 --port 9000 --rate 30 --ramp 1.5 --hold 2 --delay 2
"""

import time
import argparse
import numpy as np
from pythonosc.udp_client import SimpleUDPClient

# === Baseline angles (degrees) you asked me to compute ===
# LEFT
BASELINE_POSE = {
    "/bone/upperarm_l/pitch":  +0,   # ← abduction
    "/bone/upperarm_l/yaw":    -30,   # ← flexion
    "/bone/upperarm_l/roll":   -0,   # ← external rotation

    "/bone/lowerarm_l/pitch":  -0,   # ← elbow flexion
    "/bone/lowerarm_l/roll":   +30.13,   # ← forearm pronation

    "/bone/hand_l/pitch":      -0,    # ← wrist flexion
    "/bone/hand_l/yaw":        -6,    # ← wrist adduction (ulnar dev.)
    "/bone/hand_l/roll":       +2,    # ← wrist pronation

    # RIGHT
    "/bone/upperarm_r/pitch":  +0,
    "/bone/upperarm_r/yaw":    -30,
    "/bone/upperarm_r/roll":   -0,

    "/bone/lowerarm_r/pitch":  +0,
    "/bone/lowerarm_r/roll":   +30.13,

    "/bone/hand_r/pitch":      -0,
    "/bone/hand_r/yaw":        -6,
    "/bone/hand_r/roll":       +2,
}

def main():
    ap = argparse.ArgumentParser(description="Send the baseline pose to Unreal via OSC.")
    ap.add_argument("--ip", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=9000)
    ap.add_argument("--rate", type=float, default=30.0, help="Hz for ramp/hold streaming")
    ap.add_argument("--ramp", type=float, default=1.5, help="Seconds to ease from 0 -> baseline")
    ap.add_argument("--hold", type=float, default=2.0, help="Seconds to hold exact baseline after ramp")
    ap.add_argument("--delay", type=float, default=2.0, help="Startup delay (seconds)")
    args = ap.parse_args()

    client = SimpleUDPClient(args.ip, args.port)

    if args.delay > 0:
        print(f"Starting in {args.delay:.1f}s…")
        time.sleep(args.delay)

    rate = max(1.0, args.rate)
    dt = 1.0 / rate

    # ---- Smooth ramp 0 -> baseline ----
    n_ramp = max(1, int(args.ramp * rate))
    print(f"Ramping to baseline over {args.ramp:.2f}s ({n_ramp} frames) @ {rate:.1f} Hz")
    t0 = time.perf_counter()
    for i in range(1, n_ramp + 1):
        alpha = i / n_ramp  # 0..1
        for addr, target in BASELINE_POSE.items():
            val = float(alpha * target)
            client.send_message(addr, val)
        target_t = t0 + i * dt
        sleep = target_t - time.perf_counter()
        if sleep > 0:
            time.sleep(sleep)

    # ---- Hold exact baseline ----
    n_hold = max(1, int(args.hold * rate))
    print(f"Holding baseline for {args.hold:.2f}s ({n_hold} frames)…")
    t1 = time.perf_counter()
    for j in range(1, n_hold + 1):
        for addr, target in BASELINE_POSE.items():
            client.send_message(addr, float(target))
        target_t = t1 + j * dt
        sleep = target_t - time.perf_counter()
        if sleep > 0:
            time.sleep(sleep)

    print("Baseline pose sent and held. You can stop the script now.")

if __name__ == "__main__":
    main()