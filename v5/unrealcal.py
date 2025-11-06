#!/usr/bin/env python3
# pose_to_unreal_shoulders_calibrated_inverted.py
# Camera → MediaPipe Pose → ISB JCS → Calibrated → Sign-corrected → Unreal via OSC
# Abduction → Yaw, Flexion → Pitch, ER → Roll (MetaHuman convention)
# Inverted signs so that forward = forward, side = outward.

import os, time, math, argparse
import numpy as np
import cv2
from absl import logging as absl_logging
absl_logging.set_verbosity(absl_logging.ERROR)
import mediapipe as mp
from pythonosc.udp_client import SimpleUDPClient

# ------------------ CALIBRATION MAPS ------------------
CAL = {
    "l_abd":  {"a":  1.17106, "b": -157.1923, "min": -170.0, "max": 170.0},
    "r_abd":  {"a": -1.16820, "b": -159.2014, "min": -170.0, "max": 170.0},
    "l_flex": {"a":  1.04838, "b":   79.3609, "min":  -20.0, "max": 170.0},
    "r_flex": {"a":  1.08917, "b":   85.8435, "min":  -20.0, "max": 170.0},
}

FREEZE_ER = True

# ------------------ OSC CHANNELS (MetaHuman axes) ------------------
CHAN = {
    "l_flex": "/bone/upperarm_l/pitch",
    "l_abd":  "/bone/upperarm_l/yaw",
    "l_er":   "/bone/upperarm_l/roll",
    "r_flex": "/bone/upperarm_r/pitch",
    "r_abd":  "/bone/upperarm_r/yaw",
    "r_er":   "/bone/upperarm_r/roll",
}

# ------------------ SMOOTHING ------------------
EMA_CUTOFF_HZ     = 3.0
DEADBAND_DEG      = 0.2
SLEW_LIMIT_DEG_S  = 360.0

def _exp_alpha(cutoff_hz, dt):
    if cutoff_hz <= 0: return 1.0
    tau = 1.0 / (2.0 * math.pi * float(cutoff_hz))
    return dt / (dt + tau)

class EMA:
    def __init__(self, cutoff): self.cutoff = float(cutoff); self.y = None
    def filt(self, x, dt):
        a = _exp_alpha(self.cutoff, dt)
        self.y = float(x) if self.y is None else a*float(x)+(1.0-a)*self.y
        return self.y

class AngleSmoother:
    def __init__(self, keys):
        self.filters = {k: EMA(EMA_CUTOFF_HZ) for k in keys}
        self.last = {k: 0.0 for k in keys}
    def step(self, key, x, dt):
        y = self.filters[key].filt(x, dt)
        if abs(y - self.last[key]) < DEADBAND_DEG:
            y = self.last[key]
        max_step = SLEW_LIMIT_DEG_S * dt
        d = y - self.last[key]
        if d >  max_step: y = self.last[key] + max_step
        if d < -max_step: y = self.last[key] - max_step
        self.last[key] = y
        return y

# ------------------ ISB JCS math ------------------
mp_pose = mp.solutions.pose
POSE = mp_pose.PoseLandmark

def arr(lm): return np.array([lm.x, lm.y, lm.z], np.float32)
def vnorm(v): v = np.asarray(v, np.float32); n=np.linalg.norm(v); return v/(n+1e-8)

def basis_from_lr(left, right, up_hint):
    x = vnorm(right-left)
    z = vnorm(np.cross(x, up_hint))
    y = vnorm(np.cross(z, x))
    return x, y, z

def signed_angle(a,b,n):
    a=vnorm(a); b=vnorm(b); n=vnorm(n)
    return math.degrees(math.atan2(np.dot(np.cross(a,b),n), np.dot(a,b)))

def proj_on_plane(v,n): n=vnorm(n); return vnorm(v - np.dot(v,n)*n)

def jcs_angles(prox_R, dist_R, e1_prox, e3_dist):
    e1=vnorm(e1_prox); e3=vnorm(e3_dist)
    e2=vnorm(np.cross(e3,e1))
    e3p = proj_on_plane(e3,e1)
    beta  = signed_angle(e3p,e3,e2)
    prox_z=vnorm(prox_R[:,2])
    u_ref=proj_on_plane(prox_z,e1)
    u_flt=proj_on_plane(np.cross(e2,e1),e1)
    alpha=signed_angle(u_ref,u_flt,e1)
    dist_x=vnorm(dist_R[:,0])
    w_ref=proj_on_plane(dist_x,e3)
    w_flt=proj_on_plane(np.cross(e1,e2),e3)
    gamma=signed_angle(w_ref,w_flt,e3)
    return alpha,beta,gamma

def compute_shoulder_isb(lms):
    L=POSE; up=np.array([0,-1,0],np.float32)
    sh_l,sh_r=arr(lms[L.LEFT_SHOULDER]),arr(lms[L.RIGHT_SHOULDER])
    el_l,el_r=arr(lms[L.LEFT_ELBOW]),arr(lms[L.RIGHT_ELBOW])
    X_t,Y_t,Z_t=basis_from_lr(sh_l,sh_r,up)
    R_t=np.stack([X_t,Y_t,Z_t],axis=1)
    hum_l=vnorm(el_l-sh_l); hum_r=vnorm(el_r-sh_r)
    R_hL=np.stack([hum_l,np.cross(Z_t,hum_l),Z_t],axis=1)
    R_hR=np.stack([hum_r,np.cross(Z_t,hum_r),Z_t],axis=1)
    aL,bL,gL=jcs_angles(R_t,R_hL,Y_t,hum_l)
    aR,bR,gR=jcs_angles(R_t,R_hR,Y_t,hum_r)
    return {"l_abd":aL,"l_flex":bL,"l_er":gL,"r_abd":aR,"r_flex":bR,"r_er":gR}

# ------------------ CAMERA + OVERLAY ------------------
def open_camera(index, width, height):
    cap = cv2.VideoCapture(index, cv2.CAP_AVFOUNDATION)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width or 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height or 720)
    ok,_=cap.read()
    if not ok: raise SystemExit("❌ Camera failed.")
    print(f"✅ Camera ready {int(cap.get(3))}x{int(cap.get(4))}")
    return cap

mp_draw = mp.solutions.drawing_utils
def draw_pose(frame, landmarks):
    mp_draw.draw_landmarks(
        frame, landmarks, mp_pose.POSE_CONNECTIONS,
        mp_draw.DrawingSpec(color=(0,255,0), thickness=2, circle_radius=3),
        mp_draw.DrawingSpec(color=(0,150,255), thickness=2, circle_radius=1)
    )

# ------------------ MAIN ------------------
def main():
    ap = argparse.ArgumentParser(description="Pose→UE shoulders with inverted signs")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=9000)
    ap.add_argument("--cam", type=int, default=0)
    ap.add_argument("--mirror", action="store_true")
    ap.add_argument("--fps-cap", type=int, default=30)
    args = ap.parse_args()

    osc = SimpleUDPClient(args.host, args.port)
    smoother = AngleSmoother(list(CHAN.keys()))
    cap = open_camera(args.cam, None, None)
    pose = mp_pose.Pose(static_image_mode=False, model_complexity=2,
                        min_detection_confidence=0.3, min_tracking_confidence=0.3)
    win="Pose→UE (inverted)"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)

    t_prev=time.time()
    while True:
        ok,frame=cap.read()
        if not ok: break
        if args.mirror: frame=cv2.flip(frame,1)
        rgb=frame[:,:,::-1]
        res=pose.process(rgb)
        dt=max(1e-4,time.time()-t_prev); t_prev=time.time()

        if res.pose_landmarks:
            draw_pose(frame,res.pose_landmarks)
            raw=compute_shoulder_isb(res.pose_landmarks.landmark)
            # calibration
            l_abd=CAL["l_abd"]["a"]*raw["l_abd"]+CAL["l_abd"]["b"]
            r_abd=CAL["r_abd"]["a"]*raw["r_abd"]+CAL["r_abd"]["b"]
            l_flex=CAL["l_flex"]["a"]*raw["l_flex"]+CAL["l_flex"]["b"]
            r_flex=CAL["r_flex"]["a"]*raw["r_flex"]+CAL["r_flex"]["b"]
            # invert signs
            l_abd, r_abd = -l_abd, -r_abd
            l_flex, r_flex = -l_flex, -r_flex
            # freeze ER
            l_er=r_er=0.0
            # smooth
            for k,v in {"l_abd":l_abd,"r_abd":r_abd,"l_flex":l_flex,"r_flex":r_flex,"l_er":l_er,"r_er":r_er}.items():
                val=smoother.step(k,v,dt)
                osc.send_message(CHAN[k],float(val))
            cv2.putText(frame,"POSE OK",(10,30),cv2.FONT_HERSHEY_SIMPLEX,0.8,(0,255,0),2)
        else:
            cv2.putText(frame,"NO POSE",(10,30),cv2.FONT_HERSHEY_SIMPLEX,0.8,(0,0,255),2)

        cv2.imshow(win,frame)
        if cv2.waitKey(max(1,int(1000/args.fps_cap))) & 0xFF in (27,ord('q')): break

    cap.release(); pose.close(); cv2.destroyAllWindows()

if __name__=="__main__":
    main()