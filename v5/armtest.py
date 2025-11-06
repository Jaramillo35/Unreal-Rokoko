#!/usr/bin/env python3
# shoulder_calibration.py
# Camera → MediaPipe Pose → ISB JCS (abd, flex, er)
# Guided blocks with PREP (no recording) then RECORD (10s) with big on-screen prompts.
# Saves raw CSV (per-frame during RECORD only) + summary JSON (per-block means/std + intended targets).

import os, sys, time, math, argparse, csv, json, datetime
import numpy as np
import cv2
from absl import logging as absl_logging
absl_logging.set_verbosity(absl_logging.ERROR)
import mediapipe as mp

# =================== Calibration blocks ===================
# Each block: (label, big_text_for_pose, record_duration_s, desired_targets)
CALIB_BLOCKS = [
    # --- ABDUCTION (coronal) ---
    ("abd_down",
     "ABDUCTION\nArms next to legs\n→ Target abd = +30°",
     10.0, {"abd": 30.0}),
    ("abd_tpose",
     "ABDUCTION\nT pose (arms parallel to floor)\n→ Target abd = -60°",
     10.0, {"abd": -60.0}),
    ("abd_up",
     "ABDUCTION\nArms up (overhead)\n→ Target abd = -150°",
     10.0, {"abd": -150.0}),

    # --- FLEXION (sagittal) ---
    ("flex_down",
     "FLEXION\nArms next to legs\n→ Target flex = 0°",
     10.0, {"flex": 0.0}),
    ("flex_front",
     "FLEXION\nArms in front (shoulder height)\n→ Target flex = 90°",
     10.0, {"flex": 90.0}),
    ("flex_up",
     "FLEXION\nArms up (biceps by ears)\nKeep ABD ≈ 30°\n→ Targets flex = 150°, abd = 30°",
     10.0, {"flex": 150.0, "abd": 30.0}),
]

# =================== Camera ===================
PROFILES = {0: {"name": "Default", "width": 1280, "height": 720}}
BACKEND = cv2.CAP_AVFOUNDATION

def open_camera(index, width, height):
    prof = PROFILES.get(index, {"name":"Unknown","width":1280,"height":720})
    req_w = prof["width"] if width is None else width
    req_h = prof["height"] if height is None else height
    cap = cv2.VideoCapture(index, BACKEND)
    if not cap.isOpened():
        raise SystemExit(f"❌ Could not open camera {index} ({prof['name']}).")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  req_w)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, req_h)
    ok,_ = cap.read()
    if not ok:
        cap.release(); raise SystemExit("❌ Camera opened but returned no frames.")
    got_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); got_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"✅ Camera {index} ({prof['name']}): requested {req_w}x{req_h}, got ~{got_w}x{got_h}")
    return cap

# =================== ISB JCS math ===================
mp_pose = mp.solutions.pose
POSE = mp_pose.PoseLandmark

def arr(lm): return np.array([lm.x, lm.y, lm.z], np.float32)
def vnorm(v): v = np.asarray(v, np.float32); n = np.linalg.norm(v); return v / (n + 1e-8)

def basis_from_lr(left, right, up_hint):
    x = vnorm(right - left)              # left→right
    z = vnorm(np.cross(x, up_hint))      # forward-ish
    y = vnorm(np.cross(z, x))            # up-ish
    return x, y, z

def signed_angle(a, b, n):
    a = vnorm(a); b = vnorm(b); n = vnorm(n)
    x = float(np.dot(a, b)); y = float(np.dot(np.cross(a, b), n))
    return math.degrees(math.atan2(y, x))

def proj_on_plane(v, n): n=vnorm(n); return vnorm(v - np.dot(v, n)*n)

def jcs_angles(prox_R, dist_R, e1_prox, e3_dist):
    """
    Grood–Suntay:
      alpha  about e1_prox  (plane of elevation ~ abduction/adduction)
      beta   about e2       (elevation ~ flexion/extension)
      gamma  about e3_dist  (axial rotation ~ ER/IR)
    """
    e1 = vnorm(e1_prox)
    e3 = vnorm(e3_dist)
    e2 = vnorm(np.cross(e3, e1))
    if np.linalg.norm(e2) < 1e-6:
        e2 = vnorm(np.cross(e3, prox_R[:,0]))
        if np.linalg.norm(e2) < 1e-6: e2 = vnorm(np.cross(e3, prox_R[:,1]))

    # beta (elevation)
    e3p  = proj_on_plane(e3, e1)
    beta = signed_angle(e3p, e3, e2)

    # alpha (plane of elevation)
    prox_z = vnorm(prox_R[:,2])
    u_ref  = proj_on_plane(prox_z, e1)
    u_flt  = proj_on_plane(np.cross(e2, e1), e1)
    alpha = 0.0 if (np.linalg.norm(u_ref)<1e-6 or np.linalg.norm(u_flt)<1e-6) else signed_angle(u_ref, u_flt, e1)

    # gamma (axial)
    dist_x = vnorm(dist_R[:,0])
    w_ref  = proj_on_plane(dist_x, e3)
    w_flt  = proj_on_plane(np.cross(e1, e2), e3)
    gamma = 0.0 if (np.linalg.norm(w_ref)<1e-6 or np.linalg.norm(w_flt)<1e-6) else signed_angle(w_ref, w_flt, e3)
    return alpha, beta, gamma

def compute_shoulder_isb(lms):
    """Return dict with l_abd, l_flex, l_er, r_abd, r_flex, r_er in degrees (ISB JCS)."""
    L = POSE
    up_world = np.array([0,-1,0], np.float32)

    sh_l, sh_r = arr(lms[L.LEFT_SHOULDER]),  arr(lms[L.RIGHT_SHOULDER])
    el_l, el_r = arr(lms[L.LEFT_ELBOW]),     arr(lms[L.RIGHT_ELBOW])

    # Thorax = proximal segment
    X_t, Y_t, Z_t = basis_from_lr(sh_l, sh_r, up_world)
    R_thorax = np.stack([X_t, Y_t, Z_t], axis=1)

    # Humerus axis (shoulder→elbow) = distal e3
    hum_l = vnorm(el_l - sh_l)
    hum_r = vnorm(el_r - sh_r)
    R_hum_L = np.stack([hum_l, np.cross(Z_t, hum_l), Z_t], axis=1)
    R_hum_R = np.stack([hum_r, np.cross(Z_t, hum_r), Z_t], axis=1)

    aL, bL, gL = jcs_angles(R_thorax, R_hum_L, e1_prox=Y_t, e3_dist=hum_l)
    aR, bR, gR = jcs_angles(R_thorax, R_hum_R, e1_prox=Y_t, e3_dist=hum_r)

    return {"l_abd": aL, "l_flex": bL, "l_er": gL,
            "r_abd": aR, "r_flex": bR, "r_er": gR}

# =================== Overlay ===================
mp_draw = mp.solutions.drawing_utils
JOINT_SPEC = mp_draw.DrawingSpec(color=(0,255,0), thickness=2, circle_radius=3)
BONE_SPEC  = mp_draw.DrawingSpec(color=(0,150,255), thickness=2, circle_radius=1)

def draw_pose(frame, landmarks):
    mp_draw.draw_landmarks(
        frame, landmarks, mp_pose.POSE_CONNECTIONS,
        landmark_drawing_spec=JOINT_SPEC,
        connection_drawing_spec=BONE_SPEC
    )

def big_text(frame, lines, color=(255,255,255), bg=(20,20,20), alpha=0.7):
    """Draw a semi-transparent panel with big multi-line text centered top."""
    h, w = frame.shape[:2]
    pad = 20
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 1.1
    thickness = 3
    sizes = [cv2.getTextSize(line, font, scale, thickness)[0] for line in lines]
    text_w = max(s[0] for s in sizes)
    text_h = sum(s[1] for s in sizes) + (len(lines)-1)*10
    x = (w - text_w)//2 - pad
    y = 30
    panel_w = text_w + 2*pad
    panel_h = text_h + 2*pad
    overlay = frame.copy()
    cv2.rectangle(overlay, (x, y), (x+panel_w, y+panel_h), bg, -1)
    cv2.addWeighted(overlay, alpha, frame, 1-alpha, 0, frame)
    ty = y + pad + sizes[0][1]
    for i, line in enumerate(lines):
        (tw, th), _ = cv2.getTextSize(line, font, scale, thickness)
        tx = x + (panel_w - tw)//2
        cv2.putText(frame, line, (tx, ty), font, scale, color, thickness, cv2.LINE_AA)
        ty += th + 10

def countdown_line(frame, t_left, t_total, label=""):
    """Draw a progress bar at bottom + seconds left."""
    h, w = frame.shape[:2]
    p = max(0.0, min(1.0, 1.0 - t_left / max(t_total, 1e-6)))
    bar_w = int(w * p)
    cv2.rectangle(frame, (0, h-20), (bar_w, h), (0, 200, 0), -1)
    cv2.putText(frame, f"{label} {int(max(0, t_left))}s",
                (10, h-30), cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                (255,255,255), 2, cv2.LINE_AA)

# =================== Main ===================
def main():
    ap = argparse.ArgumentParser(description="Shoulder calibration recorder (abd & flex) with prep time")
    ap.add_argument("--cam", type=int, default=0)
    ap.add_argument("--width", type=int, default=None)
    ap.add_argument("--height", type=int, default=None)
    ap.add_argument("--fps-cap", type=int, default=30)
    ap.add_argument("--mirror", action="store_true")
    ap.add_argument("--prep-s", type=float, default=5.0, help="Seconds to prepare before each recording block")
    args = ap.parse_args()

    # Setup output files
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_csv_path   = f"shoulder_calib_raw_{ts}.csv"
    summary_path   = f"shoulder_calib_summary_{ts}.json"

    # CSV header (only recorded during RECORD phase)
    csv_header = [
        "timestamp", "block_id", "phase_label",
        "l_abd","l_flex","l_er","r_abd","r_flex","r_er"
    ]

    pose = mp_pose.Pose(static_image_mode=False, model_complexity=2,
                        min_detection_confidence=0.3, min_tracking_confidence=0.3)
    cap = open_camera(args.cam, args.width, args.height)
    win = "Shoulder Calibration — q/ESC to quit"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)

    # Prepare CSV
    csv_file = open(raw_csv_path, "w", newline="")
    writer = csv.writer(csv_file)
    writer.writerow(csv_header)

    summary = {
        "created": ts,
        "prep_seconds": args.prep_s,
        "blocks": [],  # one entry per calibration block with means/std and desired targets
    }

    try:
        block_total = len(CALIB_BLOCKS)
        for idx, (label, text, rec_dur, targets) in enumerate(CALIB_BLOCKS, start=1):
            print(f"\n=== Block {idx}/{block_total}: {label} ===")

            # -------- PREP PHASE (no recording) --------
            prep_start = time.time()
            while True:
                ok, frame = cap.read()
                if not ok:
                    print("⚠️ frame read failed; aborting.")
                    return
                if args.mirror:
                    frame = cv2.flip(frame, 1)

                rgb = frame[:, :, ::-1]
                res = pose.process(rgb)
                if res.pose_landmarks:
                    draw_pose(frame, res.pose_landmarks)

                t_now = time.time()
                t_left = args.prep_s - (t_now - prep_start)

                # Overlay: pose text + "GET READY" + countdown
                lines = text.split("\n") + ["", "GET INTO POSITION"]
                big_text(frame, lines)
                countdown_line(frame, t_left, args.prep_s, label="PREP")

                # HUD: which block
                cv2.putText(frame, f"{label}  ({idx}/{block_total})",
                            (12, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255,255,255), 2, cv2.LINE_AA)

                cv2.imshow(win, frame)
                key = cv2.waitKey(max(1, int(1000/args.fps_cap))) & 0xFF
                if key in (27, ord('q')):
                    raise KeyboardInterrupt
                if t_left <= 0:
                    break

            # -------- RECORD PHASE (write to CSV) --------
            print(f"    ▶ Recording {rec_dur:.0f}s ...")
            block_samples = []
            rec_start = time.time()
            while True:
                ok, frame = cap.read()
                if not ok:
                    print("⚠️ frame read failed; aborting.")
                    return
                if args.mirror:
                    frame = cv2.flip(frame, 1)

                rgb = frame[:, :, ::-1]
                res = pose.process(rgb)

                # compute angles if landmarks available
                l_abd = l_flex = l_er = r_abd = r_flex = r_er = np.nan
                if res.pose_landmarks:
                    angles = compute_shoulder_isb(res.pose_landmarks.landmark)
                    l_abd, l_flex, l_er = angles["l_abd"], angles["l_flex"], angles["l_er"]
                    r_abd, r_flex, r_er = angles["r_abd"], angles["r_flex"], angles["r_er"]
                    draw_pose(frame, res.pose_landmarks)

                # record row (epoch seconds)
                t_now = time.time()
                writer.writerow([t_now, idx, label, l_abd, l_flex, l_er, r_abd, r_flex, r_er])
                block_samples.append((l_abd, l_flex, l_er, r_abd, r_flex, r_er))

                # overlay: pose text + countdown (RECORD)
                lines = text.split("\n") + ["", "RECORDING"]
                big_text(frame, lines)
                t_left = rec_dur - (t_now - rec_start)
                countdown_line(frame, t_left, rec_dur, label="RECORD")

                # HUD
                cv2.putText(frame, f"{label}  ({idx}/{block_total})",
                            (12, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255,255,255), 2, cv2.LINE_AA)

                cv2.imshow(win, frame)
                key = cv2.waitKey(max(1, int(1000/args.fps_cap))) & 0xFF
                if key in (27, ord('q')):
                    raise KeyboardInterrupt
                if t_left <= 0:
                    break

            # Compute means/std for this block (ignore NaNs)
            arr_block = np.array(block_samples, dtype=np.float32)  # Nx6
            means = np.nanmean(arr_block, axis=0).tolist()
            stds  = np.nanstd(arr_block, axis=0).tolist()

            summary["blocks"].append({
                "index": idx,
                "label": label,
                "prep_seconds": args.prep_s,
                "record_seconds": rec_dur,
                "targets": targets,  # intended UE values for this pose
                "means": {
                    "l_abd": means[0], "l_flex": means[1], "l_er": means[2],
                    "r_abd": means[3], "r_flex": means[4], "r_er": means[5],
                },
                "stds": {
                    "l_abd": stds[0], "l_flex": stds[1], "l_er": stds[2],
                    "r_abd": stds[3], "r_flex": stds[4], "r_er": stds[5],
                }
            })

            print(f"    ✔ Saved block {idx}: "
                  f"L[abd {means[0]:.1f}, flex {means[1]:.1f}, er {means[2]:.1f}] | "
                  f"R[abd {means[3]:.1f}, flex {means[4]:.1f}, er {means[5]:.1f}]")

        print("\n✅ Calibration capture complete.")

    except KeyboardInterrupt:
        print("\n⏹️  Calibration interrupted by user.")
    finally:
        csv_file.close()
        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=2)
        cap.release()
        cv2.destroyAllWindows()
        print(f"\nRaw per-frame CSV: {os.path.abspath(raw_csv_path)}")
        print(f"Summary JSON:      {os.path.abspath(summary_path)}")

if __name__ == "__main__":
    main()