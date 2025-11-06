#!/usr/bin/env python3
# stream_csv_to_unreal.py
# Streams CSV (or BVH-derived CSV) frames into Unreal via OSC using mapping/signs.
# Automatically loads /mnt/data/bvh_to_unreal_map.json if present.

import time, math, re, os, sys, json
import pandas as pd
from pythonosc.udp_client import SimpleUDPClient

# ----------------------- USER CONFIG -----------------------
CSV_PATH  = "/Users/martinjaramillo/Documents/Unreal+Rokoko/v5/driving.csv"
HOST      = "127.0.0.1"
PORT      = 9000
REALTIME  = True     # match CSV timing (~30 FPS)
RADIANS   = False    # send radians instead of degrees
VERBOSE   = True     # print every OSC address used

# Optional fallback for this environment
if not os.path.exists(CSV_PATH) and os.path.exists("/mnt/data/driving.csv"):
    CSV_PATH = "/mnt/data/driving.csv"

# --- Optional BVH→Unreal bone map (JSON) ---
BVH_TO_UNREAL_MAP_PATH = "/mnt/data/bvh_to_unreal_map.json"
BVH_TO_UNREAL_MAP = {}
try:
    if os.path.exists(BVH_TO_UNREAL_MAP_PATH):
        with open(BVH_TO_UNREAL_MAP_PATH, "r") as f:
            BVH_TO_UNREAL_MAP = json.load(f) or {}
        if VERBOSE:
            print(f"Loaded BVH→Unreal map: {BVH_TO_UNREAL_MAP_PATH} ({len(BVH_TO_UNREAL_MAP)} entries)")
except Exception as e:
    print(f"⚠ Could not load BVH→Unreal map: {e}")
    BVH_TO_UNREAL_MAP = {}

# -------------- Per-bone XYZ→Unreal axis mapping --------------
PER_BONE_AXIS_MAP = {
    "upperarm_l": {"x_deg": "yaw",   "y_deg": "pitch", "z_deg": "roll"},
    "hand_l":     {"x_deg": "pitch", "y_deg": "yaw",   "z_deg": "roll"},
    "upperarm_r": {"x_deg": "pitch",   "y_deg": "yaw", "z_deg": "roll"},
    "hand_r":     {"x_deg": "pitch", "y_deg": "yaw",   "z_deg": "roll"},
}
# ---------------------------------------------------------------

SIGNS = {
    ("Shoulder","L"): {"pitch": +1, "yaw": +1, "roll": -1},
    ("Shoulder","R"): {"pitch": -1, "yaw": +1, "roll": +1},
    ("Elbow",   "L"): {"pitch": +1, "yaw": +1, "roll": +1},
    ("Elbow",   "R"): {"pitch": +1, "yaw": +1, "roll": +1},
    ("Wrist",   "L"): {"pitch": +1, "yaw": +1, "roll": +1},
    ("Wrist",   "R"): {"pitch": +1, "yaw": +1, "roll": +1},
    ("Finger","L"):  {"pitch": -1, "yaw": +1, "roll": -1},
    ("Finger","R"):  {"pitch": -1, "yaw": +1, "roll": -1},
    ("Thigh","L"):   {"pitch": +1, "yaw": +1, "roll": -1},
    ("Thigh","R"):   {"pitch": +1, "yaw": -1, "roll": +1},
    ("Calf", "L"):   {"pitch": +1, "yaw": +1, "roll": +1},
    ("Calf", "R"):   {"pitch": +1, "yaw": +1, "roll": +1},
    ("Foot", "L"):   {"pitch": +1, "yaw": +1, "roll": +1},
    ("Foot", "R"):   {"pitch": +1, "yaw": +1, "roll": +1},
    ("Ball", "L"):   {"pitch": +1, "yaw": +1, "roll": +1},
    ("Ball", "R"):   {"pitch": +1, "yaw": +1, "roll": +1},
}

# -------------------- Helper Functions --------------------
def send_axis(client, addr_stem: str, axis: str, value_deg: float, sign: int):
    val = value_deg * sign
    if RADIANS:
        val = math.radians(val)
    full = f"{addr_stem}/{axis}"
    client.send_message(full, float(val))
    if VERBOSE:
        print(f"SENT {full:<35} {val:+8.3f}")

def _side_letter(side_word: str) -> str:
    return "l" if side_word == "Left" else "r"

# ---------- Unreal bone resolver (used by JSON mapping) ----------
def _unreal_bone_to_kind_and_stem(bone_name: str):
    if bone_name == "pelvis":   return ("Pelvis", None, "/bone/pelvis")
    if bone_name.startswith("spine_"): return ("Thorax", None, f"/bone/{bone_name}")
    if bone_name == "neck_01":  return ("Neck", None, "/bone/neck_01")
    if bone_name == "head":     return ("Neck", None, "/bone/head")

    m = re.match(r".*_(l|r)$", bone_name)
    s = m.group(1) if m else None

    arm = {"upperarm":"Shoulder","lowerarm":"Elbow","hand":"Wrist"}
    leg = {"thigh":"Thigh","calf":"Calf","foot":"Foot","ball":"Ball"}
    for k,v in arm.items():
        if bone_name.startswith(k) and s:
            return (v, s, f"/bone/{bone_name}")
    for k,v in leg.items():
        if bone_name.startswith(k) and s:
            return (v, s, f"/bone/{bone_name}")

    fm = re.match(r"(thumb|index|middle|ring|pinky)_(0[1-3])_(l|r)$", bone_name)
    if fm:
        digit, slot, s = fm.groups()
        return ("Finger", s, f"/bone/{digit}_{slot}_{s}")

    return None
# ----------------------------------------------------------------

# ---------- Main mixamo_stem resolver (uses JSON first) ----------
def mixamo_stem(joint: str):
    # 1) External BVH→Unreal JSON map
    if joint in BVH_TO_UNREAL_MAP:
        unreal_bone = BVH_TO_UNREAL_MAP[joint]
        resolved = _unreal_bone_to_kind_and_stem(unreal_bone)
        if resolved:
            return resolved
        return None

    # 2) Fallback regex for legacy Mixamo naming
    m = re.match(r"mixamorig:(Left|Right)(Arm|ForeArm|Hand|UpLeg|Leg|Foot|ToeBase)$", joint)
    if m:
        side, seg = m.groups()
        s = _side_letter(side)
        table = {
            "Arm":     ("Shoulder", f"/bone/upperarm_{s}"),
            "ForeArm": ("Elbow",    f"/bone/lowerarm_{s}"),
            "Hand":    ("Wrist",    f"/bone/hand_{s}"),
            "UpLeg":   ("Thigh",    f"/bone/thigh_{s}"),
            "Leg":     ("Calf",     f"/bone/calf_{s}"),
            "Foot":    ("Foot",     f"/bone/foot_{s}"),
            "ToeBase": ("Ball",     f"/bone/ball_{s}"),
        }
        kind, addr = table[seg]
        return kind, s, addr

    if joint == "mixamorig:Hips":   return ("Pelvis", None, "/bone/pelvis")
    if joint == "mixamorig:Spine2": return ("Thorax", None, "/bone/spine_03")
    if joint == "mixamorig:Neck":   return ("Neck",   None, "/bone/neck_01")

    m = re.match(r"mixamorig:(Left|Right)Hand(Thumb|Index|Middle|Ring|Pinky)([1-3])$", joint)
    if m:
        side, digit, slot = m.groups()
        s = _side_letter(side)
        name_map = {"Thumb":"thumb","Index":"index","Middle":"middle","Ring":"ring","Pinky":"pinky"}
        stem = f"/bone/{name_map[digit]}_0{slot}_{s}"
        return ("Finger", s, stem)

    return None
# ----------------------------------------------------------------

def _invert_permutation_map(axis_map: dict) -> dict:
    return {v:k for k,v in axis_map.items()}

# ------------------------------- MAIN -------------------------------
def main():
    if not os.path.exists(CSV_PATH):
        raise SystemExit(f"CSV not found: {CSV_PATH}")

    df = pd.read_csv(CSV_PATH)
    has_xyz = all(c in df.columns for c in ("x_deg","y_deg","z_deg"))
    has_pry = all(c in df.columns for c in ("pitch_deg","yaw_deg","roll_deg"))
    if not has_xyz and not has_pry:
        raise SystemExit("CSV must have either x_deg/y_deg/z_deg or pitch_deg/yaw_deg/roll_deg.")

    if "joint" not in df.columns:
        raise SystemExit("CSV missing 'joint' column.")

    client = SimpleUDPClient(HOST, PORT)

    if VERBOSE:
        print(f"Loaded: {CSV_PATH}")
        if "frame" in df.columns:
            print(f"Frames: {df['frame'].nunique()}  Rows: {len(df)}")
        else:
            print(f"Rows: {len(df)}")

    frames = sorted(df["frame"].unique()) if "frame" in df.columns else [0]
    if "frame" not in df.columns:
        df["frame"] = 0
    t0_wall = time.time()
    t0_csv  = df.loc[df["frame"]==frames[0], "time"].iloc[0] if "time" in df.columns else 0.0

    for fr in frames:
        rows = df[df["frame"]==fr]
        if REALTIME and "time" in df.columns:
            t_csv = rows["time"].iloc[0] - t0_csv
            while (time.time() - t0_wall) < t_csv:
                time.sleep(0.0005)

        for _, r in rows.iterrows():
            m = mixamo_stem(r["joint"])
            if not m: 
                continue
            kind, side_letter, stem = m

            if kind in ("Pelvis","Thorax","Neck"):
                s_pitch = s_yaw = s_roll = 1
            else:
                k_for_sign = "Finger" if kind=="Finger" else kind
                sdict = SIGNS.get((k_for_sign, "L" if side_letter=="l" else "R"),
                                  {"pitch":1,"yaw":1,"roll":1})
                s_pitch, s_yaw, s_roll = sdict["pitch"], sdict["yaw"], sdict["roll"]

            bone_key = stem.split("/")[-1]
            if has_xyz and bone_key in PER_BONE_AXIS_MAP:
                inv = _invert_permutation_map(PER_BONE_AXIS_MAP[bone_key])
                v_pitch = float(r[inv["pitch"]])
                v_yaw   = float(r[inv["yaw"]])
                v_roll  = float(r[inv["roll"]])
            elif has_pry:
                v_pitch = float(r["pitch_deg"])
                v_yaw   = float(r["yaw_deg"])
                v_roll  = float(r["roll_deg"])
            elif has_xyz:
                v_pitch = float(r["x_deg"])
                v_yaw   = float(r["y_deg"])
                v_roll  = float(r["z_deg"])
            else:
                continue

            send_axis(client, stem, "pitch", v_pitch, s_pitch)
            send_axis(client, stem, "yaw",   v_yaw,   s_yaw)
            send_axis(client, stem, "roll",  v_roll,  s_roll)

    if VERBOSE:
        print("✅ Done streaming.")

# -------------------------------------------------------------------
if __name__ == "__main__":
    main()