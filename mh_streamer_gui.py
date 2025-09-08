#!/usr/bin/env python3
"""
MetaHuman Steering Streamer GUI
A Tkinter-based desktop application for streaming OSC messages to Unreal Engine
to drive MetaHuman characters using multi-channel steering data.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import queue
import json
import time
import os
import numpy as np
from pythonosc.udp_client import SimpleUDPClient
from datetime import datetime
import sys

# Constants
COMMANDS = {
    'START_HEARTBEAT': 'START_HEARTBEAT',
    'TURN_RIGHT': 'TURN_RIGHT',
    'TURN_LEFT': 'TURN_LEFT',
    'BASELINE': 'BASELINE',
    'STOP_ALL': 'STOP_ALL',
    'QUIT': 'QUIT'
}

MODES = {
    'IDLE': 'Idle',
    'HEARTBEAT': 'Heartbeat',
    'TURNING_RIGHT': 'Turning Right',
    'TURNING_LEFT': 'Turning Left',
    'BASELINE': 'Baseline',
    'STOPPED': 'Stopped'
}

class MetaHumanStreamerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("MetaHuman Steering Streamer")
        self.root.geometry("800x700")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # OSC and streaming state
        self.osc_client = None
        self.running = False
        self.worker_thread = None
        self.command_queue = queue.Queue()
        self.current_mode = MODES['IDLE']
        self.channels = []
        self.ramp_data = None
        self.ramp_frame = 0
        self.hold_frames = 0
        self.hold_frame = 0
        
        # Connection monitoring
        self.connection_active = False
        self.last_send_time = 0
        self.connection_timeout = 2.0  # seconds
        self.osc_send_count = 0
        self.osc_error_count = 0
        
        # Settings
        self.settings_file = os.path.expanduser("~/.mh_streamer_gui.json")
        self.load_settings()
        
        # Create GUI
        self.create_widgets()
        self.setup_hotkeys()
        
        # Start worker thread
        self.start_worker()
        
    def create_widgets(self):
        """Create and layout all GUI widgets"""
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Title
        title_label = ttk.Label(main_frame, text="MetaHuman Steering Streamer", 
                               font=('Arial', 16, 'bold'))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # Connection settings frame
        conn_frame = ttk.LabelFrame(main_frame, text="Connection Settings", padding="10")
        conn_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        conn_frame.columnconfigure(1, weight=1)
        
        # IP Address
        ttk.Label(conn_frame, text="IP Address:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.ip_var = tk.StringVar(value=self.settings.get('ip', '127.0.0.1'))
        ip_entry = ttk.Entry(conn_frame, textvariable=self.ip_var, width=15)
        ip_entry.grid(row=0, column=1, sticky=tk.W, padx=(0, 20))
        
        # Port
        ttk.Label(conn_frame, text="Port:").grid(row=0, column=2, sticky=tk.W, padx=(0, 5))
        self.port_var = tk.StringVar(value=str(self.settings.get('port', 8000)))
        port_entry = ttk.Entry(conn_frame, textvariable=self.port_var, width=8)
        port_entry.grid(row=0, column=3, sticky=tk.W, padx=(0, 20))
        
        # FPS
        ttk.Label(conn_frame, text="FPS:").grid(row=0, column=4, sticky=tk.W, padx=(0, 5))
        self.fps_var = tk.StringVar(value=str(self.settings.get('fps', 60)))
        fps_entry = ttk.Entry(conn_frame, textvariable=self.fps_var, width=8)
        fps_entry.grid(row=0, column=5, sticky=tk.W)
        
        # Config file
        ttk.Label(conn_frame, text="Config File:").grid(row=1, column=0, sticky=tk.W, padx=(0, 5), pady=(10, 0))
        self.config_var = tk.StringVar(value=self.settings.get('config_file', './data/processed/channels_steering_from_columns.json'))
        config_entry = ttk.Entry(conn_frame, textvariable=self.config_var, width=50)
        config_entry.grid(row=1, column=1, columnspan=4, sticky=(tk.W, tk.E), pady=(10, 0), padx=(0, 5))
        
        browse_btn = ttk.Button(conn_frame, text="Browse...", command=self.browse_config)
        browse_btn.grid(row=1, column=5, pady=(10, 0))
        
        # Action parameters frame
        action_frame = ttk.LabelFrame(main_frame, text="Action Parameters", padding="10")
        action_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Duration
        ttk.Label(action_frame, text="Duration (s):").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.duration_var = tk.StringVar(value=str(self.settings.get('duration', 1.5)))
        duration_entry = ttk.Entry(action_frame, textvariable=self.duration_var, width=10)
        duration_entry.grid(row=0, column=1, sticky=tk.W, padx=(0, 20))
        
        # Hold
        ttk.Label(action_frame, text="Hold (s):").grid(row=0, column=2, sticky=tk.W, padx=(0, 5))
        self.hold_var = tk.StringVar(value=str(self.settings.get('hold', 0.0)))
        hold_entry = ttk.Entry(action_frame, textvariable=self.hold_var, width=10)
        hold_entry.grid(row=0, column=3, sticky=tk.W)
        
        # Action buttons frame
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=3, pady=(0, 10))
        
        # Action buttons
        self.start_btn = ttk.Button(button_frame, text="Start Streaming", 
                                   command=self.start_streaming, width=15)
        self.start_btn.grid(row=0, column=0, padx=5)
        
        self.right_btn = ttk.Button(button_frame, text="Turn Right", 
                                   command=self.turn_right, width=15)
        self.right_btn.grid(row=0, column=1, padx=5)
        
        self.left_btn = ttk.Button(button_frame, text="Turn Left", 
                                  command=self.turn_left, width=15)
        self.left_btn.grid(row=0, column=2, padx=5)
        
        self.baseline_btn = ttk.Button(button_frame, text="Return to Baseline", 
                                      command=self.return_to_baseline, width=15)
        self.baseline_btn.grid(row=0, column=3, padx=5)
        
        self.stop_btn = ttk.Button(button_frame, text="Stop Streaming", 
                                  command=self.stop_streaming, width=15)
        self.stop_btn.grid(row=0, column=4, padx=5)
        
        # Log console
        log_frame = ttk.LabelFrame(main_frame, text="Log Console", padding="5")
        log_frame.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(4, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, width=80, 
                                                 state=tk.DISABLED, wrap=tk.WORD)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Connection indicator frame
        conn_indicator_frame = ttk.Frame(main_frame)
        conn_indicator_frame.grid(row=5, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(10, 0))
        conn_indicator_frame.columnconfigure(1, weight=1)
        
        # Connection status indicator
        self.connection_var = tk.StringVar(value="Disconnected")
        self.connection_color = "red"
        self.connection_label = ttk.Label(conn_indicator_frame, text="Connection:", font=('Arial', 10, 'bold'))
        self.connection_label.grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        
        self.connection_indicator = tk.Label(conn_indicator_frame, text="●", fg=self.connection_color, 
                                           font=('Arial', 16, 'bold'))
        self.connection_indicator.grid(row=0, column=1, sticky=tk.W, padx=(0, 5))
        
        self.connection_text = ttk.Label(conn_indicator_frame, textvariable=self.connection_var)
        self.connection_text.grid(row=0, column=2, sticky=tk.W, padx=(0, 20))
        
        # OSC stats
        self.osc_stats_var = tk.StringVar(value="Messages: 0 | Errors: 0")
        self.osc_stats_label = ttk.Label(conn_indicator_frame, textvariable=self.osc_stats_var, 
                                        font=('Arial', 9))
        self.osc_stats_label.grid(row=0, column=3, sticky=tk.E)
        
        # Status bar
        self.status_var = tk.StringVar(value="Status: Idle")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, 
                              relief=tk.SUNKEN, anchor=tk.W)
        status_bar.grid(row=6, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(5, 0))
        
        # Load initial config
        self.load_config()
        
    def setup_hotkeys(self):
        """Setup keyboard shortcuts"""
        self.root.bind('<KeyPress>', self.on_key_press)
        self.root.focus_set()
        
    def on_key_press(self, event):
        """Handle keyboard shortcuts"""
        if event.state & 0x4:  # Ctrl key
            if event.keysym.lower() == 's':
                self.start_streaming()
            elif event.keysym.lower() == 'r':
                self.turn_right()
            elif event.keysym.lower() == 'l':
                self.turn_left()
            elif event.keysym.lower() == 'b':
                self.return_to_baseline()
            elif event.keysym.lower() == 'x':
                self.stop_streaming()
    
    def load_settings(self):
        """Load settings from file or use defaults"""
        self.settings = {
            'ip': '127.0.0.1',
            'port': 8000,
            'fps': 60,
            'duration': 1.5,
            'hold': 0.0,
            'config_file': './data/processed/channels_steering_from_columns.json'
        }
        
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r') as f:
                    saved_settings = json.load(f)
                    self.settings.update(saved_settings)
            except Exception as e:
                self.log_message(f"Error loading settings: {e}")
    
    def save_settings(self):
        """Save current settings to file"""
        try:
            self.settings.update({
                'ip': self.ip_var.get(),
                'port': int(self.port_var.get()),
                'fps': int(self.fps_var.get()),
                'duration': float(self.duration_var.get()),
                'hold': float(self.hold_var.get()),
                'config_file': self.config_var.get()
            })
            
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            self.log_message(f"Error saving settings: {e}")
    
    def browse_config(self):
        """Open file dialog to select config file"""
        filename = filedialog.askopenfilename(
            title="Select Channel Configuration File",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialdir=os.path.dirname(self.config_var.get())
        )
        if filename:
            self.config_var.set(filename)
            self.load_config()
    
    def load_config(self):
        """Load channel configuration from JSON file"""
        try:
            config_path = self.config_var.get()
            if not os.path.exists(config_path):
                self.log_message(f"Config file not found: {config_path}")
                return False
                
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # Validate config structure
            if 'channels' not in config:
                raise ValueError("Config missing 'channels' key")
            
            self.channels = []
            for i, channel in enumerate(config['channels']):
                required_keys = ['address', 'amp_right', 'amp_left']
                if not all(key in channel for key in required_keys):
                    raise ValueError(f"Channel {i} missing required keys: {required_keys}")
                
                self.channels.append({
                    'address': channel['address'],
                    'amp_right': float(channel['amp_right']),
                    'amp_left': float(channel['amp_left'])
                })
            
            self.log_message(f"Loaded {len(self.channels)} channels from {config_path}")
            return True
            
        except Exception as e:
            self.log_message(f"Error loading config: {e}")
            messagebox.showerror("Config Error", f"Failed to load configuration:\n{e}")
            return False
    
    def log_message(self, message):
        """Add message to log console"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        log_entry = f"[{timestamp}] {message}\n"
        
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, log_entry)
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
    
    def update_status(self, status):
        """Update status bar"""
        self.status_var.set(f"Status: {status}")
        self.current_mode = status
    
    def start_worker(self):
        """Start the background worker thread"""
        self.running = True
        self.worker_thread = threading.Thread(target=self.worker_loop, daemon=True)
        self.worker_thread.start()
    
    def worker_loop(self):
        """Main worker loop that handles OSC communication"""
        while self.running:
            try:
                # Process commands
                try:
                    command = self.command_queue.get_nowait()
                    self.handle_command(command)
                except queue.Empty:
                    pass
                
                # Check connection timeout
                self.check_connection_timeout()
                
                # Handle current mode
                if self.current_mode == MODES['HEARTBEAT']:
                    self.send_heartbeat()
                elif self.current_mode in [MODES['TURNING_RIGHT'], MODES['TURNING_LEFT'], MODES['BASELINE']]:
                    self.send_ramp_frame()
                
                # Sleep for frame timing
                fps = int(self.fps_var.get())
                time.sleep(1.0 / fps)
                
            except Exception as e:
                self.root.after(0, lambda: self.log_message(f"Worker error: {e}"))
                time.sleep(0.1)
    
    def handle_command(self, command):
        """Handle commands from the GUI thread"""
        if command == COMMANDS['START_HEARTBEAT']:
            self.start_osc_client()
            self.root.after(0, lambda: self.update_status(MODES['HEARTBEAT']))
            self.root.after(0, lambda: self.log_message("Started heartbeat streaming"))
            
        elif command == COMMANDS['TURN_RIGHT']:
            self.start_ramp('right')
            self.root.after(0, lambda: self.update_status(MODES['TURNING_RIGHT']))
            self.root.after(0, lambda: self.log_message("Started right turn"))
            
        elif command == COMMANDS['TURN_LEFT']:
            self.start_ramp('left')
            self.root.after(0, lambda: self.update_status(MODES['TURNING_LEFT']))
            self.root.after(0, lambda: self.log_message("Started left turn"))
            
        elif command == COMMANDS['BASELINE']:
            self.start_ramp('baseline')
            self.root.after(0, lambda: self.update_status(MODES['BASELINE']))
            self.root.after(0, lambda: self.log_message("Started return to baseline"))
            
        elif command == COMMANDS['STOP_ALL']:
            self.stop_all()
            self.root.after(0, lambda: self.update_status(MODES['STOPPED']))
            self.root.after(0, lambda: self.log_message("Stopped all streaming"))
            
        elif command == COMMANDS['QUIT']:
            self.running = False
    
    def start_osc_client(self):
        """Initialize OSC client"""
        try:
            ip = self.ip_var.get()
            port = int(self.port_var.get())
            self.osc_client = SimpleUDPClient(ip, port)
            self.connection_active = True
            self.last_send_time = time.time()
            self.osc_send_count = 0
            self.osc_error_count = 0
            self.root.after(0, lambda: self.update_connection_status("Connected", "green"))
            self.log_message(f"OSC client connected to {ip}:{port}")
        except Exception as e:
            self.connection_active = False
            self.root.after(0, lambda: self.update_connection_status("Connection Failed", "red"))
            self.log_message(f"Failed to create OSC client: {e}")
    
    def send_heartbeat(self):
        """Send heartbeat (zeros) to all channels"""
        if not self.osc_client or not self.channels:
            return
            
        success_count = 0
        for channel in self.channels:
            try:
                self.osc_client.send_message(channel['address'], 0.0)
                success_count += 1
            except Exception as e:
                self.osc_error_count += 1
                self.root.after(0, lambda: self.log_message(f"OSC send error: {e}"))
        
        if success_count > 0:
            self.osc_send_count += success_count
            self.last_send_time = time.time()
            self.root.after(0, lambda: self.update_osc_stats())
    
    def start_ramp(self, direction):
        """Start a ramp animation"""
        if not self.osc_client or not self.channels:
            return
        
        try:
            duration = float(self.duration_var.get())
            fps = int(self.fps_var.get())
            hold = float(self.hold_var.get())
            
            ramp_frames = int(duration * fps)
            hold_frames = int(hold * fps)
            
            # Build ramp data
            self.ramp_data = []
            for channel in self.channels:
                if direction == 'right':
                    amplitude = channel['amp_right']
                elif direction == 'left':
                    amplitude = channel['amp_left']
                else:  # baseline
                    amplitude = 0.0
                
                # Create envelope
                envelope = self.build_envelope(ramp_frames)
                ramp_values = amplitude * envelope
                self.ramp_data.append(ramp_values)
            
            self.ramp_frame = 0
            self.hold_frames = hold_frames
            self.hold_frame = 0
            
        except Exception as e:
            self.root.after(0, lambda: self.log_message(f"Error starting ramp: {e}"))
    
    def send_ramp_frame(self):
        """Send current frame of ramp animation"""
        if not self.osc_client or not self.ramp_data:
            return
        
        try:
            success_count = 0
            # Check if we're in hold phase
            if self.ramp_frame >= len(self.ramp_data[0]):
                if self.hold_frame < self.hold_frames:
                    # Send final values during hold
                    for i, channel in enumerate(self.channels):
                        final_value = self.ramp_data[i][-1]
                        try:
                            self.osc_client.send_message(channel['address'], final_value)
                            success_count += 1
                        except Exception as e:
                            self.osc_error_count += 1
                    self.hold_frame += 1
                else:
                    # Hold complete, return to heartbeat
                    self.root.after(0, lambda: self.command_queue.put(COMMANDS['START_HEARTBEAT']))
                return
            
            # Send current ramp frame
            for i, channel in enumerate(self.channels):
                value = self.ramp_data[i][self.ramp_frame]
                try:
                    self.osc_client.send_message(channel['address'], value)
                    success_count += 1
                except Exception as e:
                    self.osc_error_count += 1
            
            if success_count > 0:
                self.osc_send_count += success_count
                self.last_send_time = time.time()
                self.root.after(0, lambda: self.update_osc_stats())
            
            # Log first few channels occasionally
            if self.ramp_frame % 10 == 0 and len(self.channels) > 0:
                sample_values = [f"{self.ramp_data[i][self.ramp_frame]:.2f}" 
                               for i in range(min(3, len(self.channels)))]
                self.root.after(0, lambda: self.log_message(
                    f"Frame {self.ramp_frame}: {', '.join(sample_values)}"))
            
            self.ramp_frame += 1
            
        except Exception as e:
            self.root.after(0, lambda: self.log_message(f"Ramp send error: {e}"))
    
    def stop_all(self):
        """Stop all streaming and send zeros"""
        self.ramp_data = None
        self.ramp_frame = 0
        self.hold_frame = 0
        self.connection_active = False
        self.root.after(0, lambda: self.update_connection_status("Disconnected", "red"))
        
        if self.osc_client and self.channels:
            success_count = 0
            for channel in self.channels:
                try:
                    self.osc_client.send_message(channel['address'], 0.0)
                    success_count += 1
                except Exception as e:
                    self.osc_error_count += 1
                    self.root.after(0, lambda: self.log_message(f"Stop send error: {e}"))
            
            if success_count > 0:
                self.osc_send_count += success_count
                self.last_send_time = time.time()
                self.root.after(0, lambda: self.update_osc_stats())
    
    def build_envelope(self, n_frames):
        """Build cubic ease-in-out envelope"""
        t = np.linspace(0, 1, n_frames)
        # Cubic ease-in-out: 3t² - 2t³
        envelope = 3 * t**2 - 2 * t**3
        return envelope
    
    def update_connection_status(self, status, color):
        """Update connection status indicator"""
        self.connection_var.set(status)
        self.connection_color = color
        self.connection_indicator.config(fg=color)
    
    def update_osc_stats(self):
        """Update OSC statistics display"""
        self.osc_stats_var.set(f"Messages: {self.osc_send_count} | Errors: {self.osc_error_count}")
    
    def check_connection_timeout(self):
        """Check if connection has timed out"""
        if self.connection_active and self.last_send_time > 0:
            time_since_last_send = time.time() - self.last_send_time
            if time_since_last_send > self.connection_timeout:
                self.connection_active = False
                self.root.after(0, lambda: self.update_connection_status("Timeout", "orange"))
                self.root.after(0, lambda: self.log_message("Connection timeout - no recent OSC activity"))
    
    # GUI event handlers
    def start_streaming(self):
        """Start heartbeat streaming"""
        if not self.channels:
            messagebox.showwarning("No Channels", "Please load a valid configuration file first.")
            return
        
        self.command_queue.put(COMMANDS['START_HEARTBEAT'])
        self.update_button_states()
    
    def turn_right(self):
        """Start right turn animation"""
        if not self.channels:
            messagebox.showwarning("No Channels", "Please load a valid configuration file first.")
            return
        
        self.command_queue.put(COMMANDS['TURN_RIGHT'])
        self.update_button_states()
    
    def turn_left(self):
        """Start left turn animation"""
        if not self.channels:
            messagebox.showwarning("No Channels", "Please load a valid configuration file first.")
            return
        
        self.command_queue.put(COMMANDS['TURN_LEFT'])
        self.update_button_states()
    
    def return_to_baseline(self):
        """Return to baseline pose"""
        if not self.channels:
            messagebox.showwarning("No Channels", "Please load a valid configuration file first.")
            return
        
        self.command_queue.put(COMMANDS['BASELINE'])
        self.update_button_states()
    
    def stop_streaming(self):
        """Stop all streaming"""
        self.command_queue.put(COMMANDS['STOP_ALL'])
        self.update_button_states()
    
    def update_button_states(self):
        """Update button enabled/disabled states"""
        is_streaming = self.current_mode in [MODES['HEARTBEAT'], MODES['TURNING_RIGHT'], 
                                           MODES['TURNING_LEFT'], MODES['BASELINE']]
        
        self.start_btn.config(state=tk.NORMAL if not is_streaming else tk.DISABLED)
        self.right_btn.config(state=tk.NORMAL if is_streaming else tk.DISABLED)
        self.left_btn.config(state=tk.NORMAL if is_streaming else tk.DISABLED)
        self.baseline_btn.config(state=tk.NORMAL if is_streaming else tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL if is_streaming else tk.DISABLED)
    
    def on_closing(self):
        """Handle window closing"""
        self.save_settings()
        self.command_queue.put(COMMANDS['QUIT'])
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=1.0)
        self.root.destroy()

def main():
    """Main entry point"""
    root = tk.Tk()
    app = MetaHumanStreamerGUI(root)
    
    # Center window
    root.update_idletasks()
    x = (root.winfo_screenwidth() // 2) - (root.winfo_width() // 2)
    y = (root.winfo_screenheight() // 2) - (root.winfo_height() // 2)
    root.geometry(f"+{x}+{y}")
    
    root.mainloop()

if __name__ == "__main__":
    main()
