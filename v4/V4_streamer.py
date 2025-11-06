#!/usr/bin/env python3
# Simplest possible live OSC streamer using our GRU_nextframe.onnx
# Usage:
#   python stream_turn.py left
#   python stream_turn.py right
#
# Requirements: pip install onnxruntime python-osc numpy

import argparse, time, os, sys
import numpy as np
import onnxruntime as ort
from pythonosc.udp_client import SimpleUDPClient

# --- Edit paths/ports if needed ---
DATA_DIR = os.path.expanduser("~/Documents/Unreal+Rokoko/data/processed_v4")
ONNX_PATH = os.path.join(DATA_DIR, "GRU_nextframe.onnx")           # use this (batch=1, T fixed = 30)
FEATURES_CSV = os.path.join(DATA_DIR, "angle_feature_names.csv")
MEAN_PATH = os.path.join(DATA_DIR, "angle_mean.npy")
STD_PATH  = os.path.join(DATA_DIR, "angle_std.npy")

OSC_HOST = "127.0.0.1"
OSC_PORT = 7000
HZ = 60.0                     # target streaming rate
T = 30                        # window length used during training
# ----------------------------------

def load_assets():
    names = [s.strip() for s in open(FEATURES_CSV, "r").read().splitlines()]
    mean = np.load(MEAN_PATH).astype(np.float32)   # [F]
    std  = np.load(STD_PATH ).astype(np.float32)   # [F]
    sess = ort.InferenceSession(ONNX_PATH, providers=["CPUExecutionProvider"])
    return names, mean, std, sess

def build_address_map(names):
    """
    Map *model feature names* to your Blueprint addresses.
    Convention: flexion->pitch, adduction->roll, pronation->yaw
    """
    mapping = {
        "LeftShoulder_flexion":  "/bone/upperarm_l/pitch",
        "LeftShoulder_abduction":"/bone/upperarm_l/roll",

        "RightShoulder_flexion":  "/bone/upperarm_r/pitch",
        "RightShoulder_abduction":"/bone/upperarm_r/roll",

        "LeftWrist_flexion":     "/bone/hand_l/pitch",
        "LeftWrist_adduction":   "/bone/hand_l/roll",
        "LeftWrist_pronation":   "/bone/hand_l/yaw",

        "RightWrist_flexion":    "/bone/hand_r/pitch",
        "RightWrist_adduction":  "/bone/hand_r/roll",
        "RightWrist_pronation":  "/bone/hand_r/yaw",
    }
    # Only keep addresses for the features present in the current model
    return {f: mapping[f] for f in names if f in mapping}

def turn_impulse_vector(names, turn_dir):
    """
    Minimal 'kick' for the first few frames to nudge the GRU into a left/right pattern.
    Tuned from earlier proxy weights (wL_flex=0.4, wL_add=0.5, wR_add=0.1).
    Positive = left, Negative = right (you can tweak if your rig flips signs).
    """
    w = dict.fromkeys(names, 0.0)
    sign = +1.0 if turn_dir == "left" else -1.0

    # Main drivers we discovered in EDA
    w_name = {
        "LeftWrist_flexion":   0.4 * sign,
        "LeftWrist_adduction": 0.5 * sign,
        "RightWrist_adduction":-0.1 * sign,  # counter-move
    }
    for k, v in w_name.items():
        if k in w: w[k] = v
    # Return as vector in model feature order
    return np.array([w[n] for n in names], dtype=np.float32)

def main():
    parser = argparse.ArgumentParser(description="Stream GRU next-frame predictions via OSC.")
    parser.add_argument("direction", choices=["left","right"], help="turn direction to nudge the generator")
    parser.add_argument("--host", default=OSC_HOST)
    parser.add_argument("--port", type=int, default=OSC_PORT)
    parser.add_argument("--hz", type=float, default=HZ)
    parser.add_argument("--seconds", type=float, default=0.0, help="run for N seconds (0 = until Ctrl+C)")
    args = parser.parse_args()

    names, mean, std, sess = load_assets()
    addr_map = build_address_map(names)
    if len(addr_map) == 0:
        print("No feature → OSC address overlap. Check your feature names and mapping.")
        sys.exit(1)

    client = SimpleUDPClient(args.host, args.port)
    input_name  = sess.get_inputs()[0].name   # "window"
    output_name = sess.get_outputs()[0].name  # "angles_next"

    F = len(names)
    # Seed window with neutral pose (z-scored zeros == mean). We'll add a small impulse for the first few frames.
    W = np.zeros((T, F), dtype=np.float32)   # z-scored space
    impulse = turn_impulse_vector(names, args.direction)

    print(f"Streaming '{args.direction}' at {args.hz:.1f} Hz → {args.host}:{args.port}")
    print("Features → OSC:")
    for f in names:
        if f in addr_map:
            print(f"  {f:>24s}  ->  {addr_map[f]}")
    print("-"*60)

    dt = 1.0 / max(1e-6, args.hz)
    t_end = time.time() + args.seconds if args.seconds > 0 else None
    step = 0
    try:
        while True:
            t0 = time.time()

            # small kick for first ~10 steps
            x = W.copy()
            if step < 10:
                x[-1] += impulse  # apply on most recent frame

            # ONNX inference (batch=1)
            y = sess.run([output_name], {input_name: x[None, ...]})[0][0]   # [F] in z-score space

            # update window (autoregressive)
            W = np.vstack([W[1:], y[None, :]])

            # denormalize to degrees
            y_deg = y * std + mean  # [F]

            # send OSC
            for i, f in enumerate(names):
                addr = addr_map.get(f)
                if addr:
                    client.send_message(addr, float(y_deg[i]))

            # pacing
            step += 1
            sleep = dt - (time.time() - t0)
            if sleep > 0:
                time.sleep(sleep)
            if t_end is not None and time.time() >= t_end:
                break
    except KeyboardInterrupt:
        pass

    print("Stopped.")

if __name__ == "__main__":
    main()