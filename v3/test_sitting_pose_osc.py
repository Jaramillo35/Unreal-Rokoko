#!/usr/bin/env python3
"""
Test script to verify sitting pose OSC messages
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mh_streamer_v3 import MetaHumanStreamerV3
from python_osc.dispatcher import Dispatcher
from python_osc.osc_server import BlockingOSCUDPServer
import threading
import time

class MockOSCReceiver:
    def __init__(self, port=9001):
        self.port = port
        self.received_messages = []
        self.dispatcher = Dispatcher()
        self.dispatcher.map("/cmd/pose", self.handle_pose_command)
        self.dispatcher.map("/bone/*", self.handle_bone_message)
        self.server = None
        self.running = False
    
    def handle_pose_command(self, address, *args):
        self.received_messages.append(("POSE", address, args))
        print(f"📡 Received pose command: {address} {args}")
    
    def handle_bone_message(self, address, *args):
        self.received_messages.append(("BONE", address, args))
        print(f"🦴 Received bone message: {address} {args[0]:.3f}")
    
    def start(self):
        self.server = BlockingOSCUDPServer(("127.0.0.1", self.port), self.dispatcher)
        self.running = True
        print(f"🎧 Mock OSC receiver started on port {self.port}")
    
    def stop(self):
        self.running = False
        if self.server:
            self.server.shutdown()
    
    def get_stats(self):
        pose_commands = [msg for msg in self.received_messages if msg[0] == "POSE"]
        bone_messages = [msg for msg in self.received_messages if msg[0] == "BONE"]
        return len(pose_commands), len(bone_messages)

def test_sitting_pose():
    print("🧪 Testing Sitting Pose OSC Messages")
    print("=" * 40)
    
    # Start mock receiver
    receiver = MockOSCReceiver(9001)
    receiver_thread = threading.Thread(target=receiver.start)
    receiver_thread.daemon = True
    receiver_thread.start()
    
    time.sleep(1)  # Let receiver start
    
    # Create streamer with different port
    print("🔧 Creating streamer...")
    app = MetaHumanStreamerV3()
    app.osc_client.host = "127.0.0.1"
    app.osc_client.port = 9001  # Send to our mock receiver
    
    print(f"✅ Streamer ready with {len(app.baseline_sitting_pose)} pose values")
    print()
    
    # Test sitting pose
    print("🪑 Triggering sitting pose...")
    app.trigger_sitting_pose()
    
    time.sleep(0.5)  # Let messages be sent
    
    # Get stats
    pose_count, bone_count = receiver.get_stats()
    
    print()
    print("📊 Results:")
    print(f"   Pose commands sent: {pose_count}")
    print(f"   Bone messages sent: {bone_count}")
    print(f"   Expected bone messages: ~44 (mapped columns)")
    
    # Show sample messages
    if receiver.received_messages:
        print()
        print("📋 Sample messages received:")
        for i, (msg_type, address, args) in enumerate(receiver.received_messages[:10]):
            if msg_type == "POSE":
                print(f"   {i+1}. {address} {args}")
            else:
                print(f"   {i+1}. {address} {args[0]:.3f}")
        
        if len(receiver.received_messages) > 10:
            print(f"   ... and {len(receiver.received_messages) - 10} more")
    
    receiver.stop()
    print()
    print("✅ Test completed!")

if __name__ == "__main__":
    test_sitting_pose()
