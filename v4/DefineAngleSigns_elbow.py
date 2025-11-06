#!/usr/bin/env python3
"""
Lowerarm (elbow) sign tester — one-way ramp & hold (no return), per side.

- Tests FLEXION on pitch and PRONATION on roll.
- Sends a positive ramp -> holds pose -> waits for your answer -> resets to 0.
- Zeros other channels before each test to avoid cross-talk.
"""

import argparse, time, json, os
import numpy as np
from pythonosc.udp_client import SimpleUDPClient

def ramp_hold(rate: float, duration_s: float, target: float, hold_s: float):
    """Monotonic cosine-ramp to +target, then hold."""
    n_up = max(2, int(duration_s * rate))
    t = np.linspace(0, np.pi, n_up, endpoint=True)
    up = target * (1 - np.cos(t)) / 2.0  # 0 -> +target
    hold = np.full(max(1, int(hold_s * rate)), target, dtype=np.float32)
    return np.concatenate([up.astype(np.float32), hold])

def stream_seq(client, addr_vals, rate: float, label: str):
    """addr_vals: list of (addr, value) for this frame (can be many channels)."""
    client_multi = SimpleUDPClient  # alias
    # Send all addr/val pairs for this moment
    for addr, val in addr_vals:
        client.send_message(addr, float(val))

def zero_channels(client, addrs):
    for a in addrs:
        client.send_message(a, 0.0)

def ask_yes_no(prompt: str) -> bool:
    ans = input(f"{prompt} [y/N]: ").strip().lower()
    return ans in ("y", "yes")

def main():
    ap = argparse.ArgumentParser(description="Elbow sign tester (one-way ramp & hold)")
    ap.add_argument("--ip", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=9000)
    ap.add_argument("--rate", type=float, default=30.0)
    ap.add_argument("--start-delay", type=float, default=3.0)

    # amplitudes (deg) and timing
    ap.add_argument("--amp-flex", type=float, default=60.0, help="Flexion +pitch target")
    ap.add_argument("--amp-pro",  type=float, default=60.0, help="Pronation +roll target")
    ap.add_argument("--ramp-s",   type=float, default=3.0,  help="Seconds to ramp up (slower = larger)")
    ap.add_argument("--hold-s",   type=float, default=2.5,  help="Seconds to hold at target before question")
    args = ap.parse_args()

    client = SimpleUDPClient(args.ip, args.port)
    print(f"OSC → {args.ip}:{args.port} @ {args.rate:.1f} Hz")
    if args.start_delay > 0:
        print(f"Starting in {args.start_delay:.1f}s…")
        time.sleep(args.start_delay)

    # OSC addresses (must match your Blueprint)
    ADDR = {
        "L": {"flex": "/bone/lowerarm_l/pitch", "pro": "/bone/lowerarm_l/roll"},
        "R": {"flex": "/bone/lowerarm_r/pitch", "pro": "/bone/lowerarm_r/roll"},
    }
    ALL_ADDRS = [ADDR[s]["flex"] for s in ("L","R")] + [ADDR[s]["pro"] for s in ("L","R")]

    report = {"invert": {"L":{"flexion":False,"pronation":False},
                         "R":{"flexion":False,"pronation":False}}}

    dt = 1.0 / args.rate

    def do_test(side: str, chan: str, target_deg: float, expect: str):
        """chan ∈ {'flex','pro'}"""
        # 1) zero everyone first
        zero_channels(client, ALL_ADDRS)
        time.sleep(0.25)

        addr = ADDR[side][chan]
        seq = ramp_hold(args.rate, args.ramp_s, target_deg, args.hold_s)
        print(f"\n{side} {chan.upper()} → sending one-way +{target_deg}° to {addr} (hold {args.hold_s}s)…")
        t0 = time.perf_counter()
        for i, v in enumerate(seq):
            client.send_message(addr, float(v))
            target = t0 + (i+1)*dt
            sleep = max(0.0, target - time.perf_counter())
            if sleep > 0: time.sleep(sleep)

        ok = ask_yes_no(f"Did the motion match this expectation: {expect}?")
        invert = (not ok)
        # 3) reset that channel to zero
        client.send_message(addr, 0.0)
        time.sleep(0.3)
        return invert

    # LEFT FLEXION (+pitch) — expect forearm TOWARD shoulder
    report["invert"]["L"]["flexion"] = do_test(
        "L", "flex", args.amp_flex,
        "LEFT flexion: +pitch should move forearm TOWARD the shoulder (sagittal)"
    )

    # LEFT PRONATION (+roll) — expect palm DOWN (thumb toward midline)
    report["invert"]["L"]["pronation"] = do_test(
        "L", "pro", args.amp_pro,
        "LEFT pronation: +roll should rotate palm DOWN (thumb toward midline)"
    )

    # RIGHT FLEXION (+pitch)
    report["invert"]["R"]["flexion"] = do_test(
        "R", "flex", args.amp_flex,
        "RIGHT flexion: +pitch should move forearm TOWARD the shoulder (sagittal)"
    )

    # RIGHT PRONATION (+roll)
    report["invert"]["R"]["pronation"] = do_test(
        "R", "pro", args.amp_pro,
        "RIGHT pronation: +roll should rotate palm DOWN (thumb toward midline)"
    )

    out = "lowerarm_sign_report_oneway.json"
    with open(out, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nSaved → {os.path.abspath(out)}")
    print("Use these invert flags in your live streamer to flip signs only where needed.")

if __name__ == "__main__":
    main()