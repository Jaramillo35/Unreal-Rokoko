#!/usr/bin/env python3
"""
Example of OSC messages sent by MetaHuman Streamer v2
"""

import numpy as np
import json

def show_osc_message_examples():
    """Show examples of OSC messages that the streamer sends"""
    print("MetaHuman Streamer v2 - OSC Message Examples")
    print("=" * 60)
    
    try:
        # Load sample data
        baseline_data = np.load("data/processed_v2/baseline_data.npy")
        sample_frame = baseline_data[0, 0, :]  # First frame
        
        # Load feature names
        with open("data/processed_v2/normalization_params.json", 'r') as f:
            norm_params = json.load(f)
        feature_columns = norm_params['feature_columns']
        
        print("📡 ACTUAL OSC MESSAGES SENT BY THE STREAMER")
        print("=" * 60)
        print()
        
        # Show first 20 features as they would appear in OSC
        print("BONE POSITION DATA:")
        for i in range(20):
            if i < len(feature_columns) and i < len(sample_frame):
                address = f"/mh/{feature_columns[i]}"
                value = sample_frame[i]
                print(f"  {address} -> {value:.6f}")
        print()
        
        # Show control messages
        print("CONTROL MESSAGES:")
        print("  /mh/frame -> 0")
        print("  /mh/mode -> BASELINE")
        print()
        
        # Show different types of data
        print("DATA TYPES BY CATEGORY:")
        print()
        
        # Position data
        position_features = [i for i, col in enumerate(feature_columns) if 'position' in col][:5]
        print("📍 POSITION DATA (x, y, z coordinates):")
        for i in position_features:
            address = f"/mh/{feature_columns[i]}"
            value = sample_frame[i]
            print(f"  {address} -> {value:.6f}")
        print()
        
        # Rotation data
        rotation_features = [i for i, col in enumerate(feature_columns) if any(rot in col for rot in ['flexion', 'rotation', 'tilt'])][:5]
        print("🔄 ROTATION DATA (joint angles):")
        for i in rotation_features:
            address = f"/mh/{feature_columns[i]}"
            value = sample_frame[i]
            print(f"  {address} -> {value:.6f}")
        print()
        
        # Velocity data
        velocity_features = [i for i, col in enumerate(feature_columns) if 'velocity' in col][:5]
        print("⚡ VELOCITY DATA (movement speed):")
        for i in velocity_features:
            address = f"/mh/{feature_columns[i]}"
            value = sample_frame[i]
            print(f"  {address} -> {value:.6f}")
        print()
        
        # Show what happens during different modes
        print("🎭 DIFFERENT MOVEMENT MODES:")
        print()
        print("BASELINE MODE:")
        print("  /mh/mode -> BASELINE")
        print("  (All 864 features stream baseline sitting position)")
        print()
        print("TURNING LEFT MODE:")
        print("  /mh/mode -> TURNING_LEFT")
        print("  (Bones involved in left turn animate, others stay baseline)")
        print()
        print("TURNING RIGHT MODE:")
        print("  /mh/mode -> TURNING_RIGHT")
        print("  (Bones involved in right turn animate, others stay baseline)")
        print()
        
        # Show frame progression
        print("⏱️  FRAME PROGRESSION (at 30 FPS):")
        print("  Frame 0:  /mh/frame -> 0")
        print("  Frame 1:  /mh/frame -> 1")
        print("  Frame 2:  /mh/frame -> 2")
        print("  ...")
        print("  Frame 59: /mh/frame -> 59")
        print("  (Then loops back to frame 0)")
        print()
        
        # Show data rate
        print("📊 DATA RATE:")
        print(f"  Features per frame: {len(feature_columns)}")
        print("  Control messages per frame: 2")
        print("  Total messages per frame: 866")
        print("  At 30 FPS: 25,980 messages/second")
        print("  At 60 FPS: 51,960 messages/second")
        print()
        
        # Show what Unreal Engine would do with this data
        print("🎯 UNREAL ENGINE INTEGRATION:")
        print("  1. Listen for OSC messages on configured port")
        print("  2. Map addresses to bone transforms:")
        print("     /mh/Pelvis_position_x -> Pelvis bone X position")
        print("     /mh/LeftShoulder_flexion -> Left shoulder rotation")
        print("     /mh/Head_position_y -> Head bone Y position")
        print("  3. Apply denormalization if needed")
        print("  4. Update bone transforms in real-time")
        print("  5. Use /mh/mode for animation blending")
        print("  6. Use /mh/frame for timing synchronization")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    show_osc_message_examples()
