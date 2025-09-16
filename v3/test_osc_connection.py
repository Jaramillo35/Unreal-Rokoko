#!/usr/bin/env python3
"""
Test OSC Connection to Unreal Engine
Sends test signals to verify connection and data flow
"""

import time
import math
from pythonosc import udp_client

def test_osc_connection():
    """Test OSC connection with animated test signals"""
    
    print("🎮 MetaHuman Streamer v3 - OSC Connection Test")
    print("=" * 50)
    
    # OSC Configuration
    host = "127.0.0.1"
    port = 9000
    
    print(f"📡 Connecting to {host}:{port}")
    
    try:
        # Create OSC client
        client = udp_client.SimpleUDPClient(host, port)
        print("✅ OSC client created successfully")
        
        # Test signals (most variable ones from analysis)
        test_signals = [
            "/bone/hand_r/yaw",      # Right wrist pronation (highest variation)
            "/bone/spine_01/yaw",    # Spine rotation
            "/bone/spine_02/yaw",    # Spine rotation
            "/bone/spine_03/yaw",    # Spine rotation
            "/bone/upperarm_r/roll", # Right shoulder abduction
            "/bone/hand_r/pitch",    # Right wrist flexion
            "/bone/hand_r/roll",     # Right wrist adduction
        ]
        
        print(f"\n🎯 Testing {len(test_signals)} signals:")
        for signal in test_signals:
            print(f"  • {signal}")
        
        print(f"\n🔄 Sending animated test data...")
        print("Press Ctrl+C to stop")
        
        frame = 0
        start_time = time.time()
        
        try:
            while True:
                current_time = time.time() - start_time
                
                # Send test data for each signal
                for i, signal in enumerate(test_signals):
                    # Create animated values (sine waves with different frequencies)
                    frequency = 0.5 + (i * 0.2)  # Different frequency for each signal
                    amplitude = 30.0 + (i * 10)  # Different amplitude for each signal
                    phase_offset = i * math.pi / 4  # Phase offset for variety
                    
                    # Generate animated value
                    value = amplitude * math.sin(2 * math.pi * frequency * current_time + phase_offset)
                    
                    # Send OSC message
                    client.send_message(signal, float(value))
                
                # Send frame info
                client.send_message("/mh/frame", frame)
                client.send_message("/mh/mode", "TEST")
                
                # Print status every 30 frames (1 second at 30 FPS)
                if frame % 30 == 0:
                    elapsed = time.time() - start_time
                    print(f"⏱️  Frame {frame:4d} | Time: {elapsed:5.1f}s | Sending {len(test_signals)} signals")
                
                frame += 1
                
                # Maintain 30 FPS
                time.sleep(1.0 / 30.0)
                
        except KeyboardInterrupt:
            print(f"\n🛑 Test stopped by user")
            print(f"📊 Sent {frame} frames over {time.time() - start_time:.1f} seconds")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        print("💡 Make sure Unreal Engine is running and listening on port 9000")

def test_specific_signals():
    """Test specific signals with known values"""
    
    print("\n🎯 Testing Specific Signal Values:")
    print("-" * 40)
    
    host = "127.0.0.1"
    port = 9000
    
    try:
        client = udp_client.SimpleUDPClient(host, port)
        
        # Test with known values
        test_values = [
            ("/bone/hand_r/yaw", 45.0),      # 45 degrees
            ("/bone/spine_01/yaw", -30.0),   # -30 degrees
            ("/bone/spine_02/yaw", -30.0),   # -30 degrees
            ("/bone/spine_03/yaw", -30.0),   # -30 degrees
            ("/bone/upperarm_r/roll", 15.0), # 15 degrees
            ("/bone/hand_r/pitch", 20.0),    # 20 degrees
            ("/bone/hand_r/roll", -10.0),    # -10 degrees
        ]
        
        print("Sending test values...")
        for signal, value in test_values:
            client.send_message(signal, value)
            print(f"  ✅ {signal} = {value}°")
        
        print("\n💡 Check Unreal Engine to see if these values are received!")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("Choose test mode:")
    print("1. Animated test (continuous sine waves)")
    print("2. Static test (fixed values)")
    
    choice = input("Enter choice (1 or 2): ").strip()
    
    if choice == "1":
        test_osc_connection()
    elif choice == "2":
        test_specific_signals()
    else:
        print("Invalid choice. Running animated test...")
        test_osc_connection()
