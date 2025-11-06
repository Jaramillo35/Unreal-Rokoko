#!/usr/bin/env python3
"""
JCS→Unreal OSC streamer (single labeled CSV with 'source' & 'iteration').

Interactive prompts (type at any time):
  - Single loop:  baseline    | leftturn    | rightturn
  - Sequence   :  baseline,leftturn,rightturn
  - zero       :  instantly zero all mapped addresses
  - quit       :  exit

Combo behavior:
- baseline plays for 5 seconds, then leftturn plays ALL iterations once each
  in random order, then rightturn does the same.

Single behavior:
- Single token loops until a new prompt is typed.
- For leftturn/rightturn, an iteration (1..10) is picked randomly each time you
  start that token.

General:
- Sends EVERY mapped Unreal address each frame (missing CSV columns → send 0.0).
- Includes torso, arms, hands, fingers (thumb 01/02/03), pelvis, and legs.
"""

import argparse, os, sys, time, threading, queue, random
from typing import List, Tuple, Iterable, Dict, Optional
import numpy as np
import pandas as pd
from pythonosc.udp_client import SimpleUDPClient

# ==================== USER PATH (change if needed) ===========================
CSV_DEFAULT = "/Users/martinjaramillo/Documents/Unreal+Rokoko/data/combined_data_labeled.csv"
# ============================================================================

# ==================== STAGE TOGGLES =========================================
ENABLE_TORSO     = True
ENABLE_SHOULDERS = True
ENABLE_ELBOWS    = True
ENABLE_WRISTS    = True
ENABLE_FINGERS   = True
ENABLE_LEGS      = True
# ============================================================================

# Axes enabled per group
ENABLE_AXES: Dict[str, Dict[str, bool]] = {
    "Torso":    {"pitch": True, "yaw": True, "roll": True},
    "Shoulder": {"pitch": True, "yaw": True, "roll": True},
    "Elbow":    {"pitch": True, "yaw": False, "roll": True},   # yaw unused
    "Wrist":    {"pitch": True, "yaw": True, "roll": True},
    "Finger":   {"pitch": True, "yaw": True, "roll": True},
    # Legs
    "Thigh":    {"pitch": True, "yaw": True, "roll": True},
    "Calf":     {"pitch": True, "yaw": False, "roll": False},  # Pitch only
    "Foot":     {"pitch": True, "yaw": True, "roll": True},
    "Ball":     {"pitch": True, "yaw": False, "roll": False},  # Pitch only
}

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
    "Thigh": {"flexion":"roll", "abduction":"pitch", "external_rotation":"yaw"},
    "Calf":  {"flexion":"pitch", "pronation":"roll"},
    "Foot":  {"flexion":"pitch", "adduction":"yaw", "pronation":"roll"},
    "Ball":  {"flexion":"pitch", "adduction":"yaw", "pronation":"roll"},
}

# Signs (tune to rig)
SIGNS = {
    ("Shoulder","L"): {"pitch": +1, "yaw": +1, "roll": +1},
    ("Shoulder","R"): {"pitch": +1, "yaw": +1, "roll": +1},
    ("Elbow",   "L"): {"pitch": +1, "yaw": +1, "roll": +1},
    ("Elbow",   "R"): {"pitch": +1, "yaw": +1, "roll": +1},
    ("Wrist",   "L"): {"pitch": +1, "yaw": +1, "roll": +1},
    ("Wrist",   "R"): {"pitch": +1, "yaw": +1, "roll": +1},
    ("Finger","L"):  {"pitch": -1, "yaw": +1, "roll": -1},
    ("Finger","R"):  {"pitch": -1, "yaw": +1, "roll": -1},
    ("Thigh","L"):   {"pitch": +1, "yaw": -1, "roll": +1},
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

# ---- Finger header aliasing -------------------------------------------------
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

# ---- Utility ----------------------------------------------------------------
def safe_sleep(seconds: float):
    if seconds is not None and seconds > 0:
        time.sleep(seconds)

def estimate_rate_from_timestamps(df: pd.DataFrame, default: float = 15.0) -> float:
    if "Timestamp" not in df.columns: return default
    ts = pd.to_numeric(df["Timestamp"], errors="coerce").dropna().values
    if len(ts) < 3: return default
    dts = np.diff(ts) / 1000.0
    dts = dts[dts > 0]
    if len(dts) == 0: return default
    med = float(np.median(dts))
    return (1.0 / med) if med > 0 else default

# Baseline offsets (0.0 by default)
BASELINE_POSE = {addr: 0.0 for _, (addr, _) in TORSO_MAP.items()}
SEND_ALL_BASELINE = True

# -------- Builders (tables of csv_col → addr * sign) -------------------------
def build_torso_table(df: pd.DataFrame) -> List[Tuple[str,str,int]]:
    table = []
    for col, (addr, sgn) in TORSO_MAP.items():
        if col not in df.columns:
            print(f"[torso-zero] Missing {col} → 0.0", file=sys.stderr)
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
                print(f"[arm-zero] Missing {col} → 0.0", file=sys.stderr)
            sgn = SIGNS[(joint, side)][axis]
            addr = f"{addr_stem}/{axis}"
            table.append((col, addr, sgn))
    return table

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
                    print(f"[leg-zero] Missing {col} (cands={candidates}) → 0.0", file=sys.stderr)
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
                        print(f"[finger-zero] Missing {col} (cands={candidates}) → 0.0")
                    addr = bone_addr(bone_base, side_tag, axis)
                    sgn  = SIGNS[("Finger", side_tag)][axis]
                    table.append((col, addr, sgn))
    return table

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

# -------- Streaming ----------------------------------------------------------
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

def send_zero_for_duration(client: SimpleUDPClient,
                           table: List[Tuple[str,str,int]],
                           hz: float,
                           seconds: float = 0.5):
    """Send 0.0 to every mapped address for 'seconds'."""
    if seconds <= 0 or hz <= 0:
        for _, addr, _ in table:
            client.send_message(addr, 0.0)
        return
    frames = max(1, int(seconds * hz))
    dt = 1.0 / hz
    for _ in range(frames):
        for _, addr, _ in table:
            client.send_message(addr, 0.0)
        safe_sleep(dt)

def stream_rows(client: SimpleUDPClient,
                table: List[Tuple[str,str,int]],
                df_slice: pd.DataFrame,
                hz: float,
                time_scale: float,
                stop_event: threading.Event,
                loop_forever: bool):
    dt = (1.0 / hz) * max(1.0, float(time_scale))
    df_cols = set(df_slice.columns)
    while not stop_event.is_set():
        t0 = time.perf_counter()
        n_total = len(df_slice)
        for i in range(n_total):
            if stop_event.is_set(): return
            row = df_slice.iloc[i]
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
                    rem = end - time.perf_counter()
                    if rem <= 0: break
                    safe_sleep(min(0.003, rem))
        if not loop_forever:
            return

def stream_for_seconds(client: SimpleUDPClient,
                       table: List[Tuple[str,str,int]],
                       df_slice: pd.DataFrame,
                       seconds: float,
                       hz: float,
                       time_scale: float,
                       stop_event: threading.Event):
    """Loop df_slice frames repeatedly to fill 'seconds' total duration."""
    if seconds <= 0: return
    dt = (1.0 / hz) * max(1.0, float(time_scale))
    df_cols = set(df_slice.columns)
    t_end = time.perf_counter() + seconds
    while not stop_event.is_set() and time.perf_counter() < t_end:
        t0 = time.perf_counter()
        n_total = len(df_slice)
        for i in range(n_total):
            if stop_event.is_set() or time.perf_counter() >= t_end:
                return
            row = df_slice.iloc[i]
            for col, addr, s in table:
                if col in df_cols:
                    try: v = float(row[col]) * s
                    except Exception: v = 0.0
                else:
                    v = 0.0
                v += BASELINE_POSE.get(addr, 0.0)
                client.send_message(addr, v)
            target = t0 + (i+1)*dt
            remaining_outer = target - time.perf_counter()
            if remaining_outer > 0:
                end = time.perf_counter() + remaining_outer
                while not stop_event.is_set() and time.perf_counter() < end:
                    safe_sleep(min(0.003, end - time.perf_counter()))

# -------- Selection helpers for labeled CSV ---------------------------------
VALID_TOKENS = {"baseline", "leftturn", "rightturn"}
SPECIAL_CMDS = {"zero", "quit"}

def pick_iteration_for(token: str) -> Optional[int]:
    if token in ("leftturn", "rightturn"):
        return random.randint(1, 10)
    return None  # baseline ignores iteration

def filter_segment(df_all: pd.DataFrame, token: str, iteration: Optional[int]) -> pd.DataFrame:
    if "source" not in df_all.columns:
        raise RuntimeError("CSV is missing required 'source' column.")
    src = token.lower()
    df = df_all[df_all["source"].astype(str).str.lower() == src]
    if src in ("leftturn", "rightturn"):
        if "iteration" not in df_all.columns:
            raise RuntimeError("CSV is missing required 'iteration' column for turns.")
        if iteration is not None:
            df_iter = df[pd.to_numeric(df["iteration"], errors="coerce") == iteration]
            if len(df_iter) > 0:
                return df_iter
    return df

def all_iterations(df_all: pd.DataFrame, token: str) -> List[int]:
    """Return sorted list of unique iterations available for a token."""
    src = token.lower()
    sub = df_all[df_all["source"].astype(str).str.lower() == src]
    if "iteration" not in sub.columns:
        return []
    vals = pd.to_numeric(sub["iteration"], errors="coerce").dropna().astype(int).unique().tolist()
    vals.sort()
    return vals

# -------- Input thread -------------------------------------------------------
def input_worker(cmd_q: "queue.Queue[str]"):
    prompt = ("\nCommand (baseline | leftturn | rightturn | "
              " zero | quit)> ")
    try:
        while True:
            s = input(prompt)
            if s is None:
                s = ""
            cmd_q.put(s.strip().lower())
            if s.strip().lower() == "quit":
                return
    except EOFError:
        cmd_q.put("quit")

# -------- Main ---------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="CSV→Unreal OSC (labeled single CSV, interruptible).")
    ap.add_argument("--csv", default=CSV_DEFAULT, help="Combined CSV with 'source' and 'iteration' columns.")
    ap.add_argument("--ip", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=9000)
    ap.add_argument("--rate", type=float, default=30.0)
    ap.add_argument("--time-scale", type=float, default=1.0)
    ap.add_argument("--start-delay", type=float, default=0.6)
    ap.add_argument("--include-cmc", action="store_true",
                    help="Map Digit2..5 Carpometacarpal_* to the _01 bone (co-drive MCP).")
    ap.add_argument("--finger-debug", action="store_true",
                    help="Print detailed mapping/skip info for finger columns.")
    args = ap.parse_args()

    if not os.path.isfile(args.csv):
        print(f"[error] CSV not found: {args.csv}", file=sys.stderr); sys.exit(1)
    df_all = pd.read_csv(args.csv)

    table = compile_table(df_all, include_cmc_as_01=bool(args.include_cmc), finger_debug=bool(args.finger_debug))
    print("=== Channels (csv_col -> addr * sign) ===")
    for col, addr, s in table:
        tag = "" if col in df_all.columns else "[zero]"
        print(f"{col:45s} -> {addr:28s} * {s:+d} {tag}")

    hz = args.rate if args.rate > 0 else estimate_rate_from_timestamps(df_all, default=15.0)

    client = SimpleUDPClient(args.ip, args.port)
    if args.start_delay > 0:
        safe_sleep(args.start_delay)
    if SEND_ALL_BASELINE and BASELINE_POSE:
        ease_values(client, BASELINE_POSE, seconds=0.4, hz=hz)

    cmd_q: "queue.Queue[str]" = queue.Queue()
    threading.Thread(target=input_worker, args=(cmd_q,), daemon=True).start()

    current_thread: Optional[threading.Thread] = None
    current_stop: Optional[threading.Event] = None

    print("\nInteractive mode ready. Type a command (or 'zero' / 'quit').")

    while True:
        try:
            try:
                raw = cmd_q.get(timeout=0.05)
            except queue.Empty:
                continue

            # Handle special commands immediately
            if raw == "quit":
                if current_thread and current_thread.is_alive():
                    current_stop.set()
                    current_thread.join(timeout=2.0)
                print("Bye.")
                return

            if raw == "zero":
                # Interrupt current job
                if current_thread and current_thread.is_alive():
                    current_stop.set()
                    current_thread.join(timeout=2.0)
                # Send zeros to ALL mapped addresses
                send_zero_for_duration(client, table, hz, seconds=0.5)
                continue

            # Parse tokens for normal actions
            tokens = [t.strip().lower() for t in raw.split(",") if t.strip()]
            if not tokens or any((t not in VALID_TOKENS) for t in tokens):
                print(f"[warn] Invalid input '{raw}'. Use baseline|leftturn|rightturn, sequences, or 'zero'.")
                continue

            # Interrupt whatever is running RIGHT AWAY
            if current_thread and current_thread.is_alive():
                current_stop.set()
                current_thread.join(timeout=2.0)

            # New stop event for the new task
            current_stop = threading.Event()

            # Single token → loop mode
            if len(tokens) == 1:
                token = tokens[0]
                iter_choice = pick_iteration_for(token)
                seg_df = filter_segment(df_all, token, iter_choice)
                if len(seg_df) == 0:
                    print(f"[warn] No rows for '{token}'.")
                    continue

                def runner_loop():
                    ease_values(client, BASELINE_POSE, seconds=0.2, hz=hz)
                    stream_rows(client, table, seg_df, hz, args.time_scale, current_stop, loop_forever=True)

                current_thread = threading.Thread(target=runner_loop, daemon=True)
                current_thread.start()

            # Multi-token → ordered sequence with special combo rules
            else:
                def runner_sequence():
                    for token in tokens:
                        if current_stop.is_set(): return

                        # baseline in combo → exactly 5s
                        if token == "baseline":
                            seg_df = filter_segment(df_all, "baseline", None)
                            if len(seg_df) == 0: continue
                            ease_values(client, BASELINE_POSE, seconds=0.2, hz=hz)
                            stream_for_seconds(client, table, seg_df, seconds=5.0,
                                               hz=hz, time_scale=args.time_scale, stop_event=current_stop)
                            continue

                        # left/right in combo → all iterations once each in random order
                        if token in ("leftturn", "rightturn"):
                            iters = all_iterations(df_all, token)
                            if not iters:
                                # Fallback: if no iteration column/values, just stream whole segment once
                                seg_df = filter_segment(df_all, token, None)
                                if len(seg_df) == 0: continue
                                ease_values(client, BASELINE_POSE, seconds=0.2, hz=hz)
                                stream_rows(client, table, seg_df, hz, args.time_scale, current_stop, loop_forever=False)
                                continue

                            random.shuffle(iters)
                            for it in iters:
                                if current_stop.is_set(): return
                                seg_df = filter_segment(df_all, token, it)
                                if len(seg_df) == 0: continue
                                ease_values(client, BASELINE_POSE, seconds=0.15, hz=hz)
                                stream_rows(client, table, seg_df, hz, args.time_scale, current_stop, loop_forever=False)

                    ease_values(client, BASELINE_POSE, seconds=0.2, hz=hz)

                current_thread = threading.Thread(target=runner_sequence, daemon=True)
                current_thread.start()

        except KeyboardInterrupt:
            # Graceful exit
            if current_thread and current_thread.is_alive():
                current_stop.set()
                current_thread.join(timeout=2.0)
            print("\nExiting.")
            return

if __name__ == "__main__":
    main()