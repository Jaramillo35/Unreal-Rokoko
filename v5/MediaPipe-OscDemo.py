#!/usr/bin/env python3
# shoulder_coronal_visualizer.py
# Live camera → MediaPipe Pose(+Hands) → Full body overlay with fingers → Only send shoulder coronal movement to Unreal

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
    1: {"name": "iPhone (Cont.)",  "width": 4032, "height": 3024},
}
BACKEND = cv2.CAP_AVFOUNDATION

# ------------------ OSC mapping (only shoulders) ------------------
ADDR = {
    # Shoulders - only coronal (abduction) will be sent
    "l_sh_abd": ("/bone/upperarm_l/pitch", +1),
    "r_sh_abd": ("/bone/upperarm_r/pitch", +1),
    # These will be zeroed
    "l_sh_flex": ("/bone/upperarm_l/yaw",   +1),
    "l_sh_er":   ("/bone/upperarm_l/roll",  +1),
    "r_sh_flex": ("/bone/upperarm_r/yaw",   +1),
    "r_sh_er":   ("/bone/upperarm_r/roll",  +1),
}

# Add all other addresses (zeroed out) to keep Unreal stable
ADDR.update({
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
    # Legs
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
    x = vnorm(right - left)
    z = vnorm(np.cross(x, up_hint))
    y = vnorm(np.cross(z, x))
    return x, y, z

# ------------------ Angle extraction ------------------
mp_pose  = mp.solutions.pose
mp_hands = mp.solutions.hands
POSE = mp_pose.PoseLandmark
HANDS = mp_hands.HandLandmark

def to_arr(lm): 
    return np.array([lm.x, lm.y, lm.z], np.float32)

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

    # Pelvis
    out["pelvis_pitch"] = signed_angle_in_plane(Y_p, X_p, up_world)
    out["pelvis_roll"]  = signed_angle_in_plane(Y_p, Z_p, up_world)
    out["pelvis_yaw"]   = signed_angle_in_plane(X_p, up_world, cam_x)

    # Thorax
    out["thorax_pitch"] = signed_angle_in_plane(Y_t, X_t, up_world)
    out["thorax_roll"]  = signed_angle_in_plane(Y_t, Z_t, up_world)
    out["thorax_yaw"]   = signed_angle_in_plane(X_t, up_world, cam_x)

    # Neck
    neck_v = vnorm(nose - thorax_c)
    out["neck_pitch"] = signed_angle_in_plane(neck_v, X_t, up_world)
    out["neck_roll"]  = signed_angle_in_plane(neck_v, Z_t, up_world)
    out["neck_yaw"]   = signed_angle_in_plane(neck_v, up_world, X_t)

    # Arms - shoulders
    upper_l = vnorm(el_l - sh_l)
    upper_r = vnorm(el_r - sh_r)
    fore_l  = vnorm(wr_l - el_l)
    fore_r  = vnorm(wr_r - el_r)

    out["l_sh_flex"] = signed_angle_in_plane(upper_l, Z_t, Y_t)   # sagittal
    out["l_sh_abd"]  = signed_angle_in_plane(upper_l, X_t, Y_t)   # coronal
    out["l_sh_er"]   = signed_angle_in_plane(fore_l, upper_l, Y_t)  # twist

    out["r_sh_flex"] = signed_angle_in_plane(upper_r, Z_t, Y_t)
    out["r_sh_abd"]  = signed_angle_in_plane(upper_r, -X_t, Y_t)
    out["r_sh_er"]   = signed_angle_in_plane(fore_r, upper_r, Y_t)

    # Elbow flexion
    out["l_elb_flex"] = 180.0 - angle_between(upper_l, fore_l)
    out["r_elb_flex"] = 180.0 - angle_between(upper_r, fore_r)

    # Placeholders
    out["l_elb_pro"] = 0.0
    out["r_elb_pro"] = 0.0
    out["l_w_flex"] = out["l_w_add"] = out["l_w_pro"] = 0.0
    out["r_w_flex"] = out["r_w_add"] = out["r_w_pro"] = 0.0
    
    return out, (sh_l, el_l, wr_l, sh_r, el_r, wr_r)

# ------------------ Smoothing Configuration ------------------
SMOOTH_ENABLED = True
SMOOTH_METHOD = "ema"  # "ema" | "one_euro" | "none"

# EMA (Exponential Moving Average) settings
EMA_CUTOFF_HZ = 3.0  # Lower = smoother but more lag

# One Euro filter settings (alternative)
ONEEURO_MIN_CUTOFF = 1.4
ONEEURO_BETA = 0.03
ONEEURO_D_CUTOFF = 1.0

# Post-filters
DEADBAND_DEG = 0.5      # Ignore changes smaller than this (degrees)
SLEW_LIMIT_DEG_S = 180.0  # Maximum change per second (degrees/sec)

# ------------------ Smoothing Classes ------------------
class EMAFilter:
    """Exponential Moving Average filter"""
    def __init__(self, cutoff_hz):
        self.cutoff = float(cutoff_hz)
        self.y = None
    def _exp_alpha(self, cutoff_hz, dt):
        if cutoff_hz <= 0:
            return 1.0
        tau = 1.0 / (2.0 * math.pi * float(cutoff_hz))
        return dt / (dt + tau)
    def filt(self, x, dt):
        a = self._exp_alpha(self.cutoff, dt)
        self.y = float(x) if self.y is None else a * float(x) + (1.0 - a) * self.y
        return self.y
    def reset(self):
        self.y = None

class OneEuro:
    """One Euro filter - adaptive smoothing based on velocity"""
    def __init__(self, min_cutoff=1.0, beta=0.0, d_cutoff=1.0):
        self.min_cutoff = float(min_cutoff)
        self.beta = float(beta)
        self.d_filt = EMAFilter(d_cutoff)
        self.x_filt = EMAFilter(min_cutoff)
        self.x_prev = None
    def reset(self):
        self.d_filt.reset()
        self.x_filt.reset()
        self.x_prev = None
    def filt(self, x, dt):
        dx = 0.0 if self.x_prev is None else (x - self.x_prev) / max(dt, 1e-6)
        self.x_prev = x
        d_hat = self.d_filt.filt(dx, dt)
        cutoff = self.min_cutoff + self.beta * abs(d_hat)
        self.x_filt.cutoff = cutoff
        return self.x_filt.filt(x, dt)

class AngleSmoother:
    """Smooth angle values with unwrapping, deadband, and slew limiting"""
    def __init__(self, method="ema"):
        self.method = method
        self.unwrap_base = {}
        self.last_out = {}
        self.filters = {}
    
    def _ensure_filter(self, key):
        if key not in self.filters:
            if self.method == "one_euro":
                self.filters[key] = OneEuro(ONEEURO_MIN_CUTOFF, ONEEURO_BETA, ONEEURO_D_CUTOFF)
            elif self.method == "ema":
                self.filters[key] = EMAFilter(EMA_CUTOFF_HZ)
            else:
                self.filters[key] = None
    
    def _unwrap(self, key, x):
        """Unwrap angle to handle 360° wraparound"""
        if key not in self.unwrap_base:
            self.unwrap_base[key] = float(x)
            return float(x)
        prev = self.unwrap_base[key]
        delta = x - prev
        # Normalize delta to [-180, 180]
        delta = (delta + 180.0) % 360.0 - 180.0
        y = prev + delta
        self.unwrap_base[key] = y
        return y
    
    def process(self, key, x, dt):
        """Process a new angle value through smoothing pipeline"""
        x = float(x)
        # Unwrap angle to handle wraparound
        xu = self._unwrap(key, x)
        # Ensure filter exists
        self._ensure_filter(key)
        # Apply smoothing filter
        if isinstance(self.filters[key], (OneEuro, EMAFilter)):
            xf = self.filters[key].filt(xu, dt)
        else:
            xf = xu
        # Deadband: ignore tiny changes
        y_prev = self.last_out.get(key, xf)
        if abs(xf - y_prev) < DEADBAND_DEG:
            xf = y_prev
        # Slew rate limiting: cap maximum change per frame
        if SLEW_LIMIT_DEG_S > 0 and key in self.last_out:
            max_step = SLEW_LIMIT_DEG_S * dt
            diff = xf - self.last_out[key]
            if diff > max_step:
                xf = self.last_out[key] + max_step
            if diff < -max_step:
                xf = self.last_out[key] - max_step
        self.last_out[key] = xf
        return xf

# ------------------ Calibration Mapping ------------------
# Valid abduction angle limits for Unreal
ABD_MIN_DEG = -150.0  # Arms overhead (next to ears)
ABD_MAX_DEG = 30.0    # Arms down (next to legs)

def calibrate_abduction_angle(raw_abd_deg, side="L"):
    """
    Map MediaPipe computed abduction to Unreal expected values.
    Based on user calibration:
    - MediaPipe 150° → Unreal -60° (T-pose)
    - MediaPipe -170° → Unreal 30° (arms down)
    - MediaPipe 0° → Unreal -150° (arms overhead)
    
    Left and right arms may have different MediaPipe angle ranges due to
    coordinate system differences, so separate calibration is supported.
    
    Returns values clamped to [ABD_MIN_DEG, ABD_MAX_DEG] = [-150°, 30°]
    """
    # Calibration points: (MediaPipe_computed_angle, Unreal_expected_angle)
    # Format: (MP_input_angle, UE_output_angle)
    
    # Right arm calibration (default)
    calibration_points = [
        (-170.0, 30.0),    # MP -170° → send 30° (arms down)
        (0.0, -150.0),     # MP 0° → send -150° (arms overhead)
        (150.0, -60.0),    # MP 150° → send -60° (T-pose)
    ]
    
    # Sort by input angle (ascending)
    calibration_points.sort(key=lambda x: x[0])
    
    # Clamp/extrapolate input
    x = float(raw_abd_deg)
    
    # Left arm may need different calibration due to coordinate system
    # MediaPipe left arm uses X_t while right uses -X_t, so angles may be inverted
    if side == "L":
        # Invert left arm MediaPipe angle to match right arm coordinate system
        x = -x
    if x <= calibration_points[0][0]:
        # Below minimum: extrapolate linearly
        if len(calibration_points) >= 2:
            x0, y0 = calibration_points[0]
            x1, y1 = calibration_points[1]
            slope = (y1 - y0) / (x1 - x0) if (x1 - x0) != 0 else 0.0
            result = y0 + slope * (x - x0)
            return float(np.clip(result, ABD_MIN_DEG, ABD_MAX_DEG))
        return float(np.clip(calibration_points[0][1], ABD_MIN_DEG, ABD_MAX_DEG))
    
    if x >= calibration_points[-1][0]:
        # Above maximum: extrapolate linearly
        if len(calibration_points) >= 2:
            x0, y0 = calibration_points[-2]
            x1, y1 = calibration_points[-1]
            slope = (y1 - y0) / (x1 - x0) if (x1 - x0) != 0 else 0.0
            result = y1 + slope * (x - x1)
            return float(np.clip(result, ABD_MIN_DEG, ABD_MAX_DEG))
        return float(np.clip(calibration_points[-1][1], ABD_MIN_DEG, ABD_MAX_DEG))
    
    # Linear interpolation between calibration points
    for i in range(len(calibration_points) - 1):
        x0, y0 = calibration_points[i]
        x1, y1 = calibration_points[i + 1]
        if x0 <= x <= x1:
            t = (x - x0) / (x1 - x0) if (x1 - x0) != 0 else 0.0
            result = y0 + t * (y1 - y0)
            # Clamp to valid range before returning
            return float(np.clip(result, ABD_MIN_DEG, ABD_MAX_DEG))
    
    # Fallback: clamp raw value
    return float(np.clip(raw_abd_deg, ABD_MIN_DEG, ABD_MAX_DEG))

# ------------------ Enhanced Drawing ------------------
# Colors for different body parts
COLOR_HEAD = (255, 200, 100)
COLOR_TORSO = (30, 30, 230)
COLOR_LARM = (180, 60, 60)
COLOR_RARM = (60, 60, 180)
COLOR_LLEG = (60, 180, 60)
COLOR_RLEG = (60, 180, 160)
COLOR_HAND = (255, 150, 0)
COLOR_FINGER = (255, 200, 150)

# Drawing specs
JOINT_SPEC = mp.solutions.drawing_utils.DrawingSpec(color=(0, 255, 0), thickness=3, circle_radius=5)
BONE_SPEC = mp.solutions.drawing_utils.DrawingSpec(color=(0, 150, 255), thickness=2, circle_radius=2)
HAND_JOINT_SPEC = mp.solutions.drawing_utils.DrawingSpec(color=COLOR_HAND, thickness=2, circle_radius=3)
HAND_BONE_SPEC = mp.solutions.drawing_utils.DrawingSpec(color=COLOR_FINGER, thickness=2, circle_radius=1)

def to_px(pt, w, h):
    return int(pt.x * w), int(pt.y * h)

def draw_segment_thick(img, p1, p2, color, thickness=12):
    cv2.line(img, p1, p2, color, thickness=thickness)

def draw_comprehensive_body_overlay(frame, pose_landmarks, hand_landmarks_list):
    """Draw complete body overlay with all segments and fingers"""
    mp_draw = mp.solutions.drawing_utils
    h, w = frame.shape[:2]
    
    if pose_landmarks:
        lm = pose_landmarks.landmark
        L = POSE
        
        # Draw MediaPipe pose skeleton (all connections)
        mp_draw.draw_landmarks(
            frame, pose_landmarks, mp_pose.POSE_CONNECTIONS,
            landmark_drawing_spec=JOINT_SPEC,
            connection_drawing_spec=BONE_SPEC
        )
        
        # Draw thick segments for major body parts
        # Torso
        hip_l = to_px(lm[L.LEFT_HIP], w, h)
        hip_r = to_px(lm[L.RIGHT_HIP], w, h)
        sh_l = to_px(lm[L.LEFT_SHOULDER], w, h)
        sh_r = to_px(lm[L.RIGHT_SHOULDER], w, h)
        draw_segment_thick(frame, hip_l, hip_r, COLOR_TORSO, 14)
        draw_segment_thick(frame, sh_l, sh_r, COLOR_TORSO, 14)
        draw_segment_thick(frame, hip_l, sh_l, COLOR_TORSO, 12)
        draw_segment_thick(frame, hip_r, sh_r, COLOR_TORSO, 12)
        
        # Head/Neck
        nose = to_px(lm[L.NOSE], w, h)
        thorax_center = ((sh_l[0] + sh_r[0]) // 2, (sh_l[1] + sh_r[1]) // 2)
        draw_segment_thick(frame, thorax_center, nose, COLOR_HEAD, 10)
        cv2.circle(frame, nose, 8, COLOR_HEAD, -1)
        
        # Left arm
        el_l = to_px(lm[L.LEFT_ELBOW], w, h)
        wr_l = to_px(lm[L.LEFT_WRIST], w, h)
        draw_segment_thick(frame, sh_l, el_l, COLOR_LARM, 12)
        draw_segment_thick(frame, el_l, wr_l, COLOR_LARM, 10)
        
        # Right arm
        el_r = to_px(lm[L.RIGHT_ELBOW], w, h)
        wr_r = to_px(lm[L.RIGHT_WRIST], w, h)
        draw_segment_thick(frame, sh_r, el_r, COLOR_RARM, 12)
        draw_segment_thick(frame, el_r, wr_r, COLOR_RARM, 10)
        
        # Left leg
        kn_l = to_px(lm[L.LEFT_KNEE], w, h)
        an_l = to_px(lm[L.LEFT_ANKLE], w, h)
        draw_segment_thick(frame, hip_l, kn_l, COLOR_LLEG, 12)
        draw_segment_thick(frame, kn_l, an_l, COLOR_LLEG, 10)
        
        # Right leg
        kn_r = to_px(lm[L.RIGHT_KNEE], w, h)
        an_r = to_px(lm[L.RIGHT_ANKLE], w, h)
        draw_segment_thick(frame, hip_r, kn_r, COLOR_RLEG, 12)
        draw_segment_thick(frame, kn_r, an_r, COLOR_RLEG, 10)
    
    # Draw hands with fingers
    if hand_landmarks_list:
        for hand_landmarks in hand_landmarks_list:
            # Draw MediaPipe hand skeleton (includes all finger connections)
            mp_draw.draw_landmarks(
                frame, hand_landmarks, mp_hands.HAND_CONNECTIONS,
                landmark_drawing_spec=HAND_JOINT_SPEC,
                connection_drawing_spec=HAND_BONE_SPEC
            )
            
            # Draw thick palm segments
            h_lm = hand_landmarks.landmark
            H = HANDS
            palm_points = [
                to_px(h_lm[H.WRIST], w, h),
                to_px(h_lm[H.THUMB_CMC], w, h),
                to_px(h_lm[H.INDEX_FINGER_MCP], w, h),
                to_px(h_lm[H.MIDDLE_FINGER_MCP], w, h),
                to_px(h_lm[H.RING_FINGER_MCP], w, h),
                to_px(h_lm[H.PINKY_MCP], w, h),
            ]
            for i in range(len(palm_points) - 1):
                cv2.line(frame, palm_points[i], palm_points[i+1], COLOR_HAND, 4)
            cv2.line(frame, palm_points[0], palm_points[-1], COLOR_HAND, 4)

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
    got_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    got_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"✅ Camera {index} ({prof['name']}): requested {req_w}x{req_h}, got ~{got_w}x{got_h}")
    return cap

# ------------------ Main ------------------
def main():
    ap = argparse.ArgumentParser(description="Full body overlay with fingers → Only shoulder coronal movement to Unreal")
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
    pose = mp_pose.Pose(static_image_mode=False, model_complexity=2,
                        min_detection_confidence=0.3, min_tracking_confidence=0.3)
    hands = mp_hands.Hands(static_image_mode=False, max_num_hands=2, model_complexity=1,
                           min_detection_confidence=0.3, min_tracking_confidence=0.3)

    # Camera + window
    cap = open_camera(args.cam, args.width, args.height)
    win = f"Shoulder Coronal Only (cam {args.cam}) — press q/ESC to quit"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)

    # Initialize smoother
    smoother = AngleSmoother(method=SMOOTH_METHOD)

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

            # Calculate delta time for smoothing
            now = time.time()
            dt = max(now - t_prev, 1e-4)  # Minimum dt to avoid division by zero
            t_prev = now

            # Compute angles & send OSC
            l_abd_smooth = 0.0
            r_abd_smooth = 0.0
            if pres.pose_landmarks:
                lms = pres.pose_landmarks.landmark
                angles, pose_points = compute_angles_pose(lms)
                
                # Only send shoulder coronal movement (abduction) with calibration and smoothing
                coronal_shoulder_keys = ("l_sh_abd", "r_sh_abd")
                for key, (addr, sgn) in ADDR.items():
                    if key in coronal_shoulder_keys:
                        raw_abd = float(angles.get(key, 0.0))
                        # Apply calibration mapping
                        calibrated_abd = calibrate_abduction_angle(raw_abd, "L" if "l_" in key else "R")
                        # Apply smoothing to reduce jitter and harsh movements
                        if SMOOTH_ENABLED:
                            smoothed_abd = smoother.process(key, calibrated_abd, dt)
                        else:
                            smoothed_abd = calibrated_abd
                        # Store smoothed values for display
                        if key == "l_sh_abd":
                            l_abd_smooth = smoothed_abd
                        elif key == "r_sh_abd":
                            r_abd_smooth = smoothed_abd
                        osc_send(addr, sgn * smoothed_abd)
                    else:
                        osc_send(addr, 0.0)
            else:
                # Keep rig stable
                coronal_shoulder_keys = ("l_sh_abd", "r_sh_abd")
                for key, (addr, sgn) in ADDR.items():
                    val = 0.0
                    if SMOOTH_ENABLED and key in coronal_shoulder_keys:
                        val = smoother.process(key, 0.0, dt)
                        if key == "l_sh_abd":
                            l_abd_smooth = val
                        elif key == "r_sh_abd":
                            r_abd_smooth = val
                    osc_send(addr, val)

            # Draw comprehensive overlay
            hand_landmarks_list = []
            if hres and hres.multi_hand_landmarks:
                hand_landmarks_list = hres.multi_hand_landmarks
            
            draw_comprehensive_body_overlay(frame, pres.pose_landmarks, hand_landmarks_list)

            # Status overlay
            if pres.pose_landmarks:
                angles, _ = compute_angles_pose(pres.pose_landmarks.landmark)
                l_abd_raw = angles.get("l_sh_abd", 0.0)
                r_abd_raw = angles.get("r_sh_abd", 0.0)
                cv2.putText(frame, "POSE: OK | Shoulder Coronal Only (Smoothed)", (12, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 220, 0), 2)
                cv2.putText(frame, f"L Abd: {l_abd_smooth:6.1f}° (raw: {l_abd_raw:6.1f}°)", (12, 60),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                cv2.putText(frame, f"R Abd: {r_abd_smooth:6.1f}° (raw: {r_abd_raw:6.1f}°)", (12, 85),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            else:
                cv2.putText(frame, "POSE: not detected (step back / add light)",
                           (12, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

            # FPS overlay
            fps = 1.0 / max(1e-6, dt)
            cv2.putText(frame, f"FPS {fps:4.1f}", (12, frame.shape[0] - 12),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

            cv2.imshow(win, frame)
            if cv2.waitKey(max(1, int(1000/args.fps_cap))) & 0xFF in (27, ord('q')):
                break

    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        pose.close()
        hands.close()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()

