#!/usr/bin/env python3
"""
Interactive Axis Tester v3 — fixed address resolution
"""

import os, re, time, math, json
import pandas as pd
from pythonosc.udp_client import SimpleUDPClient

# ----------------------- CONFIG -----------------------
DATA_PATH  = "/Users/martinjaramillo/Documents/Unreal+Rokoko/v5/driving.csv"
BVH_TO_UNREAL_MAP_PATH = "bvh_to_unreal_map.json"
SAVE_PATH = "auto_axis_mapping.json"

HOST, PORT = "127.0.0.1", 9000
RATE_HZ    = 30.0
DURATION   = 4.0      # seconds per axis test
AMPLITUDE  = 30.0     # degrees amplitude
VERBOSE    = True
# ------------------------------------------------------

# Ignore these joints during the test UI
IGNORE_KEYWORDS = ["Head", "HeadTop", "Clavicle", "Shoulder"]

# --- Fallback alias map for common Mixamo → Unreal addresses ---
# You can extend this as needed. Values may be either "/bone/..." or plain bone names.
BVH_ALIAS_TO_UNREAL = {
    # Arms (Left)
    "mixamorig:LeftArm":        "/bone/upperarm_l",
    "mixamorig:LeftForeArm":    "/bone/lowerarm_l",
    "mixamorig:LeftHand":       "/bone/hand_l",
    "LeftArm":                  "/bone/upperarm_l",
    "LeftForeArm":              "/bone/lowerarm_l",
    "LeftHand":                 "/bone/hand_l",

    # Arms (Right)
    "mixamorig:RightArm":       "/bone/upperarm_r",
    "mixamorig:RightForeArm":   "/bone/lowerarm_r",
    "mixamorig:RightHand":      "/bone/hand_r",
    "RightArm":                 "/bone/upperarm_r",
    "RightForeArm":             "/bone/lowerarm_r",
    "RightHand":                "/bone/hand_r",

    # (Optional) Legs – add as needed
    "mixamorig:LeftUpLeg":      "/bone/thigh_l",
    "mixamorig:LeftLeg":        "/bone/calf_l",
    "mixamorig:LeftFoot":       "/bone/foot_l",
    "mixamorig:RightUpLeg":     "/bone/thigh_r",
    "mixamorig:RightLeg":       "/bone/calf_r",
    "mixamorig:RightFoot":      "/bone/foot_r",
    "LeftUpLeg":                "/bone/thigh_l",
    "LeftLeg":                  "/bone/calf_l",
    "LeftFoot":                 "/bone/foot_l",
    "RightUpLeg":               "/bone/thigh_r",
    "RightLeg":                 "/bone/calf_r",
    "RightFoot":                "/bone/foot_r",
}

# --------------------- Helpers ---------------------
def load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, "r") as f:
                return json.load(f)
    except Exception as e:
        print(f"⚠ Failed to load {path}: {e}")
    return default

def save_json(path, obj):
    try:
        with open(path, "w") as f:
            json.dump(obj, f, indent=2)
        print(f"💾 Saved → {path}")
    except Exception as e:
        print(f"⚠ Failed to save {path}: {e}")

def load_bvh_to_unreal_map(path):
    mp = load_json(path, {})
    if not mp:
        print(f"⚠ BVH→Unreal map not found or empty at {path}. Using fallbacks/aliases.")
    else:
        print(f"Loaded BVH→Unreal map ({len(mp)} entries) from {path}")
    return mp

def ensure_addr_stem(v):
    """Accept either '/bone/xyz' or 'xyz' and return '/bone/xyz'."""
    if not v:
        return None
    return v if v.startswith("/bone/") else f"/bone/{v}"

def resolve_addr_stem(joint, bvh_map):
    """
    Resolve the OSC address stem for a BVH joint.
    Priority:
      1) Exact key in bvh_map (value can be bone name or full address)
      2) Namespace-stripped key in bvh_map (e.g., 'LeftForeArm')
      3) Exact key in fallback alias table
      4) Namespace-stripped key in fallback alias table
    """
    base = joint.split(":")[-1]  # strip namespaces like 'mixamorig:'

    # 1) JSON map exact
    if joint in bvh_map:
        stem = ensure_addr_stem(bvh_map[joint])
        if VERBOSE:
            print(f"🗺  Map (exact) {joint} → {stem}")
        return stem

    # 2) JSON map base
    if base in bvh_map:
        stem = ensure_addr_stem(bvh_map[base])
        if VERBOSE:
            print(f"🗺  Map (base)  {base} → {stem}")
        return stem

    # 3) Built-in alias exact
    if joint in BVH_ALIAS_TO_UNREAL:
        stem = ensure_addr_stem(BVH_ALIAS_TO_UNREAL[joint])
        if VERBOSE:
            print(f"🧭 Alias (exact) {joint} → {stem}")
        return stem

    # 4) Built-in alias base
    if base in BVH_ALIAS_TO_UNREAL:
        stem = ensure_addr_stem(BVH_ALIAS_TO_UNREAL[base])
        if VERBOSE:
            print(f"🧭 Alias (base)  {base} → {stem}")
        return stem

    # 5) Last resort: warn and use sanitized joint name (will likely be wrong)
    sanitized = base.lower().replace("left", "l").replace("right", "r")
    stem = f"/bone/{sanitized}"
    print(f"⚠ No mapping for '{joint}'. Falling back to {stem}")
    return stem

def ramp(rate, dur, amp):
    import numpy as np
    n = max(2, int(rate * dur))
    t = np.linspace(0, math.pi, n)
    return list(amp * (1 - np.cos(t)) / 2.0)

def send_axes(client, addr_stem, p, y, r):
    client.send_message(f"{addr_stem}/pitch", float(p))
    client.send_message(f"{addr_stem}/yaw",   float(y))
    client.send_message(f"{addr_stem}/roll",  float(r))
    if VERBOSE:
        print(f"SENT {addr_stem}/pitch {p:+6.1f} | yaw {y:+6.1f} | roll {r:+6.1f}")

def zero_axes(client, addr_stem):
    send_axes(client, addr_stem, 0.0, 0.0, 0.0)
    time.sleep(0.25)

def ask_action(axis_label):
    print(f"\nWhat did the movement of {axis_label.upper()} look like?")
    print("  [1] Sagittal  (forward/back) → pitch")
    print("  [2] Coronal   (side to side) → yaw")
    print("  [3] Transverse(twist)        → roll")
    print("  [r] Repeat this axis")
    print("  [q] Skip this axis only")
    print("  [b] Back to previous axis")
    print("  [j] Skip this entire joint")
    print("  [save] Save current progress")
    while True:
        c = input("Your choice: ").strip().lower()
        if c in ("1","s","sagittal"):   return "pitch"
        if c in ("2","c","coronal"):    return "yaw"
        if c in ("3","t","transverse"): return "roll"
        if c in ("r","repeat"):         return "repeat"
        if c in ("q","quit"):           return "skip_axis"
        if c in ("b","back"):           return "back"
        if c in ("j","joint"):          return "skip_joint"
        if c in ("save","w"):           return "save"
        print("Please choose 1/2/3, r, q, b, j, or save.")

def should_ignore(joint):
    return any(kw.lower() in joint.lower() for kw in IGNORE_KEYWORDS)

# ------------------------ Main ------------------------
def main():
    if not os.path.exists(DATA_PATH):
        raise SystemExit(f"Data file not found: {DATA_PATH}")
    df = pd.read_csv(DATA_PATH)

    # Required CSV columns
    for col in ("joint", "x_deg", "y_deg", "z_deg"):
        if col not in df.columns:
            raise SystemExit(f"Missing column: {col}")

    # Load name map and any existing mappings
    bvh_map = load_bvh_to_unreal_map(BVH_TO_UNREAL_MAP_PATH)
    mappings = load_json(SAVE_PATH, {})
    if mappings:
        print(f"↩ Resuming from existing mappings: {len(mappings)} joints already saved")

    client = SimpleUDPClient(HOST, PORT)

    joints = sorted(df["joint"].unique())
    print(f"\nFound {len(joints)} joints in file.")

    for joint in joints:
        if should_ignore(joint):
            print(f"⏭ Ignoring {joint} (ignored keyword)")
            continue

        addr_stem = resolve_addr_stem(joint, bvh_map)
        print(f"\n==================== {joint} → {addr_stem} ====================")

        # If this joint already fully mapped, skip
        if addr_stem in mappings and len(mappings[addr_stem]) == 3:
            print("Already fully mapped — skipping.")
            continue

        # Axis order & index; allow going back
        axis_order = ["x_deg", "y_deg", "z_deg"]
        i = 0
        current_map = dict(mappings.get(addr_stem, {}))  # resume partial per joint

        while 0 <= i < len(axis_order):
            src_axis = axis_order[i]
            if src_axis in current_map:
                print(f"(Already mapped {src_axis} → {current_map[src_axis].upper()})")

            # Generate and play sequence for this axis
            seq = ramp(RATE_HZ, DURATION, AMPLITUDE)
            print(f"\nTesting {src_axis.upper()} for {joint} ({addr_stem})...")
            t0 = time.perf_counter()
            for val in seq:
                if src_axis == "x_deg":
                    send_axes(client, addr_stem, val, 0.0, 0.0)
                elif src_axis == "y_deg":
                    send_axes(client, addr_stem, 0.0, val, 0.0)
                else:
                    send_axes(client, addr_stem, 0.0, 0.0, val)
                # pacing
                target = t0 + (1.0 / RATE_HZ)
                now = time.perf_counter()
                if target > now:
                    time.sleep(target - now)
                t0 = target
            zero_axes(client, addr_stem)

            # Ask what it looked like
            action = ask_action(src_axis)

            if action == "repeat":
                continue

            if action == "skip_axis":
                if src_axis in current_map:
                    del current_map[src_axis]
                print(f"⏭ Skipping {src_axis} for {joint}")
                i += 1
                continue

            if action == "back":
                if src_axis in current_map:
                    del current_map[src_axis]
                i = max(0, i - 1)
                print("↩ Going back to previous axis.")
                continue

            if action == "skip_joint":
                print("⏭ Skipping entire joint.")
                current_map = mappings.get(addr_stem, current_map)
                break

            if action == "save":
                tmp = dict(mappings)
                if current_map:
                    tmp[addr_stem] = current_map
                save_json(SAVE_PATH, tmp)
                continue

            # Otherwise action is a destination axis: pitch/yaw/roll
            current_map[src_axis] = action
            print(f"✓ {src_axis} → {action.upper()}")
            i += 1

        # Store results for this joint (even if partial)
        if current_map:
            mappings[addr_stem] = current_map
            print(f"✅ Current mapping for {addr_stem}: {current_map}")
            save_json(SAVE_PATH, mappings)

    # Final save
    save_json(SAVE_PATH, mappings)
    print(f"\nDone. Total joints with any mapping: {len(mappings)}")
    print(f"Result file: {SAVE_PATH}")

if __name__ == "__main__":
    main()