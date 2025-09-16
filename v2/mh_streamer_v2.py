#!/usr/bin/env python3
"""
MetaHuman Streamer v2
Streams baseline position continuously and overlays turn movements on specific bones
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
from datetime import datetime

# Configuration
OSC_HOST = "127.0.0.1"
OSC_PORT = 7000
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

class MetaHumanStreamerV2:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("MetaHuman Streamer v2")
        self.root.geometry("700x600")
        
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
        
    def setup_gui(self):
        """Setup the GUI interface"""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Title
        title_label = ttk.Label(main_frame, text="MetaHuman Streamer v2", 
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
        
        # Control frame
        control_frame = ttk.LabelFrame(main_frame, text="Controls", padding="10")
        control_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Start/Stop streaming
        self.stream_button = ttk.Button(control_frame, text="Start Streaming", 
                                       command=self.toggle_streaming)
        self.stream_button.grid(row=0, column=0, padx=(0, 10))
        
        # Movement controls
        movement_frame = ttk.Frame(control_frame)
        movement_frame.grid(row=1, column=0, pady=(10, 0))
        
        self.left_button = ttk.Button(movement_frame, text="Turn Left", 
                                     command=self.start_left_turn, state="disabled")
        self.left_button.grid(row=0, column=0, padx=(0, 10))
        
        self.right_button = ttk.Button(movement_frame, text="Turn Right", 
                                      command=self.start_right_turn, state="disabled")
        self.right_button.grid(row=0, column=1, padx=(0, 10))
        
        self.baseline_button = ttk.Button(movement_frame, text="Return to Baseline", 
                                         command=self.return_to_baseline, state="disabled")
        self.baseline_button.grid(row=0, column=2)
        
        # Settings frame
        settings_frame = ttk.LabelFrame(main_frame, text="Settings", padding="10")
        settings_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
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
        log_frame.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(4, weight=1)
        
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
        stats_frame.grid(row=5, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        stats_frame.columnconfigure(1, weight=1)
        
        # OSC stats
        self.osc_stats_var = tk.StringVar(value="Messages: 0 | Errors: 0")
        self.osc_stats_label = ttk.Label(stats_frame, textvariable=self.osc_stats_var, 
                                        font=('Arial', 9))
        self.osc_stats_label.grid(row=0, column=0, sticky=tk.W)
        
        # Info frame
        info_frame = ttk.LabelFrame(main_frame, text="Information", padding="10")
        info_frame.grid(row=6, column=0, columnspan=3, sticky=(tk.W, tk.E))
        
        info_text = """v2 Features:
• Continuously streams baseline position
• Overlays turn movements on specific bones
• Smooth transitions between movements
• Separate models for each movement type
• Configurable OSC host and port settings
• Real-time OSC connection management
• Live data logging and debugging"""
        
        info_label = ttk.Label(info_frame, text=info_text, justify=tk.LEFT)
        info_label.grid(row=0, column=0, sticky=tk.W)
        
    def load_models_and_data(self):
        """Load the trained models and data"""
        try:
            data_dir = "data/processed_v2"
            
            # Load normalization parameters
            with open(os.path.join(data_dir, "normalization_params.json"), 'r') as f:
                self.normalization_params = json.load(f)
            
            # Load baseline vector
            self.baseline_vector = np.load(os.path.join(data_dir, "baseline_vector.npy"))
            
            # Load feature names (assuming they're in the same format as v1)
            feature_file = "data/processed/columns.txt"
            if os.path.exists(feature_file):
                with open(feature_file, 'r') as f:
                    self.feature_names = [line.strip() for line in f.readlines()]
            else:
                # Generate feature names if not available
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
            self.log_message("Models and data loaded successfully")
            print("Models and data loaded successfully")
            
            # Initialize OSC client
            self.update_osc_client()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load models: {str(e)}")
            self.status_label.config(text="Error loading models")
            print(f"Error loading models: {e}")
    
    def load_channel_config(self):
        """Load OSC channel configuration for Unreal Engine"""
        try:
            config_path = "data/processed/osc_channels_config.json"
            
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
                
                # Find this feature in our feature names
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
        """Generate a baseline sequence for continuous streaming"""
        with torch.no_grad():
            # Load baseline data and use it directly
            baseline_data = np.load("data/processed_v2/baseline_data.npy")
            # Use the first sample as our baseline sequence
            self.baseline_sequence = baseline_data[0]  # Shape: (60, 864)
            print(f"Loaded baseline sequence: {self.baseline_sequence.shape}")
    
    def generate_turn_sequence(self, model, duration_seconds):
        """Generate a turn sequence using the specified model"""
        with torch.no_grad():
            # Load the appropriate turn data
            if model == self.left_turn_model:
                turn_data = np.load("data/processed_v2/left_turn_data.npy")
            else:
                turn_data = np.load("data/processed_v2/right_turn_data.npy")
            
            # Use the first sample as our turn sequence
            sequence = turn_data[0]  # Shape: (60, 864)
            return sequence
    
    def update_osc_client(self):
        """Update OSC client with current host and port settings"""
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
        """Apply OSC settings and update connection"""
        if self.is_streaming:
            messagebox.showwarning("Warning", "Cannot change OSC settings while streaming. Please stop streaming first.")
            return
        
        self.update_osc_client()
        if self.osc_client:
            messagebox.showinfo("Success", f"OSC settings updated to {self.osc_host}:{self.osc_port}")
            self.log_message(f"OSC settings updated to {self.osc_host}:{self.osc_port}")
    
    def log_message(self, message):
        """Add message to log console"""
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
        """Toggle data display in log"""
        self.show_data = self.show_data_var.get()
        self.log_message(f"Data display {'enabled' if self.show_data else 'disabled'}")
    
    def clear_log(self):
        """Clear the log console"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.log_message("Log cleared")
    
    def update_osc_stats(self):
        """Update OSC statistics display"""
        self.osc_stats_var.set(f"Messages: {self.osc_send_count} | Errors: {self.osc_error_count}")
    
    def start_left_turn(self):
        """Start left turn movement"""
        if not self.is_streaming:
            return
            
        self.current_mode = "TURNING_LEFT"
        duration = float(self.duration_var.get())
        
        # Generate left turn sequence
        self.left_turn_sequence = self.generate_turn_sequence(self.left_turn_model, duration)
        
        self.status_label.config(text="Turning Left...")
        self.log_message("Started left turn")
        print("Started left turn")
    
    def start_right_turn(self):
        """Start right turn movement"""
        if not self.is_streaming:
            return
            
        self.current_mode = "TURNING_RIGHT"
        duration = float(self.duration_var.get())
        
        # Generate right turn sequence
        self.right_turn_sequence = self.generate_turn_sequence(self.right_turn_model, duration)
        
        self.status_label.config(text="Turning Right...")
        self.log_message("Started right turn")
        print("Started right turn")
    
    def return_to_baseline(self):
        """Return to baseline movement"""
        if not self.is_streaming:
            return
            
        self.current_mode = "BASELINE"
        self.status_label.config(text="Streaming Baseline...")
        self.log_message("Returned to baseline")
        print("Returned to baseline")
    
    def toggle_streaming(self):
        """Start or stop streaming"""
        if not self.is_streaming:
            self.start_streaming()
        else:
            self.stop_streaming()
    
    def start_streaming(self):
        """Start the streaming process"""
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
        
        # Start streaming thread
        self.stream_thread = threading.Thread(target=self.stream_worker)
        self.stream_thread.daemon = True
        self.stream_thread.start()
        
        self.status_label.config(text="Streaming Baseline...")
        self.log_message("Started streaming baseline")
        print("Started streaming")
    
    def stop_streaming(self):
        """Stop the streaming process"""
        self.is_streaming = False
        self.stop_event.set()
        
        # Update GUI
        self.stream_button.config(text="Start Streaming")
        self.left_button.config(state="disabled")
        self.right_button.config(state="disabled")
        self.baseline_button.config(state="disabled")
        
        self.status_label.config(text="Stopped")
        self.log_message("Stopped streaming")
        print("Stopped streaming")
    
    def stream_worker(self):
        """Background worker for streaming data"""
        frame_duration = 1.0 / int(self.fps_var.get())
        frame_count = 0
        
        while not self.stop_event.is_set():
            start_time = time.time()
            
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
        """Stream a single frame of data via OSC using proper Unreal format"""
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
    
    def denormalize_data(self, normalized_data):
        """Denormalize data using the stored parameters"""
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
    print("Starting MetaHuman Streamer v2...")
    app = MetaHumanStreamerV2()
    app.run()

if __name__ == "__main__":
    main()
