#!/usr/bin/env python3
"""
Test script to demonstrate the connection indicator functionality
This creates a simple OSC server to receive messages from the GUI
"""

import socket
import threading
import time
from pythonosc import dispatcher
from pythonosc import osc_server

class TestOSCReceiver:
    def __init__(self, ip="127.0.0.1", port=8000):
        self.ip = ip
        self.port = port
        self.message_count = 0
        self.running = False
        self.server = None
        
    def message_handler(self, address, *args):
        """Handle incoming OSC messages"""
        self.message_count += 1
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] Received: {address} = {args[0] if args else 'no value'}")
        
        # Print every 10th message to avoid spam
        if self.message_count % 10 == 0:
            print(f"[{timestamp}] Total messages received: {self.message_count}")
    
    def start(self):
        """Start the OSC server"""
        try:
            # Create dispatcher
            disp = dispatcher.Dispatcher()
            disp.map("/mh/*", self.message_handler)
            
            # Create server
            self.server = osc_server.ThreadingOSCUDPServer((self.ip, self.port), disp)
            self.running = True
            
            print(f"OSC Server started on {self.ip}:{self.port}")
            print("Waiting for messages from MetaHuman Streamer GUI...")
            print("Press Ctrl+C to stop")
            
            # Start server in a separate thread
            server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            server_thread.start()
            
            # Keep main thread alive
            while self.running:
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\nShutting down OSC server...")
            self.stop()
        except Exception as e:
            print(f"Error starting OSC server: {e}")
    
    def stop(self):
        """Stop the OSC server"""
        self.running = False
        if self.server:
            self.server.shutdown()
        print(f"OSC Server stopped. Total messages received: {self.message_count}")

if __name__ == "__main__":
    receiver = TestOSCReceiver()
    receiver.start()
