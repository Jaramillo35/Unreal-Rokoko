#!/usr/bin/env python3
"""
Wrists/Hands sign tester — send NEGATIVE angles for all axes (pitch/yaw/roll).

Mapping (ISB JCS -> Unreal axes):
  - flexion     -> pitch  (send negative)
  - adduction   -> yaw    (send negative)
  - pronation   -> roll   (send negative)

Per side (L, R) it runs three tests:
  1) FLEXION  (-pitch): expect hand bends toward forearm (sagittal)
  2) ADDUCTION(-yaw)  : expect hand moves toward ulna/pinky (coronal; ulnar dev.)
  3) PRONATION(-roll) : expect palm rotates DOWN (thumb inward)

If you answer "no", we mark that DOF as needing sign inversion in the JSON report.

Usage:
  python WristSigns_NegAll.py --ip 127.0.0.1 --port 9000 --rate 30 \
      --amp-flex -15 --amp-add -12 --amp-pro -20 --ramp-s 6 --hold-s 2.5 --start-delay 3
"""

import argparse, time, json, os
import numpy as np
from pythonosc.udp_client import SimpleUDPClient

def ramp_hold(rate: float, duration_s: float, target: float, hold_s: float):
    """Cosine ramp 0 -> target, then hold."""
    n_up = max(2, int(duration_s * rate))
    t = np.linspace(0, np.pi, n_up, endpoint=True)
    up = target * (1 - np.cos(t)) / 2.0
    hold = np.full(max(1, int(hold_s * rate)), target, dtype=np.float32)
    return np.concatenate([up.astype(np.float32), hold])

def zero_channels(client, addrs):
    for a in addrs:
        client.send_message(a, 0.0)

def ask_yes_no(prompt: str) -> bool:
    ans = input(f"{prompt} [y/N]: ").strip().lower()
    return ans in ("y","yes")

def main():
    ap = argparse.ArgumentParser(description="Wrists/Hands sign tester (NEG pitch/yaw/roll)")
    ap.add_argument("--ip", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=9000)
    ap.add_argument("--rate", type=float, default=60.0)
    ap.add_argument("--start-delay", type=float, default=3.0)

    # Negative amplitudes by default (override if needed)
    ap.add_argument("--amp-flex", type=float, default=-60.0, help="Flexion target (pitch, negative deg)")
    ap.add_argument("--amp-add",  type=float, default=-60.0, help="Adduction target (yaw, negative deg)")
    ap.add_argument("--amp-pro",  type=float, default=-60.0, help="Pronation target (roll, negative deg)")
    ap.add_argument("--ramp-s",   type=float, default=6.0,   help="Seconds to ramp")
    ap.add_argument("--hold-s",   type=float, default=2.5,   help="Seconds to hold at target")
    args = ap.parse_args()

    client = SimpleUDPClient(args.ip, args.port)
    print(f"OSC → {args.ip}:{args.port} @ {args.rate:.1f} Hz")
    if args.start_delay > 0:
        print(f"Starting in {args.start_delay:.1f}s…")
        time.sleep(args.start_delay)

    # OSC addresses must match your Blueprint Switch on String
    ADDR = {
        "L": {"flex": "/bone/hand_l/pitch", "add": "/bone/hand_l/yaw", "pro": "/bone/hand_l/roll"},
        "R": {"flex": "/bone/hand_r/pitch", "add": "/bone/hand_r/yaw", "pro": "/bone/hand_r/roll"},
    }
    ALL_ADDRS = [ADDR[s][k] for s in ("L","R") for k in ("flex","add","pro")]

    # Report of which DOFs need inversion (if the negative direction didn’t match expectation)
    report = {"invert": {"L":{"flexion":False,"adduction":False,"pronation":False},
                         "R":{"flexion":False,"adduction":False,"pronation":False}}}

    dt = 1.0 / args.rate

    def do_test(side, kind, target_deg, expectation, label):
        zero_channels(client, ALL_ADDRS); time.sleep(0.25)
        addr = ADDR[side][kind]
        seq = ramp_hold(args.rate, args.ramp_s, target_deg, args.hold_s)

        print(f"\n{label} — {side} wrist: ramp to {target_deg:+.1f}° → {addr} (hold {args.hold_s}s)")
        t0 = time.perf_counter()
        for i, v in enumerate(seq):
            client.send_message(addr, float(v))
            # steady 30 fps pacing
            target_t = t0 + (i+1)*dt
            sleep = target_t - time.perf_counter()
            if sleep > 0: time.sleep(sleep)

        ok = ask_yes_no(f"Expected motion: {expectation}\nDid it look correct?")
        invert = not ok
        client.send_message(addr, 0.0); time.sleep(0.3)
        return invert

    EXPECT = {
        "flex": "FLEXION (-pitch): hand bends toward forearm (sagittal).",
        "add":  "ADDUCTION (-yaw): hand moves toward ulna/pinky (coronal; ulnar deviation).",
        "pro":  "PRONATION (-roll): palm rotates DOWN (thumb inward).",
    }

    # LEFT
    report["invert"]["L"]["flexion"]   = do_test("L", "flex", args.amp_flex, EXPECT["flex"], "FLEXION")
    report["invert"]["L"]["adduction"] = do_test("L", "add",  args.amp_add,  EXPECT["add"],  "ADDUCTION")
    report["invert"]["L"]["pronation"] = do_test("L", "pro",  args.amp_pro,  EXPECT["pro"],  "PRONATION")

    # RIGHT
    report["invert"]["R"]["flexion"]   = do_test("R", "flex", args.amp_flex, EXPECT["flex"], "FLEXION")
    report["invert"]["R"]["adduction"] = do_test("R", "add",  args.amp_add,  EXPECT["add"],  "ADDUCTION")
    report["invert"]["R"]["pronation"] = do_test("R", "pro",  args.amp_pro,  EXPECT["pro"],  "PRONATION")

    out = "wrist_sign_report_oneway.json"
    with open(out, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nSaved → {os.path.abspath(out)}")
    print("Use these flags to flip signs in your live streamer where needed.")

if __name__ == "__main__":
    main()