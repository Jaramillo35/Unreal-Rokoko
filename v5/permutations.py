#!/usr/bin/env python3
"""
Arm Axis Simple Mapper — ask-after-each-axis, map directly from your answers.

For each bone:
  1) X-only sweep → ask: sagittal / coronal / transverse ?
  2) Y-only sweep → ask: sagittal / coronal / transverse ?
  3) Z-only sweep → ask: sagittal / coronal / transverse ?

We then map:
  sagittal   -> pitch
  coronal    -> yaw
  transverse -> roll

If duplicates occur (e.g., both X and Y answered 'sagittal'), we warn and let you redo that bone.
Results saved to JSON.

Example:
  python ArmAxis_SimpleMapper.py --ip 127.0.0.1 --port 9000 --rate 30 \
      --amp-x 20 --amp-y 20 --amp-z 20 --ramp-s 4 --hold-s 1.5 --start-delay 3
"""

import argparse
import json
import math
import os
import time
from typing import Dict, List

from pythonosc.udp_client import SimpleUDPClient

# ---------- Bones you requested ----------
ARM_BONES = [
    "upperarm_l","lowerarm_l","hand_l",
    "upperarm_r","lowerarm_r","hand_r",
]
# ----------------------------------------

PLANE_TO_UNREAL = {
    "sagittal":   "pitch",     # forward/back (flex-ext)
    "coronal":    "yaw",       # to the sides (ab/adduct)
    "transverse": "roll",      # twist (int/ext rot)
}

PROMPT = (
    "\nWhat did it look like?\n"
    "  [1] Sagittal (forward/back)\n"
    "  [2] Coronal  (to the sides)\n"
    "  [3] Transverse (twist)\n"
    "  [r] Repeat this axis test\n"
    "  [q] Skip this bone\n"
    "Your choice: "
)

def ramp_hold(rate_hz: float, ramp_s: float, target: float, hold_s: float) -> List[float]:
    """Cosine ramp 0→target, then hold."""
    n_up = max(2, int(ramp_s * rate_hz))
    up = [target * (1 - math.cos(math.pi * (i / (n_up - 1)))) / 2.0 for i in range(n_up)]
    n_hold = max(1, int(hold_s * rate_hz))
    return [float(v) for v in up] + [float(target)] * n_hold

def send_axes(client: SimpleUDPClient, bone: str, pitch: float, roll: float, yaw: float, verbose: bool = True):
    a_pitch = f"/bone/{bone}/pitch"
    a_roll  = f"/bone/{bone}/roll"
    a_yaw   = f"/bone/{bone}/yaw"
    if verbose:
        print(f"→ {a_pitch}: {pitch:.2f}")
        print(f"→ {a_roll}:  {roll:.2f}")
        print(f"→ {a_yaw}:   {yaw:.2f}")
    client.send_message(a_pitch, float(pitch))
    client.send_message(a_roll,  float(roll))
    client.send_message(a_yaw,   float(yaw))

def zero_axes(client: SimpleUDPClient, bone: str):
    send_axes(client, bone, 0.0, 0.0, 0.0)
    time.sleep(0.3)

def ask_plane() -> str:
    """Return 'sagittal'|'coronal'|'transverse' or 'repeat'|'quit'."""
    while True:
        c = input(PROMPT).strip().lower()
        if c in ("1","s","sagittal"):   return "sagittal"
        if c in ("2","c","coronal"):    return "coronal"
        if c in ("3","t","transverse"): return "transverse"
        if c in ("r","repeat"):         return "repeat"
        if c in ("q","quit"):           return "quit"
        print("Please choose 1/2/3, or r to repeat, q to skip.")

def drive_src_and_ask(client: SimpleUDPClient, bone: str,
                      which_src: str, amp: float, rate: float,
                      ramp_s: float, hold_s: float) -> str:
    """
    Drive only one source axis by mapping it straight onto (pitch,roll,yaw)
    one-at-a-time to make the plane obvious:
      - When testing X: send to pitch only (others zero) so you judge the plane.
      - Then repeat: send to yaw only.
      - Then repeat: send to roll only.
    But to keep it simple and short, we'll do a single pass that maps source
    directly to all three Unreal axes according to "identity" for visual clarity:
      X-only sweep drives pitch; Y-only drives yaw; Z-only drives roll.
    The cues are about the PLANE you saw on the body.
    """
    dt = 1.0 / rate

    if which_src == "x":
        axis_label = "X-only → expect PITCH-like motion (sagittal)"
        addr_axis  = "pitch"
        target     = amp
    elif which_src == "y":
        axis_label = "Y-only → expect YAW-like motion (coronal)"
        addr_axis  = "yaw"
        target     = amp
    else:
        axis_label = "Z-only → expect ROLL-like motion (transverse)"
        addr_axis  = "roll"
        target     = amp

    print(f"\n[{bone}] {axis_label}")
    seq = ramp_hold(rate, ramp_s, target, hold_s)
    t0 = time.perf_counter()
    for i, v in enumerate(seq):
        p = v if addr_axis == "pitch" else 0.0
        y = v if addr_axis == "yaw"   else 0.0
        r = v if addr_axis == "roll"  else 0.0
        verbose = (i % max(1, int(rate/6)) == 0) or (i == 0) or (i == len(seq)-1)
        send_axes(client, bone, p, r, y, verbose=verbose)
        target_t = t0 + (i+1)*dt
        sleep = target_t - time.perf_counter()
        if sleep > 0: time.sleep(sleep)
    zero_axes(client, bone)

    # Ask user which plane they saw
    while True:
        plane = ask_plane()
        if plane == "repeat":
            # run again
            return drive_src_and_ask(client, bone, which_src, amp, rate, ramp_s, hold_s)
        return plane  # 'sagittal'|'coronal'|'transverse' or 'quit'

def map_from_planes(plane_x: str, plane_y: str, plane_z: str) -> Dict[str, str]:
    """
    Convert plane answers into mapping from source to Unreal axes:
      plane -> axis via PLANE_TO_UNREAL
      returns: {'x_deg': <axis>, 'y_deg': <axis>, 'z_deg': <axis>}
    """
    return {
        "x_deg": PLANE_TO_UNREAL[plane_x],
        "y_deg": PLANE_TO_UNREAL[plane_y],
        "z_deg": PLANE_TO_UNREAL[plane_z],
    }

def mapping_is_bijective(src2dst: Dict[str,str]) -> bool:
    """Ensure pitch, roll, yaw are used exactly once."""
    dst = list(src2dst.values())
    return sorted(dst) == ["pitch","roll","yaw"]

def main():
    ap = argparse.ArgumentParser(description="Arm Axis Simple Mapper")
    ap.add_argument("--ip", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=9000)
    ap.add_argument("--rate", type=float, default=30.0)
    ap.add_argument("--start-delay", type=float, default=3.0)

    ap.add_argument("--amp-x", type=float, default=20.0)
    ap.add_argument("--amp-y", type=float, default=20.0)
    ap.add_argument("--amp-z", type=float, default=20.0)

    ap.add_argument("--ramp-s", type=float, default=4.0)
    ap.add_argument("--hold-s", type=float, default=1.5)

    ap.add_argument("--out", default="arm_axis_map_simple.json")
    args = ap.parse_args()

    client = SimpleUDPClient(args.ip, args.port)
    print(f"OSC → {args.ip}:{args.port} @ {args.rate:.1f} Hz (format: /bone/<bone>/<axis>)")
    if args.start_delay > 0:
        print(f"Starting in {args.start_delay:.1f}s…")
        time.sleep(args.start_delay)

    results: Dict[str, Dict[str, str]] = {}

    for bone in ARM_BONES:
        print(f"\n==================== {bone} ====================")
        while True:
            # X-only (pitch drive)
            px = drive_src_and_ask(client, bone, "x", args.amp_x, args.rate, args.ramp_s, args.hold_s)
            if px == "quit":
                print("Skipping bone."); break

            # Y-only (yaw drive)
            py = drive_src_and_ask(client, bone, "y", args.amp_y, args.rate, args.ramp_s, args.hold_s)
            if py == "quit":
                print("Skipping bone."); break

            # Z-only (roll drive)
            pz = drive_src_and_ask(client, bone, "z", args.amp_z, args.rate, args.ramp_s, args.hold_s)
            if pz == "quit":
                print("Skipping bone."); break

            # Build mapping directly from plane answers
            src2dst = map_from_planes(px, py, pz)

            # Validate uniqueness
            if not mapping_is_bijective(src2dst):
                print("\n⚠ Detected duplicates in mapping:")
                print(json.dumps(src2dst, indent=2))
                retry = input("Responses conflict (two sources mapped to same Unreal axis). Redo this bone? [Y/n]: ").strip().lower()
                if retry in ("", "y", "yes"):
                    continue
                else:
                    print("Leaving bone unmapped due to conflict.")
                    break

            # Show summary & confirm
            print("\nProposed mapping for", bone)
            print(json.dumps(src2dst, indent=2))
            ok = input("Accept? [Y/n]: ").strip().lower()
            if ok in ("", "y", "yes"):
                results[bone] = src2dst
                print(f"✔ Saved mapping for {bone}")
                break
            else:
                print("Okay, let’s redo that bone…")

    # Persist results
    with open(args.out, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved → {os.path.abspath(args.out)}")
    if results:
        print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()