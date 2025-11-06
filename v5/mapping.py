#!/usr/bin/env python3
# pose_to_unreal_osc_overlay.py
# Live camera → MediaPipe Pose(+Hands) → ISB JCS angles → calibration-driven shoulder mapping → OSC to Unreal + overlay.

import os, time, math, argparse, json, sys
from typing import Dict, List, Tuple
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
os.environ.setdefault("GLOG_minloglevel", "2")

# ===================== TOGGLES (edit these) =====================
SEND_PELVIS     = False
SEND_THORAX     = False
SEND_NECK       = False

SEND_SHOULDERS_L = True
SEND_SHOULDERS_R = True
SEND_ELBOWS_L    = False
SEND_ELBOWS_R    = False
SEND_WRISTS_L    = False
SEND_WRISTS_R    = False

SEND_LEG_L      = False
SEND_LEG_R      = False

SEND_FINGERS_L  = False
SEND_FINGERS_R  = False
# ================================================================

# ===================== SHOULDER LOGIC MAP =======================
# Desired UE abduction at your three canonical poses:
TARGET_ABD = {
    "down":     0.0,   # arms by side → slight away from body
    "t_pose":  -60.0,   # T shape
    "overhead": -150.0  # biceps next to ears
}

# Hold other axes so only coronal plane moves (flip to False if you want them live too):
HOLD_FLEX_AT_ZERO = False   # keep l/r_sh_flex at 0 after mapping (we still *read* it to drive abduction)
HOLD_ER_AT_ZERO   = False   # keep l/r_sh_er at 0

# Clamp outgoing abduction (safety)
ABD_MIN_DEG, ABD_MAX_DEG = -170.0, 170.0

# On-screen debug of shoulder mapping:
SHOW_SH_DEBUG = True
# ================================================================

# ===================== SMOOTHING (edit these) =====================
SMOOTH_ENABLED  = True
SMOOTH_METHOD   = "one_euro"    # "one_euro" | "ema" | "none"

# One Euro
ONEEURO_MIN_CUTOFF = 1.4        # Hz
ONEEURO_BETA       = 0.03
ONEEURO_D_CUTOFF   = 1.0

# EMA (alternative)
EMA_CUTOFF_HZ      = 3.0

# Post-filters
DEADBAND_DEG       = 0.2
SLEW_LIMIT_DEG_S   = 360.0
# ================================================================

import numpy as np
import cv2
from absl import logging as absl_logging
absl_logging.set_verbosity(absl_logging.ERROR)
from pythonosc.udp_client import SimpleUDPClient
import mediapipe as mp

# ------------------ Camera profiles ------------------
PROFILES = {
    0: {"name": "Sony (ILCE)",     "width": 1920, "height": 1080},
    1: {"name": "iPhone (Cont.)",  "width": 4032, "height": 3024},
}
BACKEND = cv2.CAP_AVFOUNDATION

# ------------------ Mapping loader ------------------
DEFAULT_MAPPING_PATH = "/Users/martinjaramillo/Documents/Unreal+Rokoko/v5/auto_axis_mapping.json"

def load_axis_mapping(path: str):
    try:
        with open(path, "r") as f:
            data = json.load(f)
        # Normalize values to lower-case pitch|yaw|roll
        for bone, axes in data.items():
            for k, v in list(axes.items()):
                axes[k] = str(v).strip().lower()
        return data
    except Exception as e:
        print(f"❌ Could not load axis mapping JSON: {path}\n{e}")
        sys.exit(1)

def semantic_exists(mapping, bone_addr: str, semantic: str) -> bool:
    axes = mapping.get(bone_addr, {})
    return semantic in (axes.get("x_deg"), axes.get("y_deg"), axes.get("z_deg"))

def _warn_missing(mapping, bone_addr, semantic, keyname):
    if bone_addr not in mapping:
        print(f"⚠️  JSON has no entry for {bone_addr} (needed by '{keyname}'). Using endpoint anyway.")
    elif not semantic_exists(mapping, bone_addr, semantic):
        axes = mapping[bone_addr]
        have = [axes.get("x_deg"), axes.get("y_deg"), axes.get("z_deg")]
        print(f"⚠️  {bone_addr}: JSON does not list '{semantic}' among {have} (for '{keyname}'). Using endpoint anyway.")

def build_addr_from_json(mapping_path: str, group_toggles: dict):
    """
    Returns:
      ADDR (filtered): key -> ("/bone/.../(pitch|yaw|roll)", sign)
      KEY_GROUPS (filtered): key -> group_name
    """
    m = load_axis_mapping(mapping_path)

    # --- Signs (UE axis directions) ---
    SIGNS = {
        # pelvis / thorax / neck
        "pelvis_pitch": +1, "pelvis_roll": +1, "pelvis_yaw": +1,
        "thorax_pitch": +1, "thorax_roll": +1, "thorax_yaw": +1,
        "neck_pitch":   +1, "neck_roll":   +1, "neck_yaw":   +1,

        # shoulders (note L flex sign often opposite to R in some rigs; keep your previous)
        "l_sh_flex": -1, "l_sh_abd": +1, "l_sh_er": +1,
        "r_sh_flex": +1, "r_sh_abd": +1, "r_sh_er": +1,

        # elbows
        "l_elb_flex": +1, "l_elb_pro": +1,
        "r_elb_flex": +1, "r_elb_pro": +1,

        # wrists
        "l_w_flex": +1, "l_w_add": +1, "l_w_pro": +1,
        "r_w_flex": +1, "r_w_add": +1, "r_w_pro": +1,

        # legs/feet
        "l_hip_flex": -1, "l_thigh_abd": -1, "l_hip_er": +1, "l_knee_flex": +1,
        "l_foot_flex": +1, "l_foot_add": +1, "l_foot_pro": +1, "l_ball_flex": +1,
        "r_hip_flex": -1, "r_thigh_abd": +1, "r_hip_er": +1, "r_knee_flex": +1,
        "r_foot_flex": +1, "r_foot_add": +1, "r_foot_pro": +1, "r_ball_flex": +1,
    }

    # --- Semantic → (bone, endpoint_name) mapping ---
    SEM_TO_BONE = {
        # Pelvis/Thorax/Neck
        "pelvis_pitch": ("/bone/pelvis",   "pitch"),
        "pelvis_roll":  ("/bone/pelvis",   "roll"),
        "pelvis_yaw":   ("/bone/pelvis",   "yaw"),

        "thorax_pitch": ("/bone/spine_03", "pitch"),
        "thorax_roll":  ("/bone/spine_03", "roll"),
        "thorax_yaw":   ("/bone/spine_03", "yaw"),

        "neck_pitch":   ("/bone/neck_01",  "pitch"),
        "neck_roll":    ("/bone/neck_01",  "roll"),
        "neck_yaw":     ("/bone/neck_01",  "yaw"),

        # Shoulders
        "l_sh_flex": ("/bone/upperarm_l", "yaw"),
        "l_sh_abd":  ("/bone/upperarm_l", "pitch"),
        "l_sh_er":   ("/bone/upperarm_l", "roll"),

        "r_sh_flex": ("/bone/upperarm_r", "yaw"),
        "r_sh_abd":  ("/bone/upperarm_r", "pitch"),
        "r_sh_er":   ("/bone/upperarm_r", "roll"),

        # Elbows
        "l_elb_flex": ("/bone/lowerarm_l", "pitch"),
        "l_elb_pro":  ("/bone/lowerarm_l", "roll"),
        "r_elb_flex": ("/bone/lowerarm_r", "pitch"),
        "r_elb_pro":  ("/bone/lowerarm_r", "roll"),

        # Wrists
        "l_w_flex": ("/bone/hand_l", "pitch"),
        "l_w_add":  ("/bone/hand_l", "yaw"),
        "l_w_pro":  ("/bone/hand_l", "roll"),
        "r_w_flex": ("/bone/hand_r", "pitch"),
        "r_w_add":  ("/bone/hand_r", "yaw"),
        "r_w_pro":  ("/bone/hand_r", "roll"),

        # Legs/feet
        "l_hip_flex":  ("/bone/thigh_l", "yaw"),
        "l_thigh_abd": ("/bone/thigh_l", "pitch"),
        "l_hip_er":    ("/bone/thigh_l", "roll"),
        "l_knee_flex": ("/bone/calf_l",  "pitch"),
        "l_foot_flex": ("/bone/foot_l",  "pitch"),
        "l_foot_add":  ("/bone/foot_l",  "yaw"),
        "l_foot_pro":  ("/bone/foot_l",  "roll"),
        "l_ball_flex": ("/bone/ball_l",  "pitch"),

        "r_hip_flex":  ("/bone/thigh_r", "yaw"),
        "r_thigh_abd": ("/bone/thigh_r", "pitch"),
        "r_hip_er":    ("/bone/thigh_r", "roll"),
        "r_knee_flex": ("/bone/calf_r",  "pitch"),
        "r_foot_flex": ("/bone/foot_r",  "pitch"),
        "r_foot_add":  ("/bone/foot_r",  "yaw"),
        "r_foot_pro":  ("/bone/foot_r",  "roll"),
        "r_ball_flex": ("/bone/ball_r",  "pitch"),
    }

    # --- Key → group name ---
    KEY_GROUPS = {
        "pelvis_pitch":"pelvis","pelvis_roll":"pelvis","pelvis_yaw":"pelvis",
        "thorax_pitch":"thorax","thorax_roll":"thorax","thorax_yaw":"thorax",
        "neck_pitch":"neck","neck_roll":"neck","neck_yaw":"neck",
        "l_sh_flex":"shoulders_l","l_sh_abd":"shoulders_l","l_sh_er":"shoulders_l",
        "r_sh_flex":"shoulders_r","r_sh_abd":"shoulders_r","r_sh_er":"shoulders_r",
        "l_elb_flex":"elbows_l","l_elb_pro":"elbows_l",
        "r_elb_flex":"elbows_r","r_elb_pro":"elbows_r",
        "l_w_flex":"wrists_l","l_w_add":"wrists_l","l_w_pro":"wrists_l",
        "r_w_flex":"wrists_r","r_w_add":"wrists_r","r_w_pro":"wrists_r",
        "l_hip_flex":"leg_l","l_thigh_abd":"leg_l","l_hip_er":"leg_l",
        "l_knee_flex":"leg_l","l_foot_flex":"leg_l","l_foot_add":"leg_l","l_foot_pro":"leg_l","l_ball_flex":"leg_l",
        "r_hip_flex":"leg_r","r_thigh_abd":"leg_r","r_hip_er":"leg_r",
        "r_knee_flex":"leg_r","r_foot_flex":"leg_r","r_foot_add":"leg_r","r_foot_pro":"leg_r","r_ball_flex":"leg_r",
    }

    # Build base ADDR (all)
    ADDR = {}
    for key, (bone, sem) in SEM_TO_BONE.items():
        _warn_missing(m, bone, sem, key)
        ADDR[key] = (f"{bone}/{sem}", SIGNS.get(key, +1))

    # --- Filter by toggles ---
    enabled_groups = {name for name, on in group_toggles.items() if on}
    ADDR_f = {}
    KEY_GROUPS_f = {}
    for key, (addr, sgn) in ADDR.items():
        grp = KEY_GROUPS.get(key, None)
        if grp is None or grp in enabled_groups:
            ADDR_f[key] = (addr, sgn)
            KEY_GROUPS_f[key] = grp

    print("✅ Using axis mapping JSON:", mapping_path)
    print("✅ Enabled groups:", ", ".join(sorted(enabled_groups)) if enabled_groups else "(none)")
    sample = [k for k in ("l_sh_flex","l_sh_abd","l_sh_er","r_sh_flex","r_sh_abd","r_sh_er") if k in ADDR_f]
    for k in sample:
        addr, sgn = ADDR_f[k]
        print(f"    {k:12s} → {addr:32s} (sign {sgn:+d})")

    return ADDR_f, KEY_GROUPS_f

# ------------------ ISB JCS math helpers ------------------
def vnorm(v):
    v = np.asarray(v, np.float32)
    n = np.linalg.norm(v)
    return v / (n + 1e-8)

def basis_from_lr(left, right, up_hint):
    x = vnorm(right - left)             # left→right
    z = vnorm(np.cross(x, up_hint))     # forward-ish
    y = vnorm(np.cross(z, x))           # up-ish
    return x, y, z

def signed_angle(a, b, n):
    a = vnorm(a); b = vnorm(b); n = vnorm(n)
    x = float(np.dot(a, b))
    y = float(np.dot(np.cross(a, b), n))
    return math.degrees(math.atan2(y, x))

def proj_on_plane(v, n):
    n = vnorm(n)
    return vnorm(v - np.dot(v, n) * n)

def jcs_angles(prox_R, dist_R, e1_prox, e3_dist):
    """
    Grood–Suntay:
      e1 = axis fixed in proximal segment
      e3 = axis fixed in distal segment
      e2 = normalize(e3 × e1)  (floating)
    Returns (alpha about e1, beta about e2, gamma about e3) in degrees.
    """
    e1 = vnorm(e1_prox)
    e3 = vnorm(e3_dist)
    e2 = vnorm(np.cross(e3, e1))
    if np.linalg.norm(e2) < 1e-6:
        e2 = vnorm(np.cross(e3, prox_R[:, 0]))
        if np.linalg.norm(e2) < 1e-6:
            e2 = vnorm(np.cross(e3, prox_R[:, 1]))

    # beta: angle from projection of e3 on plane ⟂ e1 to e3, signed about e2
    e3_perp_e1 = proj_on_plane(e3, e1)
    beta = signed_angle(e3_perp_e1, e3, e2)

    # alpha: rotation about e1 comparing proximal ref to floating-plane ref
    prox_z = vnorm(prox_R[:, 2])
    u_ref  = proj_on_plane(prox_z, e1)
    u_flt  = proj_on_plane(np.cross(e2, e1), e1)
    alpha = 0.0 if (np.linalg.norm(u_ref) < 1e-6 or np.linalg.norm(u_flt) < 1e-6) else signed_angle(u_ref, u_flt, e1)

    # gamma: rotation about e3 comparing distal ref to e1×e2
    dist_x = vnorm(dist_R[:, 0])
    w_ref  = proj_on_plane(dist_x, e3)
    w_flt  = proj_on_plane(np.cross(e1, e2), e3)
    gamma = 0.0 if (np.linalg.norm(w_ref) < 1e-6 or np.linalg.norm(w_flt) < 1e-6) else signed_angle(w_ref, w_flt, e3)

    return alpha, beta, gamma  # (about e1, e2, e3)

# ------------------ Smoothing helpers ------------------
from collections import defaultdict
def _exp_alpha(cutoff_hz, dt):
    if cutoff_hz <= 0:
        return 1.0
    tau = 1.0 / (2.0 * math.pi * float(cutoff_hz))
    return dt / (dt + tau)

class EMAFilter:
    def __init__(self, cutoff_hz):
        self.cutoff = float(cutoff_hz)
        self.y = None
    def reset(self): self.y = None
    def filt(self, x, dt):
        a = _exp_alpha(self.cutoff, dt)
        self.y = float(x) if self.y is None else a*float(x) + (1.0-a)*self.y
        return self.y

class OneEuro:
    def __init__(self, min_cutoff=1.0, beta=0.0, d_cutoff=1.0):
        self.min_cutoff = float(min_cutoff)
        self.beta       = float(beta)
        self.d_filt     = EMAFilter(d_cutoff)
        self.x_filt     = EMAFilter(min_cutoff)
        self.x_prev     = None
    def reset(self):
        self.d_filt.reset(); self.x_filt.reset(); self.x_prev = None
    def filt(self, x, dt):
        dx = 0.0 if self.x_prev is None else (x - self.x_prev) / max(dt, 1e-6)
        self.x_prev = x
        d_hat = self.d_filt.filt(dx, dt)
        cutoff = self.min_cutoff + self.beta * abs(d_hat)
        self.x_filt.cutoff = cutoff
        return self.x_filt.filt(x, dt)

class AngleSmoother:
    def __init__(self, method="one_euro"):
        self.method = method
        self.unwrap_base = {}
        self.last_out    = {}
        self.filters     = {}
    def _ensure_filter(self, key):
        if key not in self.filters:
            if self.method == "one_euro":
                self.filters[key] = OneEuro(ONEEURO_MIN_CUTOFF, ONEEURO_BETA, ONEEURO_D_CUTOFF)
            elif self.method == "ema":
                self.filters[key] = EMAFilter(EMA_CUTOFF_HZ)
            else:
                self.filters[key] = None
    def _unwrap(self, key, x):
        if key not in self.unwrap_base:
            self.unwrap_base[key] = float(x); return float(x)
        prev = self.unwrap_base[key]
        delta = x - prev
        delta = (delta + 180.0) % 360.0 - 180.0
        y = prev + delta
        self.unwrap_base[key] = y
        return y
    def process(self, key, x, dt):
        x = float(x)
        xu = self._unwrap(key, x)
        self._ensure_filter(key)
        if isinstance(self.filters[key], (OneEuro, EMAFilter)):
            xf = self.filters[key].filt(xu, dt)
        else:
            xf = xu
        y_prev = self.last_out.get(key, xf)
        if abs(xf - y_prev) < DEADBAND_DEG:
            xf = y_prev
        if SLEW_LIMIT_DEG_S > 0 and key in self.last_out:
            max_step = SLEW_LIMIT_DEG_S * dt
            diff = xf - self.last_out[key]
            if diff >  max_step: xf = self.last_out[key] + max_step
            if diff < -max_step: xf = self.last_out[key] - max_step
        self.last_out[key] = xf
        return xf

# ------------------ Angle extraction (ISB JCS) ------------------
mp_pose  = mp.solutions.pose
mp_hands = mp.solutions.hands
POSE = mp_pose.PoseLandmark
def to_arr(lm): return np.array([lm.x, lm.y, lm.z], np.float32)

def compute_angles_pose(lms):
    out = {}
    L = POSE
    # Landmarks
    hip_l, hip_r = to_arr(lms[L.LEFT_HIP]),       to_arr(lms[L.RIGHT_HIP])
    sh_l,  sh_r  = to_arr(lms[L.LEFT_SHOULDER]),  to_arr(lms[L.RIGHT_SHOULDER])
    el_l,  el_r  = to_arr(lms[L.LEFT_ELBOW]),     to_arr(lms[L.RIGHT_ELBOW])
    wr_l,  wr_r  = to_arr(lms[L.LEFT_WRIST]),     to_arr(lms[L.RIGHT_WRIST])
    nose         = to_arr(lms[L.NOSE])

    up_world = np.array([0,-1,0], np.float32)   # image up (screen -Y)

    # Segment frames (approx.)
    X_p, Y_p, Z_p = basis_from_lr(hip_l, hip_r, up_world)
    R_pelvis = np.stack([X_p, Y_p, Z_p], axis=1)

    X_t, Y_t, Z_t = basis_from_lr(sh_l, sh_r, up_world)
    R_thorax = np.stack([X_t, Y_t, Z_t], axis=1)

    thorax_c = 0.5*(sh_l + sh_r)
    neck_v = vnorm(nose - thorax_c)

    hum_l = vnorm(el_l - sh_l)     # humerus long axis (L)
    hum_r = vnorm(el_r - sh_r)     # humerus long axis (R)
    uln_l = vnorm(wr_l - el_l)     # forearm long axis (L)
    uln_r = vnorm(wr_r - el_r)     # forearm long axis (R)

    # ---------------- Pelvis ↔ Thorax --------------------------------------
    a,b,g = jcs_angles(R_pelvis, R_thorax, e1_prox=Y_p, e3_dist=Z_t)
    out["pelvis_yaw"]   = a
    out["pelvis_pitch"] = b
    out["pelvis_roll"]  = g

    # ---------------- Shoulder (Thorax ↔ Humerus) --------------------------
    # Map keys: abd ~ plane-of-elevation (alpha), flex ~ elevation (beta), er ~ axial rotation (gamma)
    # Left
    R_hum_tmpL = np.stack([hum_l, np.cross(Z_t, hum_l), Z_t], axis=1)
    aL, bL, gL = jcs_angles(R_thorax, R_hum_tmpL, e1_prox=Y_t, e3_dist=hum_l)
    out["l_sh_abd"]  = aL
    out["l_sh_flex"] = bL  # elevation — this will drive the UE abduction via mapping
    out["l_sh_er"]   = gL
    # Right
    R_hum_tmpR = np.stack([hum_r, np.cross(Z_t, hum_r), Z_t], axis=1)
    aR, bR, gR = jcs_angles(R_thorax, R_hum_tmpR, e1_prox=Y_t, e3_dist=hum_r)
    out["r_sh_abd"]  = aR
    out["r_sh_flex"] = bR
    out["r_sh_er"]   = gR

    # Elbows (placeholders if enabled)
    out["l_elb_flex"] = 0.0; out["l_elb_pro"]  = 0.0
    out["r_elb_flex"] = 0.0; out["r_elb_pro"]  = 0.0

    # Wrists placeholders
    out["l_w_add"]=0.0; out["l_w_flex"]=0.0; out["l_w_pro"]=0.0
    out["r_w_add"]=0.0; out["r_w_flex"]=0.0; out["r_w_pro"]=0.0

    # Neck approx
    R_neck_tmp = np.stack([neck_v, np.cross(Y_t, neck_v), Y_t], axis=1)
    a,b,g = jcs_angles(R_thorax, R_neck_tmp, e1_prox=Y_t, e3_dist=neck_v)
    out["neck_yaw"]=a; out["neck_pitch"]=b; out["neck_roll"]=g

    # Lower body placeholders
    zeros = ["l_hip_flex","l_thigh_abd","l_hip_er","l_knee_flex","l_foot_flex","l_foot_add","l_foot_pro","l_ball_flex",
             "r_hip_flex","r_thigh_abd","r_hip_er","r_knee_flex","r_foot_flex","r_foot_add","r_foot_pro","r_ball_flex"]
    for k in zeros: out.setdefault(k, 0.0)

    return out, (to_arr(lms[L.LEFT_SHOULDER]), to_arr(lms[L.LEFT_ELBOW]), to_arr(lms[L.LEFT_WRIST]),
                 to_arr(lms[L.RIGHT_SHOULDER]),to_arr(lms[L.RIGHT_ELBOW]),to_arr(lms[L.RIGHT_WRIST]))

# ------------------ (Optional) refine wrists with Hands ------------------
def compute_wrist_from_hands(hres, pose_points):
    return {}  # keep simple for now

# ------------------ Drawing (overlay) ------------------
JOINT_SPEC = mp.solutions.drawing_utils.DrawingSpec(color=(0,255,0), thickness=3, circle_radius=5)
BONE_SPEC  = mp.solutions.drawing_utils.DrawingSpec(color=(0,150,255), thickness=2, circle_radius=2)
C_BAR_TORSO = (30, 30, 230)
C_BAR_LARM  = (180, 60, 60)
C_BAR_RARM  = (60, 60, 180)
C_BAR_LLEG  = (60, 180, 60)
C_BAR_RLEG  = (60, 180, 160)

def to_px(pt, w, h): return int(pt.x * w), int(pt.y * h)

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

# ------------------ Shoulder mapping helpers ------------------
def load_calibration_flex_anchors(calib_path: str):
    """
    Returns per-side input anchors (elevation values) from your calibration JSON:
      { "L": [(flex_down, TARGET_ABD['down']),
              (flex_T, TARGET_ABD['t_pose']),
              (flex_up, TARGET_ABD['overhead'])],
        "R": [... same ...] }
    Falls back to defaults if file missing/invalid.
    """
    # Fallbacks if no calibration is supplied: typical human values
    fallback = {
        "L": [(-60.0, TARGET_ABD["down"]), (0.0, TARGET_ABD["t_pose"]), (90.0, TARGET_ABD["overhead"])],
        "R": [(-60.0, TARGET_ABD["down"]), (0.0, TARGET_ABD["t_pose"]), (90.0, TARGET_ABD["overhead"])],
    }
    if not calib_path or not os.path.exists(calib_path):
        print("ℹ️  No calibration file provided; using default elevation anchors.")
        return fallback
    try:
        with open(calib_path, "r") as f:
            data = json.load(f)
        poses = {p["label"]: p["angles"] for p in data.get("poses", []) if "label" in p and "angles" in p}
        def get_flex(side: str, label: str) -> float:
            ang = poses.get(label, {})
            key = f"{side}_sh_flex"
            return float(ang.get(key, 0.0))
        anchors = {
            "L": [
                (get_flex("l", "arms_down"), TARGET_ABD["down"]),
                (get_flex("l", "t_pose"),    TARGET_ABD["t_pose"]),
                (get_flex("l", "overhead"),  TARGET_ABD["overhead"]),
            ],
            "R": [
                (get_flex("r", "arms_down"), TARGET_ABD["down"]),
                (get_flex("r", "t_pose"),    TARGET_ABD["t_pose"]),
                (get_flex("r", "overhead"),  TARGET_ABD["overhead"]),
            ],
        }
        anchors["L"] = sorted(anchors["L"], key=lambda t: t[0])
        anchors["R"] = sorted(anchors["R"], key=lambda t: t[0])
        print("✅ Loaded calibration anchors from:", calib_path)
        print("   L anchors:", anchors["L"])
        print("   R anchors:", anchors["R"])
        return anchors
    except Exception as e:
        print(f"⚠️  Could not parse calibration file ({calib_path}): {e}\nUsing defaults.")
        return fallback

def _piecewise_linear(x, pts):
    """pts = [(x0,y0), (x1,y1), (x2,y2)] with x increasing. Linear interp + extrapolate ends."""
    pts = sorted(pts, key=lambda t: t[0])
    if len(pts) < 2:
        return pts[0][1] if pts else 0.0
    if x <= pts[0][0]:
        x0,y0 = pts[0]; x1,y1 = pts[1]
        t = (x - x0) / max(1e-6, (x1 - x0)); return y0 + t*(y1 - y0)
    if x >= pts[-1][0]:
        xn,yn = pts[-2]; xN,yN = pts[-1]
        t = (x - xN) / max(1e-6, (xN - xn)); return yN + t*(yN - yn)
    for i in range(len(pts)-1):
        x0,y0 = pts[i]; x1,y1 = pts[i+1]
        if x0 <= x <= x1:
            t = (x - x0) / max(1e-6, (x1 - x0))
            return y0 + t*(y1 - y0)
    return pts[-1][1]

def apply_logical_shoulder_map(angles: Dict[str,float], anchors):
    """
    Convert JCS elevation (l_sh_flex / r_sh_flex) into UE abduction using
    per-side, calibration-driven piecewise maps. Optionally hold flex/ER at 0.
    """
    # LEFT
    if "l_sh_flex" in angles:
        elevL = float(angles["l_sh_flex"])
        angles["l_sh_abd"] = float(np.clip(_piecewise_linear(elevL, anchors["L"]), ABD_MIN_DEG, ABD_MAX_DEG))
        if HOLD_FLEX_AT_ZERO: angles["l_sh_flex"] = 0.0
        if HOLD_ER_AT_ZERO:   angles["l_sh_er"]   = 0.0
    # RIGHT
    if "r_sh_flex" in angles:
        elevR = float(angles["r_sh_flex"])
        angles["r_sh_abd"] = float(np.clip(_piecewise_linear(elevR, anchors["R"]), ABD_MIN_DEG, ABD_MAX_DEG))
        if HOLD_FLEX_AT_ZERO: angles["r_sh_flex"] = 0.0
        if HOLD_ER_AT_ZERO:   angles["r_sh_er"]   = 0.0
    return angles

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
    ap = argparse.ArgumentParser(description="Pose(+Hands) → Unreal OSC + on-screen overlay (JCS + calibrated shoulder mapping)")
    ap.add_argument("--cam", type=int, default=0, help="Camera index (0=Sony, 1=iPhone)")
    ap.add_argument("--width", type=int, default=None, help="Force width (else profile default)")
    ap.add_argument("--height", type=int, default=None, help="Force height (else profile default)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=9000)
    ap.add_argument("--fps-cap", type=int, default=30)
    ap.add_argument("--mirror", action="store_true", help="Mirror preview horizontally")
    ap.add_argument("--axis-json", default=DEFAULT_MAPPING_PATH, help="Path to auto_axis_mapping.json")
    ap.add_argument("--calib", default="", help="Path to calibration JSON (arms_down, t_pose, overhead)")
    args = ap.parse_args()

    # Build enabled group map from toggles
    group_toggles = {
        "pelvis": SEND_PELVIS,
        "thorax": SEND_THORAX,
        "neck":   SEND_NECK,
        "shoulders_l": SEND_SHOULDERS_L,
        "shoulders_r": SEND_SHOULDERS_R,
        "elbows_l":    SEND_ELBOWS_L,
        "elbows_r":    SEND_ELBOWS_R,
        "wrists_l":    SEND_WRISTS_L,
        "wrists_r":    SEND_WRISTS_R,
        "leg_l":       SEND_LEG_L,
        "leg_r":       SEND_LEG_R,
        "fingers_l":   SEND_FINGERS_L,
        "fingers_r":   SEND_FINGERS_R,
    }

    # Build OSC mapping from JSON and filter by toggles
    global mapping_path
    mapping_path = args.axis_json
    ADDR, KEY_GROUPS = build_addr_from_json(args.axis_json, group_toggles)

    # Load calibration → per-side LUT anchors
    anchors = load_calibration_flex_anchors(args.calib)

    # OSC
    osc = SimpleUDPClient(args.host, args.port)
    def osc_send(addr, val): osc.send_message(addr, float(val))

    # Smoother
    smoother = AngleSmoother(method=SMOOTH_METHOD)

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

            now = time.time()
            dt  = now - t_prev
            t_prev = now

            if pres.pose_landmarks:
                lms = pres.pose_landmarks.landmark
                angles, pose_points = compute_angles_pose(lms)

                # (Optional) refine wrists
                angles.update(compute_wrist_from_hands(hres, pose_points))

                # >>> Calibration-driven shoulder mapping (elevation → abduction) <<<
                angles = apply_logical_shoulder_map(angles, anchors)

                # Smooth + send only enabled channels
                for key, (addr, sgn) in ADDR.items():
                    val = float(angles.get(key, 0.0))
                    if SMOOTH_ENABLED:
                        val = smoother.process(key, val, max(dt, 1e-4))
                    osc_send(addr, sgn * val)
            else:
                # keep rig stable: only for enabled channels
                for key,(addr,sgn) in ADDR.items():
                    val = 0.0
                    if SMOOTH_ENABLED:
                        val = smoother.process(key, val, max(dt, 1e-4))
                    osc_send(addr, val)

            # overlay
            if pres.pose_landmarks:
                draw_pose_with_bars(frame, pres.pose_landmarks)
                cv2.putText(frame, "POSE: OK", (12,30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,220,0), 2)

                if SHOW_SH_DEBUG:
                    lx = int(12)
                    ly = int(60)
                    lflex = angles.get("l_sh_flex", 0.0)
                    labd  = angles.get("l_sh_abd",  0.0)
                    rflex = angles.get("r_sh_flex", 0.0)
                    rabd  = angles.get("r_sh_abd",  0.0)
                    cv2.putText(frame, f"L elev:{lflex:6.1f} → abd:{labd:6.1f}",
                                (lx, ly), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 1); ly += 22
                    cv2.putText(frame, f"R elev:{rflex:6.1f} → abd:{rabd:6.1f}",
                                (lx, ly), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 1)
            else:
                cv2.putText(frame, "POSE: not detected (step back / add light)",
                            (12,30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,255), 2)

            # FPS overlay
            fps = 1.0 / max(1e-6, time.time() - t_prev)
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

if __name__ == "__main__":
    main()