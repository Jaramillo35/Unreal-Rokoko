#!/usr/bin/env python3
"""
Left Arm Quaternion Axis Tester for Unreal (with full reset)
------------------------------------------------------------
1. Sends identity quaternions to ALL joints first (resets pose)
2. Then tests LEFT ARM chain one axis at a time (X, Y, Z)
3. After each axis sweep, asks you if the observed motion looks correct

Expected cues (per axis):
- X: flex/extend (forward/back swing)
- Y: twist (axial rotation)
- Z: abduction/adduction (side raise/lower)
"""

import time
import math
import argparse
from typing import Iterable, Tuple
from pythonosc.udp_client import SimpleUDPClient

# ----------- CONFIG -----------
DEFAULT_IP   = "127.0.0.1"
DEFAULT_PORT = 9000
DEFAULT_FPS  = 30.0
ALL_BONES = [
    # Torso
    "pelvis", "spine_01", "spine_02", "spine_03", "neck_01", "head",
    # Right arm
    "clavicle_r", "upperarm_r", "lowerarm_r", "hand_r",
    "thumb_01_r","thumb_02_r","thumb_03_r",
    "index_01_r","index_02_r","index_03_r",
    "middle_01_r","middle_02_r","middle_03_r",
    "ring_01_r","ring_02_r","ring_03_r",
    "pinky_01_r","pinky_02_r","pinky_03_r",
    # Left arm
    "clavicle_l","upperarm_l","lowerarm_l","hand_l",
    "thumb_01_l","thumb_02_l","thumb_03_l",
    "index_01_l","index_02_l","index_03_l",
    "middle_01_l","middle_02_l","middle_03_l",
    "ring_01_l","ring_02_l","ring_03_l",
    "pinky_01_l","pinky_02_l","pinky_03_l",
    # Legs
    "thigh_r","calf_r","foot_r","ball_r",
    "thigh_l","calf_l","foot_l","ball_l"
]
LEFT_ARM_BONES = ("clavicle_l", "upperarm_l", "lowerarm_l", "hand_l")
# ------------------------------


def axis_angle_to_quat_xyz_w(axis: Tuple[float,float,float], degrees: float):
    """axis=(ax,ay,az) unit vector, deg-> (x,y,z,w)"""
    theta = math.radians(degrees)
    s = math.sin(theta / 2.0)
    c = math.cos(theta / 2.0)
    ax, ay, az = axis
    return (ax * s, ay * s, az * s, c)


def addresses_for(bone: str, scheme: str):
    """Return 4 OSC addresses for (x,y,z,w) given a bone & scheme."""
    if scheme == "quat":
        return (f"/bone/{bone}/quat_x",
                f"/bone/{bone}/quat_y",
                f"/bone/{bone}/quat_z",
                f"/bone/{bone}/quat_w")
    # your current wiring: pitch/yaw/roll/w
    return (f"/bone/{bone}/pitch",
            f"/bone/{bone}/yaw",
            f"/bone/{bone}/roll",
            f"/bone/{bone}/w")


def send_identity(client: SimpleUDPClient, bones: Iterable[str], scheme: str):
    """Send identity quaternion (0,0,0,1) once to reset pose."""
    for b in bones:
        ax, ay, az, aw = addresses_for(b, scheme)
        client.send_message(ax, 0.0)
        client.send_message(ay, 0.0)
        client.send_message(az, 0.0)
        client.send_message(aw, 1.0)
    print(f"[reset] Sent identity quaternions for {len(list(bones))} bones.")


def sweep_axis(client: SimpleUDPClient,
               bones: Iterable[str],
               scheme: str,
               axis_label: str,
               axis_vec: Tuple[float,float,float],
               amplitude_deg: float,
               seconds: float,
               fps: float):
    """Sweep +amp -> -amp -> 0 on one axis for all bones in chain."""
    frames = max(1, int(seconds * fps))
    key_degs = [0.0, amplitude_deg, -amplitude_deg, 0.0]
    seg_len = max(1, frames // (len(key_degs) - 1))
    print(f"\n=== Testing {axis_label}-axis | amp={amplitude_deg}° | {frames} frames ===")
    print_cues(axis_label)

    t0 = time.perf_counter()
    for sidx in range(len(key_degs)-1):
        a0, a1 = key_degs[sidx], key_degs[sidx+1]
        for i in range(seg_len):
            t = i / float(seg_len - 1) if seg_len > 1 else 1.0
            deg = (1.0 - t) * a0 + t * a1
            qx, qy, qz, qw = axis_angle_to_quat_xyz_w(axis_vec, deg)

            for b in bones:
                ax, ay, az, aw = addresses_for(b, scheme)
                client.send_message(ax, qx)
                client.send_message(ay, qy)
                client.send_message(az, qz)
                client.send_message(aw, qw)

            print(f"{axis_label} | θ={deg:7.3f}° | "
                  f"qx={qx:+.6f} qy={qy:+.6f} qz={qz:+.6f} qw={qw:+.6f}", end="\r")

            target = t0 + (1.0 / fps)
            t0 = target
            sleep = target - time.perf_counter()
            if sleep > 0:
                time.sleep(sleep)
    print()


def print_cues(axis_label: str):
    cues = {
        "X": "- EXPECTED: flex/extend (arm swings forward/back)",
        "Y": "- EXPECTED: twist (axial rotation, pronation/supination)",
        "Z": "- EXPECTED: abduction/adduction (raise/lower sideways)"
    }
    print(cues.get(axis_label, ""))


def ask_ok(axis_label: str) -> str:
    print(f"\nDid the LEFT ARM motion for {axis_label} look correct?")
    print("Type: ok | invert | unsure | quit")
    return input("> ").strip().lower()


def main():
    ap = argparse.ArgumentParser(description="Left-arm quaternion axis tester (resets all bones first)")
    ap.add_argument("--ip", default=DEFAULT_IP)
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--scheme", choices=["pyr","quat"], default="pyr")
    ap.add_argument("--fps", type=float, default=DEFAULT_FPS)
    ap.add_argument("--seconds-per-axis", type=float, default=2.5)
    ap.add_argument("--amplitude-deg", type=float, default=30.0)
    args = ap.parse_args()

    client = SimpleUDPClient(args.ip, args.port)

    try:
        # Zero all joints first
        print("Resetting ALL bones to identity quaternion (0,0,0,1)...")
        send_identity(client, ALL_BONES, args.scheme)
        time.sleep(1.5)
        print("✅ All bones reset. Starting left arm test...\n")

        # Test X-axis
        sweep_axis(client, LEFT_ARM_BONES, args.scheme, "X", (1,0,0),
                   args.amplitude_deg, args.seconds_per_axis, args.fps)
        ans = ask_ok("X (flex/extend)")
        if ans == "quit": return
        if ans == "invert":
            print("⚙️  Note: Flip sign of qx if direction is reversed.\n")

        # Test Y-axis
        send_identity(client, LEFT_ARM_BONES, args.scheme)
        time.sleep(0.5)
        sweep_axis(client, LEFT_ARM_BONES, args.scheme, "Y", (0,1,0),
                   args.amplitude_deg, args.seconds_per_axis, args.fps)
        ans = ask_ok("Y (twist)")
        if ans == "quit": return
        if ans == "invert":
            print("⚙️  Note: Flip sign of qy if direction is reversed.\n")

        # Test Z-axis
        send_identity(client, LEFT_ARM_BONES, args.scheme)
        time.sleep(0.5)
        sweep_axis(client, LEFT_ARM_BONES, args.scheme, "Z", (0,0,1),
                   args.amplitude_deg, args.seconds_per_axis, args.fps)
        ans = ask_ok("Z (ab/adduction)")
        if ans == "quit": return
        if ans == "invert":
            print("⚙️  Note: Flip sign of qz if direction is reversed.\n")

        # Final reset
        print("\nResetting all bones again to neutral pose...")
        send_identity(client, ALL_BONES, args.scheme)
        print("✅ Test finished. Use your feedback to fix axis mapping or signs in Control Rig.")

    except KeyboardInterrupt:
        send_identity(client, ALL_BONES, args.scheme)
        print("\n⏹️  Interrupted. All bones reset to identity.")


if __name__ == "__main__":
    main()