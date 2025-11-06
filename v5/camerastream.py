#!/usr/bin/env python3
# pose_to_unreal_osc_overlay.py
# Live camera → MediaPipe Pose(+Hands) → send OSC to Unreal + on-screen overlay (segments + joints).

import os, time, math, argparse
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
os.environ.setdefault("GLOG_minloglevel", "2")

import numpy as np
import cv2
from absl import logging as absl_logging
absl_logging.set_verbosity(absl_logging.ERROR)

from pythonosc.udp_client import SimpleUDPClient
import mediapipe as mp

# ------------------ Camera profiles ------------------
PROFILES = {
    0: {"name": "Sony (ILCE)",     "width": 1920, "height": 1080},
    1: {"name": "iPhone (Cont.)",  "width": 4032, "height": 3024},  # heavy; override with --width/--height if needed
}
BACKEND = cv2.CAP_AVFOUNDATION

# ------------------ OSC mapping (your table) ------------------
ADDR = {
    # Pelvis/Thorax/Neck
    "pelvis_pitch": ("/bone/pelvis/pitch", +1),
    "pelvis_roll":  ("/bone/pelvis/roll",  +1),
    "pelvis_yaw":   ("/bone/pelvis/yaw",   +1),

    "thorax_pitch": ("/bone/spine_03/pitch", +1),
    "thorax_roll":  ("/bone/spine_03/roll",  +1),
    "thorax_yaw":   ("/bone/spine_03/yaw",   +1),

    "neck_pitch":   ("/bone/neck_01/pitch", +1),
    "neck_roll":    ("/bone/neck_01/roll",  +1),
    "neck_yaw":     ("/bone/neck_01/yaw",   +1),

    # Shoulders
    "l_sh_flex": ("/bone/upperarm_l/yaw",   +1),
    "l_sh_abd":  ("/bone/upperarm_l/pitch", +1),
    "l_sh_er":   ("/bone/upperarm_l/roll",  +1),

    "r_sh_flex": ("/bone/upperarm_r/yaw",   +1),
    "r_sh_abd":  ("/bone/upperarm_r/pitch", +1),
    "r_sh_er":   ("/bone/upperarm_r/roll",  +1),

    # Elbows
    "l_elb_flex": ("/bone/lowerarm_l/pitch", +1),
    "l_elb_pro":  ("/bone/lowerarm_l/roll",  +1),
    "r_elb_flex": ("/bone/lowerarm_r/pitch", +1),
    "r_elb_pro":  ("/bone/lowerarm_r/roll",  +1),

    # Wrists
    "l_w_flex": ("/bone/hand_l/pitch", +1),
    "l_w_add":  ("/bone/hand_l/yaw",   +1),
    "l_w_pro":  ("/bone/hand_l/roll",  +1),

    "r_w_flex": ("/bone/hand_r/pitch", +1),
    "r_w_add":  ("/bone/hand_r/yaw",   +1),
    "r_w_pro":  ("/bone/hand_r/roll",  +1),
}

# Add leg/foot addresses (we’ll send zeros for now so UE stays stable)
ADDR.update({
    "l_hip_flex":  ("/bone/thigh_l/yaw",   -1),
    "l_thigh_abd": ("/bone/thigh_l/pitch", -1),
    "l_hip_er":    ("/bone/thigh_l/roll",  +1),
    "l_knee_flex": ("/bone/calf_l/pitch",  +1),
    "l_foot_flex": ("/bone/foot_l/pitch",  +1),
    "l_foot_add":  ("/bone/foot_l/yaw",    +1),
    "l_foot_pro":  ("/bone/foot_l/roll",   +1),
    "l_ball_flex": ("/bone/ball_l/pitch",  +1),

    "r_hip_flex":  ("/bone/thigh_r/yaw",   -1),
    "r_thigh_abd": ("/bone/thigh_r/pitch", +1),
    "r_hip_er":    ("/bone/thigh_r/roll",  +1),
    "r_knee_flex": ("/bone/calf_r/pitch",  +1),
    "r_foot_flex": ("/bone/foot_r/pitch",  +1),
    "r_foot_add":  ("/bone/foot_r/yaw",    +1),
    "r_foot_pro":  ("/bone/foot_r/roll",   +1),
    "r_ball_flex": ("/bone/ball_r/pitch",  +1),
})

# Add finger addresses (zeros for now; fill later if you want)
def add_finger_addr(side_letter):
    bprefix = {"thumb":"thumb","index":"index","middle":"middle","ring":"ring","pinky":"pinky"}
    s = "l" if side_letter=="l" else "r"
    for dname,bbase in bprefix.items():
        for j in ("01","02","03"):
            ADDR[f"{s}_{dname}_{j}_p"] = (f"/bone/{bbase}_{j.lower()}_{s}/pitch", -1)
            ADDR[f"{s}_{dname}_{j}_y"] = (f"/bone/{bbase}_{j.lower()}_{s}/yaw",   +1)
            ADDR[f"{s}_{dname}_{j}_r"] = (f"/bone/{bbase}_{j.lower()}_{s}/roll",  -1)
add_finger_addr("l"); add_finger_addr("r")

# ------------------ Math helpers ------------------
def vnorm(v):
    v = np.asarray(v, np.float32)
    n = np.linalg.norm(v) + 1e-8
    return v / n

def angle_between(v1, v2):
    v1, v2 = vnorm(v1), vnorm(v2)
    c = float(np.clip(np.dot(v1, v2), -1.0, 1.0))
    return math.degrees(math.acos(c))

def signed_angle_in_plane(vec, axis_normal, ref_axis):
    n  = vnorm(axis_normal)
    r  = vnorm(ref_axis)
    v  = vnorm(vec)
    r_p = vnorm(r - np.dot(r, n)*n)
    v_p = vnorm(v - np.dot(v, n)*n)
    x   = float(np.dot(r_p, v_p))
    y   = float(np.dot(np.cross(r_p, v_p), n))
    return math.degrees(math.atan2(y, x))

def basis_from_lr(left, right, up_hint):
    x = vnorm(right - left)            # left→right
    z = vnorm(np.cross(x, up_hint))    # forward-ish
    y = vnorm(np.cross(z, x))          # up-ish
    return x, y, z

# ------------------ Angle extraction ------------------
mp_pose  = mp.solutions.pose
mp_hands = mp.solutions.hands
POSE = mp_pose.PoseLandmark
def to_arr(lm): return np.array([lm.x, lm.y, lm.z], np.float32)

def compute_angles_pose(lms):
    out = {}
    L = POSE
    hip_l, hip_r = to_arr(lms[L.LEFT_HIP]),   to_arr(lms[L.RIGHT_HIP])
    sh_l,  sh_r  = to_arr(lms[L.LEFT_SHOULDER]), to_arr(lms[L.RIGHT_SHOULDER])
    el_l,  el_r  = to_arr(lms[L.LEFT_ELBOW]), to_arr(lms[L.RIGHT_ELBOW])
    wr_l,  wr_r  = to_arr(lms[L.LEFT_WRIST]), to_arr(lms[L.RIGHT_WRIST])
    nose         = to_arr(lms[L.NOSE])

    thorax_c  = 0.5*(sh_l + sh_r)
    up_world  = np.array([0,-1,0], np.float32)     # image up
    cam_x     = np.array([1,0,0],  np.float32)

    X_p, Y_p, Z_p = basis_from_lr(hip_l, hip_r, up_world)
    X_t, Y_t, Z_t = basis_from_lr(sh_l,  sh_r,  up_world)

    # Pelvis
    out["pelvis_pitch"] = signed_angle_in_plane(Y_p, X_p, up_world)   # flex/extend
    out["pelvis_roll"]  = signed_angle_in_plane(Y_p, Z_p, up_world)   # lateral tilt
    out["pelvis_yaw"]   = signed_angle_in_plane(X_p, up_world, cam_x) # axial

    # Thorax
    out["thorax_pitch"] = signed_angle_in_plane(Y_t, X_t, up_world)
    out["thorax_roll"]  = signed_angle_in_plane(Y_t, Z_t, up_world)
    out["thorax_yaw"]   = signed_angle_in_plane(X_t, up_world, cam_x)

    # Neck (vector from thorax to nose)
    neck_v = vnorm(nose - thorax_c)
    out["neck_pitch"] = signed_angle_in_plane(neck_v, X_t, up_world)
    out["neck_roll"]  = signed_angle_in_plane(neck_v, Z_t, up_world)
    out["neck_yaw"]   = signed_angle_in_plane(neck_v, up_world, X_t)

    # Arms
    upper_l = vnorm(el_l - sh_l);  upper_r = vnorm(el_r - sh_r)
    fore_l  = vnorm(wr_l - el_l);  fore_r  = vnorm(wr_r - el_r)

    out["l_sh_flex"] = signed_angle_in_plane(upper_l, Z_t, Y_t)   # sagittal
    out["l_sh_abd"]  = signed_angle_in_plane(upper_l, X_t, Y_t)   # coronal
    out["l_sh_er"]   = signed_angle_in_plane(fore_l, upper_l, Y_t)  # twist approx

    out["r_sh_flex"] = signed_angle_in_plane(upper_r, Z_t, Y_t)
    out["r_sh_abd"]  = signed_angle_in_plane(upper_r, -X_t, Y_t)  # mirror
    out["r_sh_er"]   = signed_angle_in_plane(fore_r, upper_r, Y_t)

    # Elbow flexion
    out["l_elb_flex"] = 180.0 - angle_between(upper_l, fore_l)
    out["r_elb_flex"] = 180.0 - angle_between(upper_r, fore_r)

    # Placeholders (wrist/pronation via Hands later)
    out["l_elb_pro"] = 0.0
    out["r_elb_pro"] = 0.0
    out["l_w_flex"] = out["l_w_add"] = out["l_w_pro"] = 0.0
    out["r_w_flex"] = out["r_w_add"] = out["r_w_pro"] = 0.0
    return out, (sh_l, el_l, wr_l, sh_r, el_r, wr_r)

def compute_wrist_from_hands(hres, pose_points):
    if hres is None or hres.multi_hand_landmarks is None:
        return {}
    sh_l, el_l, wr_l, sh_r, el_r, wr_r = pose_points
    out = {}
    for h, handed in zip(hres.multi_hand_landmarks, hres.multi_handedness):
        tag = handed.classification[0].label  # "Left" or "Right"
        lm = h.landmark
        pW = to_arr(lm[0]); pI = to_arr(lm[5]); pP = to_arr(lm[17]); pM = to_arr(lm[9])
        palm_x = vnorm(pI - pP)
        palm_y = vnorm(pM - pW)
        palm_n = vnorm(np.cross(palm_x, palm_y))
        if tag == "Left":
            fore = vnorm(wr_l - el_l); side = "l"
        else:
            fore = vnorm(wr_r - el_r); side = "r"
        flex = 180.0 - angle_between(fore, palm_y)           # bend
        add  = signed_angle_in_plane(palm_x, fore, palm_y)   # deviation
        pro  = signed_angle_in_plane(palm_n, fore, palm_y)   # roll
        out[f"{side}_w_flex"] = flex
        out[f"{side}_w_add"]  = add
        out[f"{side}_w_pro"]  = pro
        out[f"{side}_elb_pro"] = pro                         # use same as forearm pronation approx
    return out

# ------------------ Drawing (overlay) ------------------
JOINT_SPEC = mp.solutions.drawing_utils.DrawingSpec(color=(0,255,0), thickness=3, circle_radius=5)
BONE_SPEC  = mp.solutions.drawing_utils.DrawingSpec(color=(0,150,255), thickness=2, circle_radius=2)

C_BAR_TORSO = (30, 30, 230)
C_BAR_LARM  = (180, 60, 60)
C_BAR_RARM  = (60, 60, 180)
C_BAR_LLEG  = (60, 180, 60)
C_BAR_RLEG  = (60, 180, 160)

def to_px(pt, w, h):
    return int(pt.x * w), int(pt.y * h)

def draw_segment_bar(img, p1, p2, color, thickness=10):
    cv2.line(img, p1, p2, color, thickness=thickness)

def draw_pose_with_bars(frame, pose_landmarks):
    mp_draw = mp.solutions.drawing_utils
    mp_draw.draw_landmarks(
        frame, pose_landmarks, mp_pose.POSE_CONNECTIONS,
        landmark_drawing_spec=JOINT_SPEC,
        connection_drawing_spec=BONE_SPEC
    )
    lm = pose_landmarks.landmark
    L = POSE
    h, w = frame.shape[:2]
    hip_l = to_px(lm[L.LEFT_HIP],       w, h)
    hip_r = to_px(lm[L.RIGHT_HIP],      w, h)
    sh_l  = to_px(lm[L.LEFT_SHOULDER],  w, h)
    sh_r  = to_px(lm[L.RIGHT_SHOULDER], w, h)
    el_l  = to_px(lm[L.LEFT_ELBOW],     w, h)
    wr_l  = to_px(lm[L.LEFT_WRIST],     w, h)
    el_r  = to_px(lm[L.RIGHT_ELBOW],    w, h)
    wr_r  = to_px(lm[L.RIGHT_WRIST],    w, h)
    kn_l  = to_px(lm[L.LEFT_KNEE],      w, h)
    an_l  = to_px(lm[L.LEFT_ANKLE],     w, h)
    kn_r  = to_px(lm[L.RIGHT_KNEE],     w, h)
    an_r  = to_px(lm[L.RIGHT_ANKLE],    w, h)

    draw_segment_bar(frame, hip_l, hip_r, C_BAR_TORSO, 12)
    draw_segment_bar(frame, sh_l,  sh_r,  C_BAR_TORSO, 12)
    draw_segment_bar(frame, sh_l, el_l, C_BAR_LARM, 10)
    draw_segment_bar(frame, el_l, wr_l, C_BAR_LARM, 10)
    draw_segment_bar(frame, sh_r, el_r, C_BAR_RARM, 10)
    draw_segment_bar(frame, el_r, wr_r, C_BAR_RARM, 10)
    draw_segment_bar(frame, hip_l, kn_l, C_BAR_LLEG, 10)
    draw_segment_bar(frame, kn_l, an_l, C_BAR_LLEG, 10)
    draw_segment_bar(frame, hip_r, kn_r, C_BAR_RLEG, 10)
    draw_segment_bar(frame, kn_r, an_r, C_BAR_RLEG, 10)

# ------------------ Camera open ------------------
def open_camera(index, width, height):
    prof = PROFILES.get(index, {"name":"Unknown","width":1280,"height":720})
    req_w = prof["width"] if width is None else width
    req_h = prof["height"] if height is None else height
    cap = cv2.VideoCapture(index, BACKEND)
    if not cap.isOpened():
        raise SystemExit(f"❌ Could not open camera {index} ({prof['name']}). Close Zoom/OBS and retry.")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  req_w)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, req_h)
    ok,_ = cap.read()
    if not ok:
        cap.release()
        raise SystemExit("❌ Camera opened but returned no frames.")
    got_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); got_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"✅ Camera {index} ({prof['name']}): requested {req_w}x{req_h}, got ~{got_w}x{got_h}")
    return cap

# ------------------ Main ------------------
def main():
    ap = argparse.ArgumentParser(description="Pose(+Hands) → Unreal OSC + on-screen overlay")
    ap.add_argument("--cam", type=int, default=0, help="Camera index (0=Sony, 1=iPhone)")
    ap.add_argument("--width", type=int, default=None, help="Force width (else profile default)")
    ap.add_argument("--height", type=int, default=None, help="Force height (else profile default)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=9000)
    ap.add_argument("--fps-cap", type=int, default=30)
    ap.add_argument("--mirror", action="store_true", help="Mirror preview horizontally")
    args = ap.parse_args()

    # OSC
    osc = SimpleUDPClient(args.host, args.port)
    def osc_send(addr, val): osc.send_message(addr, float(val))

    # Models
    pose  = mp_pose.Pose(static_image_mode=False, model_complexity=2,
                         min_detection_confidence=0.3, min_tracking_confidence=0.3)
    hands = mp_hands.Hands(static_image_mode=False, max_num_hands=2, model_complexity=1,
                           min_detection_confidence=0.3, min_tracking_confidence=0.3)

    # Camera + window
    cap = open_camera(args.cam, args.width, args.height)
    win = f"Pose→UE OSC (cam {args.cam}) — press q/ESC to quit"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)

    t_prev = time.time()
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("⚠️ frame read failed; exiting.")
                break
            if args.mirror:
                frame = cv2.flip(frame, 1)

            rgb = frame[:,:,::-1]
            pres = pose.process(rgb)
            hres = hands.process(rgb)

            # compute angles & send
            if pres.pose_landmarks:
                lms = pres.pose_landmarks.landmark
                angles, pose_points = compute_angles_pose(lms)
                wang = compute_wrist_from_hands(hres, pose_points)
                angles.update(wang)
                # Only send shoulder flexion (sagittal plane); zero out abduction, external rotation, and everything else
                sagittal_shoulder_keys = ("l_sh_flex", "r_sh_flex")
                for key,(addr,sgn) in ADDR.items():
                    if key in sagittal_shoulder_keys:
                        osc_send(addr, sgn * float(angles.get(key, 0.0)))
                    else:
                        osc_send(addr, 0.0)
            else:
                # keep rig stable
                for key,(addr,sgn) in ADDR.items():
                    osc_send(addr, 0.0)

            # overlay
            if pres.pose_landmarks:
                draw_pose_with_bars(frame, pres.pose_landmarks)
                cv2.putText(frame, "POSE: OK", (12,30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,220,0), 2)
            else:
                cv2.putText(frame, "POSE: not detected (step back / add light)",
                            (12,30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,255), 2)

            if hres and hres.multi_hand_landmarks:
                for h in hres.multi_hand_landmarks:
                    mp.solutions.drawing_utils.draw_landmarks(
                        frame, h, mp_hands.HAND_CONNECTIONS,
                        mp.solutions.drawing_utils.DrawingSpec(color=(40,180,240), thickness=2, circle_radius=3),
                        mp.solutions.drawing_utils.DrawingSpec(color=(40,180,240), thickness=2)
                    )

            # FPS overlay
            now = time.time()
            fps = 1.0 / max(1e-6, now - t_prev); t_prev = now
            cv2.putText(frame, f"FPS {fps:4.1f}", (12,frame.shape[0]-12),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2)

            cv2.imshow(win, frame)
            if cv2.waitKey(max(1, int(1000/args.fps_cap))) & 0xFF in (27, ord('q')):
                break

    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        pose.close(); hands.close()
        cv2.destroyAllWindows()

# (internal) helper adjusted signature for reuse above
def compute_angles_pose(lms):
    out = {}
    L = POSE
    hip_l, hip_r = to_arr(lms[L.LEFT_HIP]),   to_arr(lms[L.RIGHT_HIP])
    sh_l,  sh_r  = to_arr(lms[L.LEFT_SHOULDER]), to_arr(lms[L.RIGHT_SHOULDER])
    el_l,  el_r  = to_arr(lms[L.LEFT_ELBOW]), to_arr(lms[L.RIGHT_ELBOW])
    wr_l,  wr_r  = to_arr(lms[L.LEFT_WRIST]), to_arr(lms[L.RIGHT_WRIST])
    nose         = to_arr(lms[L.NOSE])

    thorax_c  = 0.5*(sh_l + sh_r)
    up_world  = np.array([0,-1,0], np.float32)
    cam_x     = np.array([1,0,0],  np.float32)

    X_p, Y_p, Z_p = basis_from_lr(hip_l, hip_r, up_world)
    X_t, Y_t, Z_t = basis_from_lr(sh_l,  sh_r,  up_world)

    out["pelvis_pitch"] = signed_angle_in_plane(Y_p, X_p, up_world)
    out["pelvis_roll"]  = signed_angle_in_plane(Y_p, Z_p, up_world)
    out["pelvis_yaw"]   = signed_angle_in_plane(X_p, up_world, cam_x)

    out["thorax_pitch"] = signed_angle_in_plane(Y_t, X_t, up_world)
    out["thorax_roll"]  = signed_angle_in_plane(Y_t, Z_t, up_world)
    out["thorax_yaw"]   = signed_angle_in_plane(X_t, up_world, cam_x)

    neck_v = vnorm(nose - thorax_c)
    out["neck_pitch"] = signed_angle_in_plane(neck_v, X_t, up_world)
    out["neck_roll"]  = signed_angle_in_plane(neck_v, Z_t, up_world)
    out["neck_yaw"]   = signed_angle_in_plane(neck_v, up_world, X_t)

    upper_l = vnorm(el_l - sh_l);  upper_r = vnorm(el_r - sh_r)
    fore_l  = vnorm(wr_l - el_l);  fore_r  = vnorm(wr_r - el_r)

    out["l_sh_flex"] = signed_angle_in_plane(upper_l, Z_t, Y_t)
    out["l_sh_abd"]  = signed_angle_in_plane(upper_l, X_t, Y_t)
    out["l_sh_er"]   = signed_angle_in_plane(fore_l, upper_l, Y_t)

    out["r_sh_flex"] = signed_angle_in_plane(upper_r, Z_t, Y_t)
    out["r_sh_abd"]  = signed_angle_in_plane(upper_r, -X_t, Y_t)
    out["r_sh_er"]   = signed_angle_in_plane(fore_r, upper_r, Y_t)

    out["l_elb_flex"] = 180.0 - angle_between(upper_l, fore_l)
    out["r_elb_flex"] = 180.0 - angle_between(upper_r, fore_r)

    out["l_elb_pro"] = 0.0
    out["r_elb_pro"] = 0.0
    out["l_w_flex"] = out["l_w_add"] = out["l_w_pro"] = 0.0
    out["r_w_flex"] = out["r_w_add"] = out["r_w_pro"] = 0.0
    # also return pose points needed by hands pass
    return out, (to_arr(lms[L.LEFT_SHOULDER]), to_arr(lms[L.LEFT_ELBOW]), to_arr(lms[L.LEFT_WRIST]),
                 to_arr(lms[L.RIGHT_SHOULDER]),to_arr(lms[L.RIGHT_ELBOW]),to_arr(lms[L.RIGHT_WRIST]))

if __name__ == "__main__":
    main()