#!/usr/bin/env python3
"""
MetaHuman Streamer v3
Natural Language Processing + Bone-level Streaming
Uses v2 as base with NLP text input for commands
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import queue
import time
import json
import numpy as np
import torch
import torch.nn as nn
from pythonosc import udp_client
import os
import sys
import re
import math
import pandas as pd
from sklearn.cluster import KMeans
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# Configuration
OSC_HOST = "127.0.0.1"
OSC_PORT = 9000
FPS = 30
OUT_FRAMES = 60

class MovementGRU(nn.Module):
    """GRU model for generating movement sequences"""
    def __init__(self, input_size, hidden_size=128, output_size=None):
        super().__init__()
        if output_size is None:
            output_size = input_size
        self.hidden_size = hidden_size
        self.gru = nn.GRU(input_size, hidden_size, batch_first=True, num_layers=2)
        self.output_layer = nn.Linear(hidden_size, output_size)
        self.dropout = nn.Dropout(0.2)
        
    def forward(self, x):
        # x shape: (batch, seq_len, input_dim)
        gru_out, _ = self.gru(x)
        gru_out = self.dropout(gru_out)
        output = self.output_layer(gru_out)
        return output

class NLPCommandParser:
    """Natural Language Processing for steering commands"""
    
    def __init__(self):
        # Define command patterns and synonyms
        self.commands = {
            'turn_left': {
                'patterns': [
                    r'\b(turn|steer|go)\s+(left|l)\b',
                    r'\b(left|l)\s+(turn|steer)\b',
                    r'\bturn\s+to\s+the\s+left\b',
                    r'\bsteer\s+left\b',
                    r'\bgo\s+left\b'
                ],
                'action': 'TURN_LEFT'
            },
            'turn_right': {
                'patterns': [
                    r'\b(turn|steer|go)\s+(right|r)\b',
                    r'\b(right|r)\s+(turn|steer)\b',
                    r'\bturn\s+to\s+the\s+right\b',
                    r'\bsteer\s+right\b',
                    r'\bgo\s+right\b'
                ],
                'action': 'TURN_RIGHT'
            },
            'basic_position': {
                'patterns': [
                    r'\b(basic|baseline|default|normal|center|straight|neutral)\s+(position|pose|posture)\b',
                    r'\breturn\s+to\s+(basic|baseline|default|normal|center|straight|neutral)\b',
                    r'\b(basic|baseline|default|normal|center|straight|neutral)\b',
                    r'\bstraighten\s+up\b',
                    r'\bcenter\s+position\b'
                ],
                'action': 'BASELINE'
            },
            'stop': {
                'patterns': [
                    r'\b(stop|halt|pause|end|quit|exit)\b',
                    r'\bstop\s+(turning|steering|moving)\b'
                ],
                'action': 'STOP'
            },
            'sit': {
                'patterns': [
                    r'\b(sit|sit\s+down|make\s+it\s+sit|sitting\s+position|baseline\s+sitting|assume\s+seated|go\s+to\s+sitting)\b'
                ],
                'action': 'POSE_SITTING'
            }
        }
        
        # Compile regex patterns for efficiency
        self.compiled_patterns = {}
        for cmd_name, cmd_data in self.commands.items():
            self.compiled_patterns[cmd_name] = [
                re.compile(pattern, re.IGNORECASE) for pattern in cmd_data['patterns']
            ]
    
    def parse_command(self, text: str) -> Tuple[str, str, float]:
        """
        Parse natural language command
        Returns: (action, original_text, confidence)
        """
        if not text or not text.strip():
            return 'UNKNOWN', text, 0.0
        
        text = text.strip().lower()
        
        # Try to match each command type
        for cmd_name, cmd_data in self.commands.items():
            for pattern in self.compiled_patterns[cmd_name]:
                if pattern.search(text):
                    action = cmd_data['action']
                    confidence = 1.0  # Simple binary matching for now
                    return action, text, confidence
        
        return 'UNKNOWN', text, 0.0

class MetaHumanStreamerV3:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("MetaHuman Streamer v3 - NLP + Bone Streaming")
        self.root.geometry("800x700")
        
        # OSC configuration
        self.osc_host = OSC_HOST
        self.osc_port = OSC_PORT
        self.osc_client = None
        
        # Data storage
        self.baseline_vector = None
        self.baseline_model = None
        self.left_turn_model = None
        self.right_turn_model = None
        self.feature_names = None
        self.normalization_params = None
        
        # OSC channel configuration
        self.channels = []
        self.channel_mapping = {}  # Maps source columns to feature indices
        
        # Streaming state
        self.is_streaming = False
        self.current_mode = "BASELINE"  # BASELINE, TURNING_LEFT, TURNING_RIGHT
        self.stream_thread = None
        self.stop_event = threading.Event()
        
        # Data mode
        self.data_mode = "REAL"  # REAL or MOCK
        
        # Baseline sitting pose
        self.baseline_sitting_pose = None
        
        # Column to OSC bone mapping
        self.COLUMN_TO_OSC = {
            # Pelvis
            "Pelvis_extension": ("pelvis", "pitch"),
            "Pelvis_lateral_flexion_rotation": ("pelvis", "roll"),
            "Pelvis_axial_rotation": ("pelvis", "yaw"),

            # Thorax/Spine
            "Thorax_extension": ("spine_01", "pitch"),
            "Thorax_lateral_flexion_rotation": ("spine_01", "roll"),
            "Thorax_axial_rotation": ("spine_01", "yaw"),

            # Neck
            "Neck_flexion": ("neck_01", "pitch"),
            "Neck_left-ward_tilt": ("neck_01", "roll"),
            "Neck_right-ward_rotation": ("neck_01", "yaw"),

            # Left Leg
            "LeftHip_flexion": ("thigh_l", "pitch"),
            "LeftHip_adduction": ("thigh_l", "roll"),
            "LeftHip_external_rotation": ("thigh_l", "yaw"),
            "LeftKnee_flexion": ("calf_l", "pitch"),
            "LeftKnee_adduction": ("calf_l", "roll"),
            "LeftKnee_external_rotation": ("calf_l", "yaw"),
            "LeftAnkle_dorsiflexion": ("foot_l", "pitch"),
            "LeftAnkle_inversion": ("foot_l", "roll"),
            "LeftAnkle_internal_rotation": ("foot_l", "yaw"),

            # Right Leg
            "RightHip_flexion": ("thigh_r", "pitch"),
            "RightHip_adduction": ("thigh_r", "roll"),
            "RightHip_external_rotation": ("thigh_r", "yaw"),
            "RightKnee_flexion": ("calf_r", "pitch"),
            "RightKnee_adduction": ("calf_r", "roll"),
            "RightKnee_external_rotation": ("calf_r", "yaw"),
            "RightAnkle_dorsiflexion": ("foot_r", "pitch"),
            "RightAnkle_inversion": ("foot_r", "roll"),
            "RightAnkle_internal_rotation": ("foot_r", "yaw"),

            # Left Arm
            "LeftShoulder_flexion": ("clavicle_l", "pitch"),
            "LeftShoulder_abduction": ("clavicle_l", "roll"),
            "LeftShoulder_external_rotation": ("clavicle_l", "yaw"),
            "LeftElbow_flexion": ("lowerarm_l", "pitch"),
            "LeftElbow_abduction": ("lowerarm_l", "roll"),
            "LeftElbow_pronation": ("lowerarm_l", "yaw"),
            "LeftWrist_flexion": ("hand_l", "pitch"),
            "LeftWrist_adduction": ("hand_l", "roll"),
            "LeftWrist_pronation": ("hand_l", "yaw"),

            # Right Arm
            "RightShoulder_flexion": ("clavicle_r", "pitch"),
            "RightShoulder_abduction": ("clavicle_r", "roll"),
            "RightShoulder_external_rotation": ("clavicle_r", "yaw"),
            "RightElbow_flexion": ("lowerarm_r", "pitch"),
            "RightElbow_abduction": ("lowerarm_r", "roll"),
            "RightElbow_pronation": ("lowerarm_r", "yaw"),
            "RightWrist_flexion": ("hand_r", "pitch"),
            "RightWrist_adduction": ("hand_r", "roll"),
            "RightWrist_pronation": ("hand_r", "yaw"),
        }
        
        # NLP Parser
        self.nlp_parser = NLPCommandParser()
        
        # Logging and stats
        self.osc_send_count = 0
        self.osc_error_count = 0
        self.last_send_time = 0
        self.show_data = True  # Toggle for showing data in log
        
        # Movement data
        self.baseline_sequence = None
        self.left_turn_sequence = None
        self.right_turn_sequence = None
        
        # GUI setup
        self.setup_gui()
        
        # Load models and data
        self.load_models_and_data()
        
        # Load channel configuration
        self.load_channel_config()
        
        # Load baseline sitting pose
        self.load_baseline_sitting_pose()
        
    def setup_gui(self):
        """Setup the GUI interface with NLP text input"""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Title
        title_label = ttk.Label(main_frame, text="MetaHuman Streamer v3 - NLP + Bone Streaming", 
                               font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # Status frame
        status_frame = ttk.LabelFrame(main_frame, text="Status", padding="10")
        status_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.status_label = ttk.Label(status_frame, text="Ready", font=("Arial", 12))
        self.status_label.grid(row=0, column=0)
        
        # Connection info
        self.conn_label = ttk.Label(status_frame, text=f"OSC: {self.osc_host}:{self.osc_port}")
        self.conn_label.grid(row=1, column=0, pady=(5, 0))
        
        # NLP Command Input Frame
        nlp_frame = ttk.LabelFrame(main_frame, text="Natural Language Commands", padding="10")
        nlp_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Command input
        ttk.Label(nlp_frame, text="Enter command:", font=("Arial", 10, "bold")).grid(row=0, column=0, sticky=tk.W)
        
        self.command_var = tk.StringVar()
        self.command_entry = ttk.Entry(nlp_frame, textvariable=self.command_var, width=50, font=("Arial", 11))
        self.command_entry.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(5, 0))
        self.command_entry.bind('<Return>', self.process_command)
        
        # Send command button
        self.send_button = ttk.Button(nlp_frame, text="Send Command", command=self.process_command)
        self.send_button.grid(row=1, column=2, padx=(10, 0), pady=(5, 0))
        
        # Example commands
        examples_frame = ttk.Frame(nlp_frame)
        examples_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(10, 0))
        
        ttk.Label(examples_frame, text="Examples:", font=("Arial", 9, "bold")).grid(row=0, column=0, sticky=tk.W)
        
        examples_text = "• 'turn left' or 'steer left' • 'turn right' or 'steer right' • 'basic position' or 'return to baseline' • 'sit' or 'sit down' • 'stop'"
        ttk.Label(examples_frame, text=examples_text, font=("Arial", 9), foreground="gray").grid(row=1, column=0, sticky=tk.W)
        
        # Control frame
        control_frame = ttk.LabelFrame(main_frame, text="Controls", padding="10")
        control_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Start/Stop streaming
        self.stream_button = ttk.Button(control_frame, text="Start Streaming", 
                                       command=self.toggle_streaming)
        self.stream_button.grid(row=0, column=0, padx=(0, 10))
        
        # Quick action buttons
        quick_frame = ttk.Frame(control_frame)
        quick_frame.grid(row=1, column=0, pady=(10, 0))
        
        self.left_button = ttk.Button(quick_frame, text="Turn Left", 
                                     command=lambda: self.process_text_command("turn left"), state="disabled")
        self.left_button.grid(row=0, column=0, padx=(0, 10))
        
        self.right_button = ttk.Button(quick_frame, text="Turn Right", 
                                      command=lambda: self.process_text_command("turn right"), state="disabled")
        self.right_button.grid(row=0, column=1, padx=(0, 10))
        
        self.baseline_button = ttk.Button(quick_frame, text="Basic Position", 
                                         command=lambda: self.process_text_command("basic position"), state="disabled")
        self.baseline_button.grid(row=0, column=2)
        
        self.sit_button = ttk.Button(quick_frame, text="Sit", 
                                   command=lambda: self.process_text_command("sit"), state="disabled")
        self.sit_button.grid(row=0, column=3, padx=(10, 0))
        
        # Data mode buttons
        data_mode_frame = ttk.Frame(control_frame)
        data_mode_frame.grid(row=2, column=0, pady=(10, 0))
        
        ttk.Label(data_mode_frame, text="Data Mode:", font=("Arial", 10, "bold")).grid(row=0, column=0, sticky=tk.W)
        
        self.real_data_button = ttk.Button(data_mode_frame, text="Real Data (ML Models)", 
                                          command=self.set_real_data_mode, state="disabled")
        self.real_data_button.grid(row=0, column=1, padx=(10, 5))
        
        self.mock_data_button = ttk.Button(data_mode_frame, text="Mock Data (Directional)", 
                                          command=self.set_mock_data_mode, state="disabled")
        self.mock_data_button.grid(row=0, column=2, padx=(5, 0))
        
        # Data mode status
        self.data_mode_label = ttk.Label(data_mode_frame, text="Mode: REAL", font=("Arial", 9))
        self.data_mode_label.grid(row=1, column=0, columnspan=3, pady=(5, 0))
        
        # Settings frame
        settings_frame = ttk.LabelFrame(main_frame, text="Settings", padding="10")
        settings_frame.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # OSC Configuration
        osc_frame = ttk.Frame(settings_frame)
        osc_frame.grid(row=0, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(osc_frame, text="OSC Configuration:", font=("Arial", 10, "bold")).grid(row=0, column=0, sticky=tk.W)
        
        # Host
        ttk.Label(osc_frame, text="Host:").grid(row=1, column=0, sticky=tk.W, pady=(5, 0))
        self.host_var = tk.StringVar(value=self.osc_host)
        host_entry = ttk.Entry(osc_frame, textvariable=self.host_var, width=15)
        host_entry.grid(row=1, column=1, padx=(10, 0), pady=(5, 0))
        
        # Port
        ttk.Label(osc_frame, text="Port:").grid(row=1, column=2, sticky=tk.W, padx=(20, 0), pady=(5, 0))
        self.port_var = tk.StringVar(value=str(self.osc_port))
        port_entry = ttk.Entry(osc_frame, textvariable=self.port_var, width=10)
        port_entry.grid(row=1, column=3, padx=(10, 0), pady=(5, 0))
        
        # Apply OSC settings button
        self.apply_osc_button = ttk.Button(osc_frame, text="Apply OSC Settings", 
                                          command=self.apply_osc_settings)
        self.apply_osc_button.grid(row=1, column=4, padx=(20, 0), pady=(5, 0))
        
        # Separator
        ttk.Separator(settings_frame, orient='horizontal').grid(row=1, column=0, columnspan=4, 
                                                               sticky=(tk.W, tk.E), pady=(10, 10))
        
        # Turn duration
        ttk.Label(settings_frame, text="Turn Duration (seconds):").grid(row=2, column=0, sticky=tk.W)
        self.duration_var = tk.StringVar(value="2.0")
        duration_entry = ttk.Entry(settings_frame, textvariable=self.duration_var, width=10)
        duration_entry.grid(row=2, column=1, padx=(10, 0))
        
        # FPS
        ttk.Label(settings_frame, text="FPS:").grid(row=3, column=0, sticky=tk.W, pady=(5, 0))
        self.fps_var = tk.StringVar(value=str(FPS))
        fps_entry = ttk.Entry(settings_frame, textvariable=self.fps_var, width=10)
        fps_entry.grid(row=3, column=1, padx=(10, 0), pady=(5, 0))
        
        # Log console
        log_frame = ttk.LabelFrame(main_frame, text="Log Console", padding="5")
        log_frame.grid(row=5, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(5, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=12, width=80, 
                                                 state=tk.DISABLED, wrap=tk.WORD)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Log controls
        log_controls = ttk.Frame(log_frame)
        log_controls.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(5, 0))
        
        self.show_data_var = tk.BooleanVar(value=True)
        show_data_check = ttk.Checkbutton(log_controls, text="Show data values", 
                                         variable=self.show_data_var,
                                         command=self.toggle_data_display)
        show_data_check.grid(row=0, column=0, sticky=tk.W)
        
        clear_log_btn = ttk.Button(log_controls, text="Clear Log", command=self.clear_log)
        clear_log_btn.grid(row=0, column=1, padx=(10, 0))
        
        # Stats frame
        stats_frame = ttk.Frame(main_frame)
        stats_frame.grid(row=6, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        stats_frame.columnconfigure(1, weight=1)
        
        # OSC stats
        self.osc_stats_var = tk.StringVar(value="Messages: 0 | Errors: 0")
        self.osc_stats_label = ttk.Label(stats_frame, textvariable=self.osc_stats_var, 
                                        font=('Arial', 9))
        self.osc_stats_label.grid(row=0, column=0, sticky=tk.W)
        
        # Info frame
        info_frame = ttk.LabelFrame(main_frame, text="v3 Features", padding="10")
        info_frame.grid(row=7, column=0, columnspan=3, sticky=(tk.W, tk.E))
        
        info_text = """v3 Features:
• Natural Language Processing for commands
• Text input: 'turn left', 'steer right', 'basic position', 'sit'
• Two data modes: Real (ML models) or Mock (directional signals)
• Real mode: 37 bone channels with ML models
• Mock mode: /mh/LeftForeArm_roll (left turns), /mh/RightForeArm_roll (right turns)
• Sitting pose: /cmd/pose with baseline pose values
• Quick action buttons for common commands
• Real-time command parsing and execution"""
        
        info_label = ttk.Label(info_frame, text=info_text, justify=tk.LEFT)
        info_label.grid(row=0, column=0, sticky=tk.W)
        
    def process_command(self, event=None):
        """Process the command from text input"""
        command_text = self.command_var.get().strip()
        if not command_text:
            return
        
        self.process_text_command(command_text)
        self.command_var.set("")  # Clear input after processing
    
    def process_text_command(self, command_text: str):
        """Process a text command using NLP"""
        action, original_text, confidence = self.nlp_parser.parse_command(command_text)
        
        self.log_message(f"Command: '{original_text}' → Action: {action} (confidence: {confidence:.2f})")
        
        if action == 'TURN_LEFT':
            self.start_left_turn()
        elif action == 'TURN_RIGHT':
            self.start_right_turn()
        elif action == 'BASELINE':
            self.return_to_baseline()
        elif action == 'POSE_SITTING':
            self.trigger_sitting_pose()
        elif action == 'STOP':
            self.stop_streaming()
        else:
            self.log_message(f"Unknown command: '{original_text}'. Try: 'turn left', 'turn right', 'basic position', 'sit', or 'stop'")
    
    def set_real_data_mode(self):
        """Switch to real data mode (ML models)"""
        self.data_mode = "REAL"
        self.data_mode_label.config(text="Mode: REAL (ML Models)")
        self.log_message("Switched to REAL data mode - using ML models")
        print("Switched to REAL data mode")
    
    def set_mock_data_mode(self):
        """Switch to mock data mode (2 signals only)"""
        self.data_mode = "MOCK"
        self.data_mode_label.config(text="Mode: MOCK (Directional)")
        self.log_message("Switched to MOCK data mode - sending /mh/LeftForeArm_roll for left turns, /mh/RightForeArm_roll for right turns")
        print("Switched to MOCK data mode")
    
    def load_baseline_sitting_pose(self):
        """Load baseline sitting pose from CSV file"""
        try:
            csv_path = "../data/Baseline_SittingPose_Selected.csv"
            
            if not os.path.exists(csv_path):
                self.log_message(f"Baseline sitting pose CSV not found: {csv_path}")
                return False
            
            # Load CSV data
            df = pd.read_csv(csv_path)
            self.log_message(f"Loaded baseline sitting pose CSV: {df.shape}")
            
            # Select only numeric columns
            numeric_columns = df.select_dtypes(include=[np.number]).columns
            numeric_data = df[numeric_columns]
            
            # Compute mean per column to get baseline pose vector
            self.baseline_sitting_pose = numeric_data.mean().to_dict()
            
            self.log_message(f"Computed baseline sitting pose vector: {len(self.baseline_sitting_pose)} values")
            self.log_message(f"Pose vector range: {min(self.baseline_sitting_pose.values()):.3f} to {max(self.baseline_sitting_pose.values()):.3f}")
            
            return True
            
        except Exception as e:
            self.log_message(f"Error loading baseline sitting pose: {e}")
            return False
    
    def trigger_sitting_pose(self):
        """Trigger sitting pose by sending baseline pose to Unreal"""
        if self.baseline_sitting_pose is None:
            self.log_message("Baseline sitting pose not loaded")
            return
        
        if self.osc_client is None:
            self.log_message("OSC client not available")
            return
        
        try:
            # Optional: Send pose command for blending
            self.osc_client.send_message("/cmd/pose", ["sitting", 0.35])
            self.log_message("Sent pose command: sitting with 0.35s blend")
            
            # Send per-bone, per-axis messages
            messages_sent = 0
            for column_name, value in self.baseline_sitting_pose.items():
                if column_name in self.COLUMN_TO_OSC:
                    bone_name, axis = self.COLUMN_TO_OSC[column_name]
                    osc_address = f"/bone/{bone_name}/{axis}"
                    
                    self.osc_client.send_message(osc_address, float(value))
                    messages_sent += 1
            
            self.log_message(f"Sent sitting pose: {messages_sent} bone messages")
            self.log_message(f"Pose range: {min(self.baseline_sitting_pose.values()):.3f} to {max(self.baseline_sitting_pose.values()):.3f}")
            
        except Exception as e:
            self.log_message(f"Error sending sitting pose: {e}")
    
    def load_models_and_data(self):
        """Load the trained models and data (same as v2)"""
        try:
            data_dir = "../v2"  # Data files are in v2 directory (relative to v3/)
            
            # Load normalization parameters
            with open(os.path.join(data_dir, "normalization_params.json"), 'r') as f:
                self.normalization_params = json.load(f)
            
            # Load baseline vector
            self.baseline_vector = np.load(os.path.join(data_dir, "baseline_vector.npy"))
            
            # Load feature names
            feature_file = "../v1/columns.txt"  # Try v1 directory first
            if not os.path.exists(feature_file):
                feature_file = "../v2/columns.txt"  # Try v2 directory
            if not os.path.exists(feature_file):
                feature_file = "../data/processed/columns.txt"  # Fallback to data/processed
                
            if os.path.exists(feature_file):
                with open(feature_file, 'r') as f:
                    self.feature_names = [line.strip() for line in f.readlines()]
            else:
                self.feature_names = [f"feature_{i}" for i in range(len(self.baseline_vector))]
            
            # Load models
            input_size = len(self.baseline_vector)
            
            # Baseline model
            self.baseline_model = MovementGRU(input_size, hidden_size=128)
            self.baseline_model.load_state_dict(torch.load(os.path.join(data_dir, "baseline_gru.pth")))
            self.baseline_model.eval()
            
            # Left turn model
            self.left_turn_model = MovementGRU(input_size, hidden_size=128)
            self.left_turn_model.load_state_dict(torch.load(os.path.join(data_dir, "left_turn_gru.pth")))
            self.left_turn_model.eval()
            
            # Right turn model
            self.right_turn_model = MovementGRU(input_size, hidden_size=128)
            self.right_turn_model.load_state_dict(torch.load(os.path.join(data_dir, "right_turn_gru.pth")))
            self.right_turn_model.eval()
            
            # Generate baseline sequence
            self.generate_baseline_sequence()
            
            self.status_label.config(text="Models loaded successfully")
            self.log_message("v3 Models and data loaded successfully")
            print("v3 Models and data loaded successfully")
            
            # Initialize OSC client
            self.update_osc_client()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load models: {str(e)}")
            self.status_label.config(text="Error loading models")
            print(f"Error loading models: {e}")
    
    def load_channel_config(self):
        """Load OSC channel configuration for Unreal Engine (same as v2)"""
        try:
            config_path = "../v2/osc_channels_config.json"
            
            if not os.path.exists(config_path):
                self.log_message(f"OSC channel config not found: {config_path}")
                return False
                
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # Load channels
            self.channels = []
            for channel in config['channels']:
                self.channels.append({
                    'source_column': channel['source_column'],
                    'osc_address': channel['osc_address'],
                    'transform': channel['transform']
                })
            
            # Create mapping from source columns to feature indices
            self.channel_mapping = {}
            for channel in self.channels:
                source_column = channel['source_column']
                
                if self.feature_names:
                    try:
                        feature_idx = self.feature_names.index(source_column)
                        self.channel_mapping[source_column] = feature_idx
                    except ValueError:
                        self.log_message(f"Warning: Feature {source_column} not found in data")
            
            self.log_message(f"Loaded {len(self.channels)} OSC channels from {config_path}")
            self.log_message(f"Mapped {len(self.channel_mapping)} channels to features")
            return True
            
        except Exception as e:
            self.log_message(f"Error loading OSC channel config: {e}")
            return False
    
    def generate_baseline_sequence(self):
        """Generate a baseline sequence for continuous streaming (same as v2)"""
        with torch.no_grad():
            # Load baseline data and use it directly
            baseline_data = np.load("../v2/baseline_data.npy")
            # Use the first sample as our baseline sequence
            self.baseline_sequence = baseline_data[0]  # Shape: (60, 864)
            print(f"Loaded baseline sequence: {self.baseline_sequence.shape}")
    
    def generate_turn_sequence(self, model, duration_seconds):
        """Generate a turn sequence using the specified model (same as v2)"""
        with torch.no_grad():
            # Load the appropriate turn data
            if model == self.left_turn_model:
                turn_data = np.load("../v2/left_turn_data.npy")
            else:
                turn_data = np.load("../v2/right_turn_data.npy")
            
            # Use the first sample as our turn sequence
            sequence = turn_data[0]  # Shape: (60, 864)
            return sequence
    
    def update_osc_client(self):
        """Update OSC client with current host and port settings (same as v2)"""
        try:
            self.osc_host = self.host_var.get()
            self.osc_port = int(self.port_var.get())
            self.osc_client = udp_client.SimpleUDPClient(self.osc_host, self.osc_port)
            self.conn_label.config(text=f"OSC: {self.osc_host}:{self.osc_port}")
            self.log_message(f"OSC client connected to {self.osc_host}:{self.osc_port}")
            print(f"OSC client updated: {self.osc_host}:{self.osc_port}")
        except ValueError:
            messagebox.showerror("Error", "Invalid port number. Please enter a valid integer.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update OSC client: {str(e)}")
    
    def apply_osc_settings(self):
        """Apply OSC settings and update connection (same as v2)"""
        if self.is_streaming:
            messagebox.showwarning("Warning", "Cannot change OSC settings while streaming. Please stop streaming first.")
            return
        
        self.update_osc_client()
        if self.osc_client:
            messagebox.showinfo("Success", f"OSC settings updated to {self.osc_host}:{self.osc_port}")
            self.log_message(f"OSC settings updated to {self.osc_host}:{self.osc_port}")
    
    def log_message(self, message):
        """Add message to log console (same as v2)"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        log_entry = f"[{timestamp}] {message}\n"
        
        def update_log():
            self.log_text.config(state=tk.NORMAL)
            self.log_text.insert(tk.END, log_entry)
            self.log_text.see(tk.END)
            self.log_text.config(state=tk.DISABLED)
        
        # Update from main thread
        self.root.after(0, update_log)
    
    def toggle_data_display(self):
        """Toggle data display in log (same as v2)"""
        self.show_data = self.show_data_var.get()
        self.log_message(f"Data display {'enabled' if self.show_data else 'disabled'}")
    
    def clear_log(self):
        """Clear the log console (same as v2)"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.log_message("Log cleared")
    
    def update_osc_stats(self):
        """Update OSC statistics display (same as v2)"""
        self.osc_stats_var.set(f"Messages: {self.osc_send_count} | Errors: {self.osc_error_count}")
    
    def start_left_turn(self):
        """Start left turn movement (same as v2)"""
        if not self.is_streaming:
            self.log_message("Please start streaming first")
            return
            
        self.current_mode = "TURNING_LEFT"
        duration = float(self.duration_var.get())
        
        # Generate left turn sequence
        self.left_turn_sequence = self.generate_turn_sequence(self.left_turn_model, duration)
        
        self.status_label.config(text="Turning Left...")
        self.log_message("Started left turn movement")
        print("Started left turn")
    
    def start_right_turn(self):
        """Start right turn movement (same as v2)"""
        if not self.is_streaming:
            self.log_message("Please start streaming first")
            return
            
        self.current_mode = "TURNING_RIGHT"
        duration = float(self.duration_var.get())
        
        # Generate right turn sequence
        self.right_turn_sequence = self.generate_turn_sequence(self.right_turn_model, duration)
        
        self.status_label.config(text="Turning Right...")
        self.log_message("Started right turn movement")
        print("Started right turn")
    
    def return_to_baseline(self):
        """Return to baseline movement (same as v2)"""
        if not self.is_streaming:
            self.log_message("Please start streaming first")
            return
            
        self.current_mode = "BASELINE"
        self.status_label.config(text="Streaming Baseline...")
        self.log_message("Returned to basic position (baseline)")
        print("Returned to baseline")
    
    def toggle_streaming(self):
        """Start or stop streaming (same as v2)"""
        if not self.is_streaming:
            self.start_streaming()
        else:
            self.stop_streaming()
    
    def start_streaming(self):
        """Start the streaming process (same as v2)"""
        if self.baseline_sequence is None:
            messagebox.showerror("Error", "Baseline sequence not available")
            return
        
        if self.osc_client is None:
            messagebox.showerror("Error", "OSC client not initialized. Please check your OSC settings.")
            return
        
        self.is_streaming = True
        self.stop_event.clear()
        
        # Update GUI
        self.stream_button.config(text="Stop Streaming")
        self.left_button.config(state="normal")
        self.right_button.config(state="normal")
        self.baseline_button.config(state="normal")
        self.sit_button.config(state="normal")
        self.real_data_button.config(state="normal")
        self.mock_data_button.config(state="normal")
        
        # Start streaming thread
        self.stream_thread = threading.Thread(target=self.stream_worker)
        self.stream_thread.daemon = True
        self.stream_thread.start()
        
        self.status_label.config(text="Streaming Baseline...")
        self.log_message("Started streaming baseline")
        print("Started streaming")
    
    def stop_streaming(self):
        """Stop the streaming process (same as v2)"""
        self.is_streaming = False
        self.stop_event.set()
        
        # Update GUI
        self.stream_button.config(text="Start Streaming")
        self.left_button.config(state="disabled")
        self.right_button.config(state="disabled")
        self.baseline_button.config(state="disabled")
        self.sit_button.config(state="disabled")
        self.real_data_button.config(state="disabled")
        self.mock_data_button.config(state="disabled")
        
        self.status_label.config(text="Stopped")
        self.log_message("Stopped streaming")
        print("Stopped streaming")
    
    def stream_worker(self):
        """Background worker for streaming data"""
        frame_duration = 1.0 / int(self.fps_var.get())
        frame_count = 0
        
        while not self.stop_event.is_set():
            start_time = time.time()
            
            if self.data_mode == "MOCK":
                # Mock data mode - send only 2 signals
                self.stream_mock_frame(frame_count)
            else:
                # Real data mode - use ML models
                # Get current sequence based on mode
                if self.current_mode == "TURNING_LEFT" and self.left_turn_sequence is not None:
                    sequence = self.left_turn_sequence
                elif self.current_mode == "TURNING_RIGHT" and self.right_turn_sequence is not None:
                    sequence = self.right_turn_sequence
                else:
                    sequence = self.baseline_sequence
                
                # Stream current frame
                if sequence is not None:
                    frame_idx = frame_count % len(sequence)
                    self.stream_frame(sequence[frame_idx], frame_count)
            
            frame_count += 1
            
            # Maintain FPS
            elapsed = time.time() - start_time
            sleep_time = max(0, frame_duration - elapsed)
            time.sleep(sleep_time)
    
    def stream_frame(self, frame_data, frame_count):
        """Stream a single frame of data via OSC using proper Unreal format (same as v2)"""
        try:
            if self.osc_client is None:
                self.log_message("OSC client not available")
                return
                
            if not self.channels:
                self.log_message("No channels configured")
                return
                
            # Denormalize the data
            denormalized_data = self.denormalize_data(frame_data)
            
            # Send data to configured OSC channels
            success_count = 0
            sample_values = []
            
            for channel in self.channels:
                source_column = channel['source_column']
                osc_address = channel['osc_address']
                transform = channel['transform']
                
                # Get the feature value for this channel
                if source_column in self.channel_mapping:
                    feature_idx = self.channel_mapping[source_column]
                    if feature_idx < len(denormalized_data):
                        # Get raw value from data
                        raw_value = denormalized_data[feature_idx]
                        
                        # Apply transform: scale * value + offset
                        transformed_value = transform['scale'] * raw_value + transform['offset']
                        
                        # Apply clamping if specified
                        if transform['clamp'] is not None:
                            clamp_min, clamp_max = transform['clamp']
                            transformed_value = max(clamp_min, min(clamp_max, transformed_value))
                        
                        try:
                            # Send OSC message with proper address format
                            self.osc_client.send_message(osc_address, float(transformed_value))
                            success_count += 1
                            sample_values.append(f"{transformed_value:.3f}")
                        except Exception as e:
                            self.osc_error_count += 1
                            self.log_message(f"OSC send error for {osc_address}: {e}")
                else:
                    # Send zero if feature not found
                    try:
                        self.osc_client.send_message(osc_address, 0.0)
                        success_count += 1
                    except Exception as e:
                        self.osc_error_count += 1
                        self.log_message(f"OSC send error for {osc_address}: {e}")
            
            # Send frame info (optional control messages)
            try:
                self.osc_client.send_message("/mh/frame", frame_count)
                self.osc_client.send_message("/mh/mode", self.current_mode)
                success_count += 2
            except Exception as e:
                self.osc_error_count += 1
                self.log_message(f"OSC send error for control messages: {e}")
            
            # Update stats
            self.osc_send_count += success_count
            self.last_send_time = time.time()
            
            # Update stats display
            self.root.after(0, self.update_osc_stats)
            
            # Log data if enabled (every 10th frame to avoid spam)
            if self.show_data and frame_count % 10 == 0:
                self.log_message(f"Frame {frame_count} ({self.current_mode}): {', '.join(sample_values[:5])}...")
            
        except Exception as e:
            self.osc_error_count += 1
            self.log_message(f"Error streaming frame: {e}")
            print(f"Error streaming frame: {e}")
    
    def stream_mock_frame(self, frame_count):
        """Stream mock data - only LeftForeArm_roll and RightForeArm_roll"""
        try:
            if self.osc_client is None:
                self.log_message("OSC client not available")
                return
            
            # Generate animated mock values based on current mode and frame
            time_factor = frame_count * 0.1  # Slow animation
            
            # Send different signals based on mode
            if self.current_mode == "TURNING_LEFT":
                # Left turn: send LeftForeArm_roll
                value = 30.0 + 20.0 * math.sin(time_factor)  # 10-50 degrees
                mock_signals = [("/mh/LeftForeArm_roll", value)]
            elif self.current_mode == "TURNING_RIGHT":
                # Right turn: send RightForeArm_roll
                value = 30.0 + 20.0 * math.sin(time_factor)  # 10-50 degrees
                mock_signals = [("/mh/RightForeArm_roll", value)]
            else:
                # Baseline: send LeftForeArm_roll with neutral movement
                value = 5.0 * math.sin(time_factor * 0.5)  # -5 to +5 degrees
                mock_signals = [("/mh/LeftForeArm_roll", value)]
            
            success_count = 0
            for osc_address, value in mock_signals:
                try:
                    self.osc_client.send_message(osc_address, float(value))
                    success_count += 1
                except Exception as e:
                    self.osc_error_count += 1
                    self.log_message(f"OSC send error for {osc_address}: {e}")
            
            # Send frame info
            try:
                self.osc_client.send_message("/mh/frame", frame_count)
                self.osc_client.send_message("/mh/mode", f"{self.current_mode}_MOCK")
                success_count += 2
            except Exception as e:
                self.osc_error_count += 1
                self.log_message(f"OSC send error for control messages: {e}")
            
            # Update stats
            self.osc_send_count += success_count
            self.last_send_time = time.time()
            
            # Update stats display
            self.root.after(0, self.update_osc_stats)
            
            # Log data if enabled (every 30th frame to avoid spam)
            if self.show_data and frame_count % 30 == 0:
                signal_name = mock_signals[0][0].split('/')[-1]  # Get signal name
                self.log_message(f"Mock Frame {frame_count} ({self.current_mode}): {signal_name}={value:.1f}°")
            
        except Exception as e:
            self.osc_error_count += 1
            self.log_message(f"Error streaming mock frame: {e}")
            print(f"Error streaming mock frame: {e}")
    
    def denormalize_data(self, normalized_data):
        """Denormalize data using the stored parameters (same as v2)"""
        if self.normalization_params is None:
            return normalized_data
        
        mean = np.array(self.normalization_params['mean'])
        std = np.array(self.normalization_params['std'])
        
        # Denormalize: x = (x_norm * std) + mean
        denormalized = (normalized_data * std) + mean
        return denormalized
    
    def run(self):
        """Start the GUI application"""
        self.root.mainloop()

def main():
    """Main function"""
    print("Starting MetaHuman Streamer v3 - NLP + Bone Streaming...")
    app = MetaHumanStreamerV3()
    app.run()

if __name__ == "__main__":
    main()
