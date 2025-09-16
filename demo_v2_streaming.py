#!/usr/bin/env python3
"""
Demo: What v2 Streamer sends to Unreal Engine
Shows the exact OSC messages and data flow
"""

import json
import numpy as np

def demo_v2_streaming():
    """Demonstrate what the v2 streamer sends to Unreal"""
    
    print("🎭 MetaHuman Streamer v2 - What's Streaming to Unreal")
    print("=" * 60)
    
    # Simulate the v2 streamer configuration
    print("1. STREAMER CONFIGURATION:")
    print("-" * 30)
    print("• OSC Endpoint: 127.0.0.1:7000")
    print("• Streaming Rate: 30 FPS")
    print("• Data Source: ML Models (GRU)")
    print("• Modes: BASELINE, TURNING_LEFT, TURNING_RIGHT")
    print()
    
    # Show what channels would be configured
    print("2. OSC CHANNELS (Bone-level messages):")
    print("-" * 40)
    
    # Simulate typical MetaHuman bone channels
    bone_channels = [
        "/bone/thorax/extension",
        "/bone/thorax/left_ward_rotation", 
        "/bone/thorax/right_ward_rotation",
        "/bone/thorax/flexion",
        "/bone/neck/extension",
        "/bone/neck/left_ward_rotation",
        "/bone/neck/right_ward_rotation",
        "/bone/neck/flexion",
        "/bone/left_shoulder/extension",
        "/bone/left_shoulder/flexion",
        "/bone/left_shoulder/left_ward_rotation",
        "/bone/right_shoulder/extension", 
        "/bone/right_shoulder/flexion",
        "/bone/right_shoulder/right_ward_rotation",
        "/bone/left_elbow/flexion",
        "/bone/right_elbow/flexion",
        "/bone/left_forearm/pronation",
        "/bone/right_forearm/pronation",
        "/bone/left_wrist/flexion",
        "/bone/right_wrist/flexion"
    ]
    
    for i, channel in enumerate(bone_channels):
        print(f"  {i+1:2d}. {channel}")
    print(f"     ... and more (typically 37+ channels)")
    print()
    
    # Show data flow
    print("3. DATA FLOW:")
    print("-" * 15)
    print("Raw Data → ML Model → Denormalize → Transform → OSC")
    print("   ↓           ↓           ↓           ↓        ↓")
    print("864 features → GRU → Real values → Scale/Offset → Unreal")
    print()
    
    # Show what happens during streaming
    print("4. STREAMING PROCESS:")
    print("-" * 25)
    print("• Continuously streams at 30 FPS")
    print("• Each frame sends 37+ individual OSC messages")
    print("• Messages contain bone rotation values in degrees")
    print("• Values are transformed and clamped")
    print("• Control messages sent for frame tracking")
    print()
    
    # Show sample data
    print("5. SAMPLE OSC MESSAGES (Frame 1):")
    print("-" * 40)
    
    # Simulate baseline values
    baseline_values = {
        "/bone/thorax/extension": 0.0,
        "/bone/thorax/left_ward_rotation": 0.0,
        "/bone/thorax/right_ward_rotation": 0.0,
        "/bone/neck/extension": 0.0,
        "/bone/neck/left_ward_rotation": 0.0,
        "/bone/neck/right_ward_rotation": 0.0,
        "/bone/left_shoulder/extension": 0.0,
        "/bone/right_shoulder/extension": 0.0,
        "/bone/left_elbow/flexion": 0.0,
        "/bone/right_elbow/flexion": 0.0,
    }
    
    for channel, value in baseline_values.items():
        print(f"  {channel:35s} = {value:8.3f}")
    print("  /mh/frame                           = 1")
    print("  /mh/mode                            = BASELINE")
    print()
    
    # Show turn left example
    print("6. SAMPLE OSC MESSAGES (Turn Left):")
    print("-" * 40)
    
    # Simulate left turn values
    left_turn_values = {
        "/bone/thorax/extension": 2.5,
        "/bone/thorax/left_ward_rotation": 15.3,
        "/bone/thorax/right_ward_rotation": -5.2,
        "/bone/neck/extension": 1.8,
        "/bone/neck/left_ward_rotation": 12.7,
        "/bone/neck/right_ward_rotation": -3.1,
        "/bone/left_shoulder/extension": 8.9,
        "/bone/right_shoulder/extension": -2.3,
        "/bone/left_elbow/flexion": 5.4,
        "/bone/right_elbow/flexion": -1.2,
    }
    
    for channel, value in left_turn_values.items():
        print(f"  {channel:35s} = {value:8.3f}")
    print("  /mh/frame                           = 2")
    print("  /mh/mode                            = TURNING_LEFT")
    print()
    
    # Show turn right example
    print("7. SAMPLE OSC MESSAGES (Turn Right):")
    print("-" * 40)
    
    # Simulate right turn values
    right_turn_values = {
        "/bone/thorax/extension": 2.1,
        "/bone/thorax/left_ward_rotation": -8.7,
        "/bone/thorax/right_ward_rotation": 18.4,
        "/bone/neck/extension": 1.5,
        "/bone/neck/left_ward_rotation": -6.9,
        "/bone/neck/right_ward_rotation": 14.2,
        "/bone/left_shoulder/extension": -3.8,
        "/bone/right_shoulder/extension": 9.1,
        "/bone/left_elbow/flexion": -2.1,
        "/bone/right_elbow/flexion": 4.7,
    }
    
    for channel, value in right_turn_values.items():
        print(f"  {channel:35s} = {value:8.3f}")
    print("  /mh/frame                           = 3")
    print("  /mh/mode                            = TURNING_RIGHT")
    print()
    
    # Show data processing
    print("8. DATA PROCESSING:")
    print("-" * 20)
    print("• Raw ML output: 864 features (normalized)")
    print("• Denormalization: (value * std) + mean")
    print("• Transformation: (value * scale) + offset")
    print("• Clamping: min/max limits applied")
    print("• Units: Degrees for rotations")
    print()
    
    # Show streaming modes
    print("9. STREAMING MODES:")
    print("-" * 20)
    print("• BASELINE: Default sitting position")
    print("• TURNING_LEFT: Left steering movement")
    print("• TURNING_RIGHT: Right steering movement")
    print("• Smooth transitions between modes")
    print("• Auto-return to baseline after turns")
    print()
    
    print("=" * 60)
    print("🎯 SUMMARY:")
    print("• v2 sends MANY individual /bone/{bone}/{axis} messages")
    print("• Each message contains a single rotation value")
    print("• Values are in degrees and represent bone rotations")
    print("• 30 FPS continuous streaming")
    print("• ML models generate realistic movement sequences")
    print("• Perfect for detailed MetaHuman animation control")

if __name__ == "__main__":
    demo_v2_streaming()
