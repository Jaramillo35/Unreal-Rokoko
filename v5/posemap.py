#!/usr/bin/env python3
# test_shoulders_osc.py
# Commands:
#   flex 50        → set both shoulders' flexion = 50°
#   flex 0 90      → sweep flexion 0→90 at --sweep-speed deg/s
#   abd  -60       → set abduction  = -60°
#   er   0  45     → sweep ER 0→45
#   stop           → stop all sweeps (holds current targets)
#   status | zero | quit

import time, sys, select, argparse, json
from pythonosc.udp_client import SimpleUDPClient

# ------------- CLI -------------
ap = argparse.ArgumentParser(description="Interactive shoulder angle sender to Unreal via OSC (set or sweep).")
ap.add_argument("--host", default="127.0.0.1")
ap.add_argument("--port", type=int, default=9000)
ap.add_argument("--fps", type=int, default=60)
ap.add_argument("--ease", type=float, default=0.35, help="Seconds to ease toward target for SET commands")
ap.add_argument("--scale", type=float, default=1.0, help="Global multiplier for all angles (deg)")
ap.add_argument("--sweep-speed", type=float, default=60.0, help="Sweep speed in deg/s (used when 2 values given)")
ap.add_argument("--l_flex_off", type=float, default=0.0)
ap.add_argument("--l_abd_off",  type=float, default=0.0)
ap.add_argument("--l_er_off",   type=float, default=0.0)
ap.add_argument("--r_flex_off", type=float, default=0.0)
ap.add_argument("--r_abd_off",  type=float, default=0.0)
ap.add_argument("--r_er_off",   type=float, default=0.0)
ap.add_argument("--save-last",  default="", help="Optional path to save the last sent angles JSON on exit")
args = ap.parse_args()

# ------------- OSC client -------------
osc = SimpleUDPClient(args.host, args.port)

# ------------- Channels (shoulders only) -------------
CHAN = {
    "l_flex": "/bone/upperarm_l/roll",
    "l_abd":  "/bone/upperarm_l/pitch",
    "l_er":   "/bone/upperarm_l/yaw",
    "r_flex": "/bone/upperarm_r/roll",
    "r_abd":  "/bone/upperarm_r/pitch",
    "r_er":   "/bone/upperarm_r/yaw",
}
AXES = ("flex", "abd", "er")

# Offsets (per side/axis)
OFF = {
    "l_flex": args.l_flex_off, "l_abd": args.l_abd_off, "l_er": args.l_er_off,
    "r_flex": args.r_flex_off, "r_abd": args.r_abd_off, "r_er": args.r_er_off,
}

def apply_off_scale(side_axis_key: str, value_deg: float) -> float:
    return (value_deg + OFF.get(side_axis_key, 0.0)) * args.scale

# ------------- Animation state -------------
current = {k: 0.0 for k in CHAN}      # what we're currently sending (stored last angles)
target  = {k: 0.0 for k in CHAN}      # instantaneous target this frame (post set/sweep)

# Sweep state per axis (affects both sides)
#   None or {"pos":float, "end":float, "dir":+/-1}
sweep = {ax: None for ax in AXES}

def smoothstep01(x):
    x = max(0.0, min(1.0, x))
    return x*x*(3.0 - 2.0*x)

def lerp(a, b, t): return a + (b - a) * t

def set_axis_both(axis_name: str, value_deg: float):
    """Hard-set a target value (cancels any sweep on that axis)."""
    axis_name = axis_name.lower().strip()
    if axis_name not in AXES:
        print(f"Unknown axis '{axis_name}'. Use one of: {', '.join(AXES)}")
        return False
    # Cancel sweep on this axis (SET command semantics)
    sweep[axis_name] = None
    lk = f"l_{axis_name}"; rk = f"r_{axis_name}"
    target[lk] = apply_off_scale(lk, value_deg)
    target[rk] = apply_off_scale(rk, value_deg)
    print(f"→ Set {axis_name} {value_deg:.1f}°  (L:{target[lk]:.1f}, R:{target[rk]:.1f} after off/scale)")
    return True

def start_sweep_axis_both(axis_name: str, v0: float, v1: float):
    """Begin a linear sweep from v0→v1 (deg) at args.sweep_speed deg/s. Updates every frame."""
    axis_name = axis_name.lower().strip()
    if axis_name not in AXES:
        print(f"Unknown axis '{axis_name}'. Use one of: {', '.join(AXES)}")
        return False
    if v0 == v1:
        return set_axis_both(axis_name, v0)
    direction = 1.0 if (v1 - v0) > 0 else -1.0
    sweep[axis_name] = {"pos": float(v0), "end": float(v1), "dir": direction}
    # Initialize targets at v0 WITHOUT canceling the sweep
    lk = f"l_{axis_name}"; rk = f"r_{axis_name}"
    target[lk] = apply_off_scale(lk, v0)
    target[rk] = apply_off_scale(rk, v0)
    print(f"→ Sweep {axis_name}: {v0:.1f}° → {v1:.1f}° at {args.sweep_speed:.1f}°/s")
    return True

def update_sweeps(dt: float):
    """Advance active sweeps by speed*dt and set per-frame targets."""
    speed = abs(args.sweep_speed)
    for ax, st in sweep.items():
        if st is None:
            continue
        step = st["dir"] * speed * dt
        new_pos = st["pos"] + step

        # Reached the end?
        if (st["dir"] > 0 and new_pos >= st["end"]) or (st["dir"] < 0 and new_pos <= st["end"]):
            new_pos = st["end"]
            sweep[ax] = None  # finished

        if st is not None:
            st["pos"] = new_pos  # keep updating while active

        # Apply to both sides (with offsets and global scale)
        lk = f"l_{ax}"; rk = f"r_{ax}"
        target[lk] = apply_off_scale(lk, new_pos)
        target[rk] = apply_off_scale(rk, new_pos)

def send_angles(vals):
    for k, v in vals.items():
        osc.send_message(CHAN[k], float(v))

def nonblocking_line():
    dr, _, _ = select.select([sys.stdin], [], [], 0)
    if dr:
        return sys.stdin.readline().strip()
    return None

def print_status():
    print("\n--- STATUS ---")
    print("Current (sending):")
    for ax in AXES:
        print(f"  {ax.upper():>3}  L:{current[f'l_{ax}']:+8.3f}   R:{current[f'r_{ax}']:+8.3f}")
    print("Target (frame):")
    for ax in AXES:
        print(f"  {ax.upper():>3}  L:{target[f'l_{ax}']:+8.3f}   R:{target[f'r_{ax}']:+8.3f}")
    print("Sweeps:")
    for ax in AXES:
        st = sweep[ax]
        if st:
            print(f"  {ax} pos:{st['pos']:+6.2f} → end:{st['end']:+6.2f} dir:{'+' if st['dir']>0 else '-'}")
    print("-------------\n")

def save_last_if_requested():
    if not args.save_last:
        return
    payload = {"timestamp": time.time(), "angles_deg": {k: float(v) for k, v in current.items()}}
    try:
        with open(args.save_last, "w") as f:
            json.dump(payload, f, indent=2)
        print(f"💾 Saved last angles to {args.save_last}")
    except Exception as e:
        print(f"⚠️ Could not save last angles: {e}")

print("\nShoulder Axis Driver (set or sweep)")
print("Examples:")
print("  flex 30        # set flex = 30° on both arms")
print("  flex 0 90      # sweep flex 0→90 at --sweep-speed deg/s")
print("  abd -60        # set abduction = -60°")
print("  er  45 0       # sweep ER 45→0")
print("  stop           # stop all sweeps")
print("  status | zero | quit\n")
print(f"Sending to {args.host}:{args.port} at {args.fps} FPS. Ease(sets) {args.ease:.2f}s, sweep {args.sweep_speed:.1f}°/s.\n")

# Start at zeros
ease_dur = max(0.0, args.ease)
frame_dt = 1.0 / max(1, args.fps)
t0 = time.time()
t_set_start = t0  # easing timer for SETs only

try:
    while True:
        # Handle text commands
        cmdline = nonblocking_line()
        if cmdline:
            parts = cmdline.strip().split()
            if not parts:
                pass
            else:
                cmd = parts[0].lower()
                if cmd in ("quit", "exit", "q"):
                    break
                elif cmd == "status":
                    print_status()
                elif cmd == "zero":
                    for ax in AXES: set_axis_both(ax, 0.0)
                    t_set_start = time.time()
                elif cmd == "stop":
                    for ax in AXES: sweep[ax] = None
                    print("⏹️  Stopped all sweeps.")
                elif cmd in AXES:
                    if len(parts) == 2:
                        # SET
                        try:
                            v = float(parts[1])
                            if set_axis_both(cmd, v):
                                t_set_start = time.time()  # ease toward new set target
                        except ValueError:
                            print("Please provide a numeric degree value, e.g., 'abd -60'")
                    elif len(parts) >= 3:
                        # SWEEP
                        try:
                            v0 = float(parts[1]); v1 = float(parts[2])
                            start_sweep_axis_both(cmd, v0, v1)  # no cancel, initializes at v0
                        except ValueError:
                            print("Please provide numeric degree values, e.g., 'flex 0 90'")
                    else:
                        print(f"Usage: {cmd} <deg>  OR  {cmd} <deg_start> <deg_end>")
                else:
                    print("Unknown command. Try: flex 30 | flex 0 90 | abd -60 | er 15 | stop | status | zero | quit")

        # Timing
        now = time.time()
        dt = now - t0
        if dt < 0: dt = 0.0

        # Advance active sweeps and set per-frame targets
        update_sweeps(dt)

        # Decide easing: if ANY sweep is active, follow targets directly; else ease for SETs
        any_sweep_active = any(sweep[ax] is not None for ax in AXES)
        if any_sweep_active:
            s = 1.0  # follow sweep target exactly (speed controlled by update_sweeps)
        else:
            # ease toward last SET target
            s = 1.0 if ease_dur == 0 else smoothstep01(
                min((now - t_set_start) / (ease_dur if ease_dur > 0 else 1e-6), 1.0)
            )

        # Interpolate and send
        pose_now = {}
        for k in current.keys():
            pose_now[k] = current[k] = lerp(current[k], target[k], s)
        for k, v in pose_now.items():
            osc.send_message(CHAN[k], float(v))

        # FPS pacing
        sleep_for = frame_dt - (time.time() - t0)
        if sleep_for > 0:
            time.sleep(sleep_for)
        t0 = time.time()
except KeyboardInterrupt:
    pass
finally:
    print_status()
    save_last_if_requested()
    print("Bye!")