#!/usr/bin/env python3
"""
Arms Axis Mapper (interactive; no BVH) — run with:  python arms_mapper.py

• Drives each arm joint (L then R), sweeping Unreal pitch → yaw → roll.
• After each sweep, asks which plane you observed (sagittal / coronal / transverse).
• Builds a per-joint BVH→Unreal map and saves after each joint.
• **Prints the exact Unreal OSC addresses** used for each joint & sweep.

CSV in:
    /Users/martinjaramillo/Documents/Unreal+Rokoko/v5/bvh_euler_to_unreal_map.csv
Required columns:
    unreal_bone, addr_pitch, addr_yaw, addr_roll

CSV out:
    /Users/martinjaramillo/Documents/Unreal+Rokoko/v5/arm_bvh_to_unreal_map.csv
Columns:
    unreal_bone, pitch_src, yaw_src, roll_src   (sources are X/Y/Z)
"""

import sys
import time
import pandas as pd
from typing import Dict, List, Tuple
from pythonosc.udp_client import SimpleUDPClient

# -------- CONFIG --------
MAPPING_CSV = "/Users/martinjaramillo/Documents/Unreal+Rokoko/v5/bvh_euler_to_unreal_map.csv"
OUT_CSV     = "/Users/martinjaramillo/Documents/Unreal+Rokoko/v5/arm_bvh_to_unreal_map.csv"
IP, PORT    = "127.0.0.1", 9000
FPS         = 30.0
AMP_DEG     = 30.0
DUR_S       = 2.2
VERBOSE     = True

# Print every OSC send? (can be very chatty). If False, prints a few samples per sweep.
PRINT_EVERY_SEND = False
# ------------------------

ARM_BONES = [
    "clavicle_l","upperarm_l","lowerarm_l","hand_l",
    "clavicle_r","upperarm_r","lowerarm_r","hand_r",
]

PLANE_ALIASES = {
    "sagittal": {"s","sag","sagittal","forward","front","back","forwards"},
    "coronal":  {"c","cor","coronal","side","sides","abduct","adduct","lateral"},
    "transverse":{"t","trans","transverse","twist","rotate","rotation","axial"},
}

AXES = ("pitch","yaw","roll")  # Unreal axes

def load_mapping(path: str) -> pd.DataFrame:
    m = pd.read_csv(path)
    required = {"unreal_bone","addr_pitch","addr_yaw","addr_roll"}
    miss = required - set(m.columns)
    if miss:
        raise ValueError(f"Mapping CSV missing columns: {sorted(miss)}")
    m = m[list(required)].dropna(subset=["unreal_bone"]).drop_duplicates("unreal_bone", keep="last")
    return m

def zero_rows(client: SimpleUDPClient, rows: pd.DataFrame):
    for _, r in rows.iterrows():
        client.send_message(r["addr_pitch"], 0.0)
        client.send_message(r["addr_yaw"],   0.0)
        client.send_message(r["addr_roll"],  0.0)

def sweep_axis(client: SimpleUDPClient, addr_p: str, addr_y: str, addr_r: str, axis: str,
               amp_deg: float, dur_s: float, fps: float):
    """Sweep one Unreal axis (+amp → -amp → 0) for a single joint, printing addresses/values."""
    assert axis in AXES
    frames = max(1, int(dur_s * fps))
    seg = max(1, frames // 3)
    key = [0.0, +amp_deg, -amp_deg, 0.0]

    cue = {
        "pitch": "PITCH (Unreal X) — EXPECT: sagittal (forward/back).",
        "yaw":   "YAW   (Unreal Y) — EXPECT: transverse (twist).",
        "roll":  "ROLL  (Unreal Z) — EXPECT: coronal (to the sides).",
    }[axis]
    print(f"\n   → Sweep {axis.upper()}: {cue}")
    print(f"     Addresses: pitch→{addr_p} | yaw→{addr_y} | roll→{addr_r}")

    t_ref = time.perf_counter()
    # throttle printing if not printing every send
    sample_every = 1 if PRINT_EVERY_SEND else max(1, seg // 6)
    sample_idx = 0

    for si in range(3):
        a0, a1 = key[si], key[si+1]
        for k in range(seg):
            t = k / (seg - 1) if seg > 1 else 1.0
            deg = (1.0 - t)*a0 + t*a1
            p = float(deg) if axis=="pitch" else 0.0
            y = float(deg) if axis=="yaw"   else 0.0
            r = float(deg) if axis=="roll"  else 0.0

            client.send_message(addr_p, p)
            client.send_message(addr_y, y)
            client.send_message(addr_r, r)

            # print address + value (throttled)
            if PRINT_EVERY_SEND or (sample_idx % sample_every == 0):
                if p != 0.0:
                    print(f"     SEND {addr_p:<35} = {p:+7.2f}")
                if y != 0.0:
                    print(f"     SEND {addr_y:<35} = {y:+7.2f}")
                if r != 0.0:
                    print(f"     SEND {addr_r:<35} = {r:+7.2f}")
            sample_idx += 1

            # pacing
            t_next = t_ref + (1.0 / fps); t_ref = t_next
            slp = t_next - time.perf_counter()
            if slp > 0: time.sleep(slp)
    print("   ✓ Sweep done.")

def ask_plane() -> str:
    while True:
        ans = input("      Which plane did that look like? "
                    "[sagittal (forward/back) | coronal (to the sides) | transverse (twist)]\n"
                    "      (you can also type: forward / sides / twist, or 'redo') > ").strip().lower()
        if ans == "redo":
            return "redo"
        if ans in PLANE_ALIASES["sagittal"] or "forward" in ans:
            return "sagittal"
        if ans in PLANE_ALIASES["coronal"]  or "side" in ans:
            return "coronal"
        if ans in PLANE_ALIASES["transverse"] or "twist" in ans or "rotate" in ans:
            return "transverse"
        print("      🤔 Try: sagittal / coronal / transverse, or 'redo'.")

def invert_to_bvh_sources(plane_for_axis: Dict[str,str]) -> Dict[str,str]:
    """plane_for_axis: {'pitch':'sagittal','yaw':'transverse','roll':'coronal'} → {'pitch':'Z','yaw':'Y','roll':'X'}"""
    plane_to_bvh = {"sagittal":"Z", "transverse":"Y", "coronal":"X"}
    return {ax: plane_to_bvh.get(plane, "Z") for ax, plane in plane_for_axis.items()}

def save_partial(csv_path: str, table: List[Tuple[str,str,str,str]]):
    df = pd.DataFrame(table, columns=["unreal_bone","pitch_src","yaw_src","roll_src"])
    df.to_csv(csv_path, index=False)
    print(f"💾 Saved mapping so far → {csv_path}")

def main():
    # Load mapping; filter to arm bones present
    try:
        mapping = load_mapping(MAPPING_CSV)
    except Exception as e:
        print(f"❌ Failed to load mapping: {e}")
        return

    available = set(mapping["unreal_bone"])
    arm_list = [b for b in ARM_BONES if b in available]
    if not arm_list:
        print("❌ No arm bones found in mapping CSV.")
        return

    print("🎛️ Arms Axis Mapper — one joint at a time.")
    print("Joints to map:", ", ".join(arm_list))
    print("Cues:\n  • Sagittal = forward/back (flex/extend)\n  • Coronal = to the sides (ab/adduction / side tilt)\n  • Transverse = twist (axial rotation)")
    print("Printing OSC addresses being used. Set PRINT_EVERY_SEND=True to log every send.\n")

    client = SimpleUDPClient(IP, PORT)
    results: List[Tuple[str,str,str,str]] = []

    for bone in arm_list:
        row = mapping[mapping["unreal_bone"] == bone]
        addr_p, addr_y, addr_r = row["addr_pitch"].values[0], row["addr_yaw"].values[0], row["addr_roll"].values[0]

        print("\n" + "="*70)
        print(f"🦴 Mapping joint: {bone}")
        print(f"   Using addresses:\n     pitch → {addr_p}\n     yaw   → {addr_y}\n     roll  → {addr_r}")

        # zero before starting
        client.send_message(addr_p, 0.0); client.send_message(addr_y, 0.0); client.send_message(addr_r, 0.0)
        time.sleep(0.25)

        plane_for_axis: Dict[str,str] = {}
        for axis in AXES:
            while True:
                sweep_axis(client, addr_p, addr_y, addr_r, axis, AMP_DEG, DUR_S, FPS)
                plane = ask_plane()
                if plane == "redo":
                    print("   ↻ Repeating that sweep...")
                    continue
                plane_for_axis[axis] = plane
                break

        # Compute BVH sources per Unreal axis
        sources = invert_to_bvh_sources(plane_for_axis)
        print(f"📝 Result for {bone}: pitch←{sources['pitch']}  yaw←{sources['yaw']}  roll←{sources['roll']}")
        results.append((bone, sources["pitch"], sources["yaw"], sources["roll"]))

        # zero before next bone
        client.send_message(addr_p, 0.0); client.send_message(addr_y, 0.0); client.send_message(addr_r, 0.0)
        time.sleep(0.25)

        # Save partial after each bone (safety)
        save_partial(OUT_CSV, results)

        nxt = input("Proceed to next joint? [Enter=Yes / 'skip' to skip next / 'quit' to stop] > ").strip().lower()
        if nxt == "quit":
            break

    save_partial(OUT_CSV, results)
    print("\n✅ Done. If nothing moves, verify Unreal is listening on", f"{IP}:{PORT}", "and that the addresses above match your Control Rig.")

if __name__ == "__main__":
    main()