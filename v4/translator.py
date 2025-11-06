"""
JCS→Unreal OSC streamer (torso + arms + fingers + legs) with INTERRUPTIBLE interactive control.

Type at any time:
  Baseline | LeftTurn | RightTurn | quit

What’s included:
- Pelvis, Spine (spine_03), Neck
- Shoulders, Elbows, Wrists
- Fingers (Digits 1–5) with THUMB aliasing: Digit1==Thumb, CMC/MCP/IP → thumb_01/02/03
- Legs: Thigh, Calf, Foot, Ball (Unreal bones)

Behavior:
- Sends EVERY mapped Unreal address each frame.
- If a CSV column is missing, it still sends the address with 0.0 so ABP stays consistent.
- Use --finger-debug to print detailed finger matches/skips.
"""

import argparse, os, time, sys, threading, queue
from typing import List, Tuple, Iterable, Dict, Optional
import numpy as np
import pandas as pd
from pythonosc.udp_client import SimpleUDPClient

# ==================== STAGE TOGGLES ====================
ENABLE_TORSO     = True
ENABLE_SHOULDERS = True
ENABLE_ELBOWS    = True
ENABLE_WRISTS    = True
ENABLE_FINGERS   = True
ENABLE_LEGS      = True
# =======================================================

# Which axes are enabled per group (controls address inclusion)
ENABLE_AXES: Dict[str, Dict[str, bool]] = {
    "Torso":    {"pitch": True, "yaw": True, "roll": True},
    "Shoulder": {"pitch": True, "yaw": True, "roll": True},
    "Elbow":    {"pitch": True, "yaw": False, "roll": True},   # yaw unused
    "Wrist":    {"pitch": True, "yaw": True, "roll": True},
    "Finger":   {"pitch": True, "yaw": True, "roll": True},
    # Legs
    "Thigh":    {"pitch": True, "yaw": True, "roll": True},
    "Calf":     {"pitch": True, "yaw": False, "roll": False},   # Pitch only (your BP)
    "Foot":     {"pitch": True, "yaw": True, "roll": True},
    "Ball":     {"pitch": True, "yaw": False, "roll": False},   # Pitch only (your BP)
}

# Interactive command → path (edit these to your files if needed)
INTERACTIVE_PATHS = {
    "baseline": "/Users/martinjaramillo/Downloads/BaseLine(SittingPosition)_filtered_3000_to_6700.csv", # "baseline":  "/Users/martinjaramillo/Documents/Unreal+Rokoko/data/BaseLine(SittingPosition).csv",
    "leftturn": "/Users/martinjaramillo/Downloads/LeftTurn_10times_filtered_3000_to_6700.csv", #"leftturn":  "/Users/martinjaramillo/Documents/Unreal+Rokoko/data/LeftTurn_10times.csv",
    "rightturn": "/Users/martinjaramillo/Downloads/RightTurn_10times_filtered_3000_to_6700.csv", #"rightturn": "/Users/martinjaramillo/Documents/Unreal+Rokoko/data/RightTurn_10times.csv",
}

# Default CSV used by --csv for non-interactive one-off runs
CSV_DEFAULT = INTERACTIVE_PATHS["leftturn"]

# -------------- Address stems (arms & legs) ----------------------------------
ADDR = {
    # Arms
    ("Shoulder","L"): "/bone/upperarm_l",
    ("Shoulder","R"): "/bone/upperarm_r",
    ("Elbow",   "L"): "/bone/lowerarm_l",
    ("Elbow",   "R"): "/bone/lowerarm_r",
    ("Wrist",   "L"): "/bone/hand_l",
    ("Wrist",   "R"): "/bone/hand_r",
    # Legs
    ("Thigh","L"): "/bone/thigh_l",
    ("Thigh","R"): "/bone/thigh_r",
    ("Calf", "L"): "/bone/calf_l",
    ("Calf", "R"): "/bone/calf_r",
    ("Foot", "L"): "/bone/foot_l",
    ("Foot", "R"): "/bone/foot_r",
    ("Ball", "L"): "/bone/ball_l",
    ("Ball", "R"): "/bone/ball_r",
}

# CSV stems (arms)
CSV_STEM = {
    ("Shoulder","L"): "LeftShoulder",
    ("Shoulder","R"): "RightShoulder",
    ("Elbow",   "L"): "LeftElbow",
    ("Elbow",   "R"): "RightElbow",
    ("Wrist",   "L"): "LeftWrist",
    ("Wrist",   "R"): "RightWrist",
}

# DOF→Unreal axis (arms & fingers)
MAP_AXES = {
    "Shoulder": {"flexion":"yaw", "abduction":"pitch", "external_rotation":"roll"},
    "Elbow":    {"flexion":"pitch", "pronation":"roll"},
    "Wrist":    {"flexion":"pitch", "adduction":"yaw", "pronation":"roll"},
    "Finger":   {"flexion":"pitch", "ulnarDeviation":"yaw", "pronation":"roll"},
}

# DOF→Unreal axis (legs)
MAP_AXES_LEG = {
    "Thigh": {"flexion":"yaw", "abduction":"pitch", "external_rotation":"roll"},
    "Calf":  {"flexion":"pitch", "pronation":"roll"},
    "Foot":  {"flexion":"pitch", "adduction":"yaw", "pronation":"roll"},
    "Ball":  {"flexion":"pitch", "adduction":"yaw", "pronation":"roll"},
}

# Signs (adjust to your rig)
SIGNS = {
    ("Shoulder","L"): {"pitch": +1, "yaw": +1, "roll": +1},
    ("Shoulder","R"): {"pitch": +1, "yaw": +1, "roll": +1},
    ("Elbow",   "L"): {"pitch": +1, "yaw": +1, "roll": +1},
    ("Elbow",   "R"): {"pitch": +1, "yaw": +1, "roll": +1},
    ("Wrist",   "L"): {"pitch": +1, "yaw": +1, "roll": +1},
    ("Wrist",   "R"): {"pitch": +1, "yaw": +1, "roll": +1},
    ("Finger","L"):  {"pitch": -1, "yaw": +1, "roll": -1},
    ("Finger","R"):  {"pitch": -1, "yaw": +1, "roll": -1},
    ("Thigh","L"):   {"pitch": -1, "yaw": -1, "roll": +1},
    ("Thigh","R"):   {"pitch": -1, "yaw": -1, "roll": +1},
    ("Calf", "L"):   {"pitch": +1, "yaw": +1, "roll": +1},
    ("Calf", "R"):   {"pitch": +1, "yaw": +1, "roll": +1},
    ("Foot", "L"):   {"pitch": +1, "yaw": +1, "roll": +1},
    ("Foot", "R"):   {"pitch": +1, "yaw": +1, "roll": +1},
    ("Ball", "L"):   {"pitch": +1, "yaw": +1, "roll": +1},
    ("Ball", "R"):   {"pitch": +1, "yaw": +1, "roll": +1},
}

# --- Torso CSV → OSC mapping ---
TORSO_MAP = {
    "Pelvis_extension":                ("/bone/pelvis/pitch", +1),
    "Pelvis_lateral_flexion_rotation": ("/bone/pelvis/roll",  +1),
    "Pelvis_axial_rotation":           ("/bone/pelvis/yaw",   +1),

    "Thorax_extension":                ("/bone/spine_03/pitch", +1),
    "Thorax_lateral_flexion_rotation": ("/bone/spine_03/roll",  +1),
    "Thorax_axial_rotation":           ("/bone/spine_03/yaw",   +1),

    "Neck_flexion":                    ("/bone/neck_01/pitch", +1),
    "Neck_left-ward_tilt":             ("/bone/neck_01/roll",  +1),
    "Neck_right-ward_rotation":        ("/bone/neck_01/yaw",   +1),
}

# ----------------- FINGER BONE ADDRESS MAP (UE MetaHuman) -----------------
FINGER_BONES = {
    1: ("thumb_01", "thumb_02", "thumb_03"),
    2: ("index_01", "index_02", "index_03"),
    3: ("middle_01","middle_02","middle_03"),
    4: ("ring_01",  "ring_02",  "ring_03"),
    5: ("pinky_01", "pinky_02", "pinky_03"),
}
def bone_addr(bone_base: str, side: str, axis: str) -> str:
    return f"/bone/{bone_base}_{side.lower()}/{axis}"

# CSV joint → UE “_01/_02/_03” selection rules
DIGIT_JOINT_TO_SLOT = {
    1: {  # thumb: CMC→01, MCP→02, IP→03
        "Carpometacarpal": 0,
        "Metacarpophalangeal": 1,
        "Interphalangeal": 2,
    },
    "default": {  # digits 2..5: MCP→01, PIP→02, DIP→03
        "Metacarpophalangeal": 0,
        "ProximalInterphalangeal": 1,
        "DistalInterphalangeal": 2,
    }
}

# ---- Finger header aliasing & debug -----------------------------------------
THUMB_JOINT_ALIASES = {
    "Carpometacarpal": ["Carpometacarpal", "CMC"],
    "Metacarpophalangeal": ["Metacarpophalangeal", "MCP"],
    "Interphalangeal": ["Interphalangeal", "IP"],
}

def _finger_candidates(side_word: str, digit: int, joint: str, dof: str):
    cands = [f"{side_word}Digit{digit}{joint}_{dof}"]
    if digit == 1:
        for jalt in THUMB_JOINT_ALIASES.get(joint, [joint]):
            cands += [
                f"{side_word}Thumb{jalt}_{dof}",
                f"{side_word}Thumb_{jalt}_{dof}",
                f"{side_word}Digit1{jalt}_{dof}",
                f"{side_word}Digit1_{jalt}_{dof}",
            ]
    return cands

def _find_first_present(df_cols, candidates):
    s = set(df_cols)
    for name in candidates:
        if name in s:
            return name
    return None

# ---- Safe sleep helper ------------------------------------------------------
def safe_sleep(seconds: float):
    """Sleep only if positive; ignore slight negative values from timing drift."""
    if seconds is not None and seconds > 0:
        time.sleep(seconds)

# Baseline pose (add offsets if needed)
BASELINE_POSE = {addr: 0.0 for _, (addr, _) in TORSO_MAP.items()}
SEND_ALL_BASELINE = True

# -------- Helpers ------------------------------------------------------------
def enabled_arm_items(with_elbows: bool, with_wrists: bool):
    items = []
    if ENABLE_SHOULDERS: items.extend([("Shoulder","L"),("Shoulder","R")])
    if ENABLE_ELBOWS or with_elbows: items.extend([("Elbow","L"),("Elbow","R")])
    if ENABLE_WRISTS or with_wrists: items.extend([("Wrist","L"),("Wrist","R")])
    return items

def estimate_rate_from_timestamps(df: pd.DataFrame, default: float = 15.0) -> float:
    if "Timestamp" not in df.columns: return default
    ts = pd.to_numeric(df["Timestamp"], errors="coerce").dropna().values
    if len(ts) < 3: return default
    dts = np.diff(ts) / 1000.0
    dts = dts[dts > 0]
    if len(dts) == 0: return default
    med = float(np.median(dts))
    return (1.0 / med) if med > 0 else default

# -------- Builders -----------------------------------------------------------
def build_torso_table(df: pd.DataFrame) -> List[Tuple[str,str,int]]:
    table = []
    for col, (addr, sgn) in TORSO_MAP.items():
        if col not in df.columns:
            print(f"[torso-zero] Missing CSV col {col} → will send 0.0", file=sys.stderr)
        table.append((col, addr, sgn))
    return table

def build_arms_table(df: pd.DataFrame,
                     items: Iterable[Tuple[str, Optional[str]]],
                     axes_enabled: Dict[str, Dict[str,bool]]) -> List[Tuple[str,str,int]]:
    table: List[Tuple[str,str,int]] = []
    for joint, side in items:
        if joint not in axes_enabled: continue
        addr_stem = ADDR.get((joint, side))
        if not addr_stem: continue
        for dof, axis in MAP_AXES[joint].items():
            if not axes_enabled[joint].get(axis, False): continue
            col = f"{CSV_STEM[(joint, side)]}_{dof}"
            if col not in df.columns:
                print(f"[arm-zero] Missing CSV col {col} → will send 0.0", file=sys.stderr)
            sgn = SIGNS[(joint, side)][axis]
            addr = f"{addr_stem}/{axis}"
            table.append((col, addr, sgn))
    return table

# Leg CSV alias candidates (handle Hip/Thigh, Knee/Calf, Ankle/Foot, Ball/Toes)
def _leg_candidates(side_word: str, logical_joint: str, dof: str):
    joint_aliases = {
        "Thigh": [ "Thigh", "Hip" ],
        "Calf":  [ "Calf", "Knee" ],
        "Foot":  [ "Foot", "Ankle" ],
        "Ball":  [ "Ball", "Toes", "Toe" ],
    }
    cands = []
    for j in joint_aliases.get(logical_joint, [logical_joint]):
        cands.append(f"{side_word}{j}_{dof}")
    return cands

def build_legs_table(df: pd.DataFrame,
                     axes_enabled: Dict[str, Dict[str,bool]],
                     include_ball: bool=True) -> List[Tuple[str,str,int]]:
    table: List[Tuple[str,str,int]] = []
    for side_word, side_tag in (("Left","L"), ("Right","R")):
        for logical_joint in ("Thigh","Calf","Foot","Ball"):
            if logical_joint == "Ball" and not include_ball:
                continue
            if logical_joint not in axes_enabled:
                continue
            addr_stem = ADDR[(logical_joint, side_tag)]
            map_axes = MAP_AXES_LEG[logical_joint]
            for dof, axis in map_axes.items():
                if not axes_enabled[logical_joint].get(axis, False):
                    continue
                candidates = _leg_candidates(side_word, logical_joint, dof)
                col = _find_first_present(df.columns, candidates) or candidates[0]
                if col not in df.columns:
                    print(f"[leg-zero] Missing CSV col {col} (candidates={candidates}) → will send 0.0", file=sys.stderr)
                sgn  = SIGNS[(logical_joint, side_tag)][axis]
                addr = f"{addr_stem}/{axis}"
                table.append((col, addr, sgn))
    return table

def build_finger_table(df: pd.DataFrame,
                       include_cmc_as_01: bool = False,
                       finger_debug: bool = False) -> List[Tuple[str,str,int]]:
    table: List[Tuple[str,str,int]] = []
    df_cols = list(df.columns)

    for side_word in ("Left","Right"):
        side_tag = "L" if side_word == "Left" else "R"
        for digit in (1,2,3,4,5):
            bones = FINGER_BONES[digit]
            if digit == 1:
                joint_iter = ("Carpometacarpal", "Metacarpophalangeal", "Interphalangeal")
                slot_map   = DIGIT_JOINT_TO_SLOT[1]
            else:
                joint_iter = ("Carpometacarpal","Metacarpophalangeal","ProximalInterphalangeal","DistalInterphalangeal")
                slot_map   = DIGIT_JOINT_TO_SLOT["default"]

            for joint_name in joint_iter:
                if digit != 1 and joint_name == "Carpometacarpal" and not include_cmc_as_01:
                    continue

                slot = slot_map.get(joint_name, 0 if include_cmc_as_01 else None)
                if slot is None or slot > 2:
                    continue

                bone_base = bones[slot]
                for dof, axis in MAP_AXES["Finger"].items():
                    candidates = _finger_candidates(side_word, digit, joint_name, dof)
                    col = _find_first_present(df_cols, candidates) or candidates[0]
                    if col not in df_cols and finger_debug:
                        print(f"[finger-zero] Missing {col} (candidates={candidates}) → will send 0.0")
                    addr = bone_addr(bone_base, side_tag, axis)
                    sgn  = SIGNS[("Finger", side_tag)][axis]
                    table.append((col, addr, sgn))
                    if finger_debug and col in df_cols:
                        print(f"[finger-map] {col:50s} -> {addr}")
    return table

def ease_values(client: SimpleUDPClient, targets: Dict[str, float], seconds: float, hz: float):
    if seconds <= 0:
        for a,v in targets.items(): client.send_message(a, float(v))
        return
    n = max(1, int(seconds * hz))
    t = np.linspace(0, 1, n)
    w = 0.5 - 0.5*np.cos(np.pi*t)
    dt = 1.0 / hz
    t0 = time.perf_counter()
    for i, alpha in enumerate(w, start=1):
        for a, v in targets.items():
            client.send_message(a, float(alpha * v))
        target = t0 + i*dt
        remaining = target - time.perf_counter()
        if remaining > 0:
            safe_sleep(remaining)

# -------- Streaming core (interruptible) -------------------------------------
def compile_table(df: pd.DataFrame,
                  include_cmc_as_01: bool,
                  finger_debug: bool,
                  axes=ENABLE_AXES) -> List[Tuple[str,str,int]]:
    table: List[Tuple[str,str,int]] = []
    if ENABLE_TORSO:
        table += build_torso_table(df)
    if ENABLE_SHOULDERS or ENABLE_ELBOWS or ENABLE_WRISTS:
        arm_items = []
        if ENABLE_SHOULDERS: arm_items += [("Shoulder","L"),("Shoulder","R")]
        if ENABLE_ELBOWS:    arm_items += [("Elbow","L"),("Elbow","R")]
        if ENABLE_WRISTS:    arm_items += [("Wrist","L"),("Wrist","R")]
        table += build_arms_table(df, arm_items, axes)
    if ENABLE_FINGERS:
        table += build_finger_table(df, include_cmc_as_01=include_cmc_as_01, finger_debug=finger_debug)
    if ENABLE_LEGS:
        table += build_legs_table(df, axes)
    if not table:
        raise RuntimeError("No channels selected.")
    return table

def stream_csv(csv_path: str,
               ip: str,
               port: int,
               rate: float,
               time_scale: float,
               start_delay: float,
               limit: int,
               include_cmc: bool,
               finger_debug: bool,
               stop_event: threading.Event):
    if not os.path.isfile(csv_path):
        print(f"[error] CSV not found: {csv_path}", file=sys.stderr); return
    df = pd.read_csv(csv_path)

    print(f"[csv] {os.path.basename(csv_path)} | cols={len(df.columns)} | "
          f"LeftDigit1? {any(c.startswith('LeftDigit1') for c in df.columns)} | "
          f"Thumb? {any('Thumb' in c for c in df.columns)}")

    table = compile_table(df, include_cmc_as_01=bool(include_cmc), finger_debug=bool(finger_debug))
    print(f"\n=== Streaming: {csv_path} ===")
    for col, addr, s in table:
        off = BASELINE_POSE.get(addr, 0.0)
        tag = "" if col in df.columns else "[zero]"
        print(f"{col:45s} -> {addr:28s} * {s:+d} {'+ ' + str(off) if off else ''} {tag}")

    # Pace
    hz = rate if rate > 0 else estimate_rate_from_timestamps(df, default=15.0)
    dt = (1.0 / hz) * max(1.0, float(time_scale))
    n_total = len(df) if (limit is None or limit <= 0) else min(limit, len(df))

    client = SimpleUDPClient(ip, port)

    if start_delay > 0:
        t_until = time.perf_counter() + start_delay
        while not stop_event.is_set() and time.perf_counter() < t_until:
            safe_sleep(0.01)

    if SEND_ALL_BASELINE and BASELINE_POSE and not stop_event.is_set():
        ease_values(client, BASELINE_POSE, seconds=1.0, hz=hz)

    # Stream frames
    t0 = time.perf_counter()
    df_cols = set(df.columns)
    for i in range(n_total):
        if stop_event.is_set():
            print("[info] Stream interrupted.")
            return
        row = df.iloc[i]
        for col, addr, s in table:
            if col in df_cols:
                try:
                    v = float(row[col]) * s
                except Exception:
                    v = 0.0
            else:
                v = 0.0
            v += BASELINE_POSE.get(addr, 0.0)
            client.send_message(addr, v)

        target = t0 + (i+1)*dt
        remaining_outer = target - time.perf_counter()
        if remaining_outer > 0:
            end = time.perf_counter() + remaining_outer
            while not stop_event.is_set():
                remaining = end - time.perf_counter()
                if remaining <= 0:
                    break
                safe_sleep(min(0.005, remaining))
    print("[info] Stream finished.")

# -------- Input thread -------------------------------------------------------
def input_worker(cmd_q: "queue.Queue[str]"):
    prompt = "\nType command (Baseline | LeftTurn | RightTurn | quit): "
    try:
        while True:
            s = input(prompt).strip().lower()
            cmd_q.put(s)
            if s == "quit":
                return
    except EOFError:
        cmd_q.put("quit")

# -------- Main ---------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="CSV→Unreal OSC streamer (interruptible).")
    ap.add_argument("--csv", default=CSV_DEFAULT, help="One-off non-interactive stream if --once is used.")
    ap.add_argument("--ip", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=9000)
    ap.add_argument("--rate", type=float, default=30.0)
    ap.add_argument("--time-scale", type=float, default=1.0)
    ap.add_argument("--start-delay", type=float, default=0.8)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--include-cmc", action="store_true",
                    help="Map Digit2..5 Carpometacarpal_* to the _01 bone (co-drive MCP).")
    ap.add_argument("--finger-debug", action="store_true",
                    help="Print detailed mapping/skip info for finger columns.")
    ap.add_argument("--once", action="store_true",
                    help="Run a single CSV specified by --csv and exit (no interactive loop).")
    args = ap.parse_args()

    # Non-interactive single-run mode
    if args.once:
        stop_event = threading.Event()
        stream_csv(args.csv, args.ip, args.port, args.rate, args.time_scale,
                   args.start_delay, args.limit, args.include_cmc, args.finger_debug, stop_event)
        return

    # Interactive mode with interrupt
    cmd_q: "queue.Queue[str]" = queue.Queue()
    threading.Thread(target=input_worker, args=(cmd_q,), daemon=True).start()

    current_thread: Optional[threading.Thread] = None
    stop_event = threading.Event()

    print("\nInteractive mode is ready.")
    print("You can interrupt a running stream by typing a new command.\n")

    while True:
        try:
            try:
                cmd = cmd_q.get(timeout=0.05)
            except queue.Empty:
                continue

            if cmd == "quit":
                if current_thread and current_thread.is_alive():
                    stop_event.set()
                    current_thread.join(timeout=2.0)
                print("Bye.")
                return

            if cmd not in ("baseline", "leftturn", "rightturn"):
                print(f"[warn] Unknown command: {cmd}. Valid: Baseline | LeftTurn | RightTurn | quit")
                continue

            csv_path = INTERACTIVE_PATHS[cmd]

            if current_thread and current_thread.is_alive():
                print("[info] Stopping current stream...")
                stop_event.set()
                current_thread.join(timeout=2.0)

            stop_event = threading.Event()
            current_thread = threading.Thread(
                target=stream_csv,
                args=(csv_path, args.ip, args.port, args.rate, args.time_scale,
                      args.start_delay, args.limit, args.include_cmc, args.finger_debug, stop_event),
                daemon=True
            )
            current_thread.start()

        except KeyboardInterrupt:
            print("\n[ctrl-c] Exiting...")
            if current_thread and current_thread.is_alive():
                stop_event.set()
                current_thread.join(timeout=2.0)
            return

if __name__ == "__main__":
    main()