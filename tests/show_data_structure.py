#!/usr/bin/env python3
"""
Show the data structure and sample output of MetaHuman Streamer v2
"""

import numpy as np
import json
import os

def show_data_structure():
    """Display the structure of data being sent by the streamer"""
    print("MetaHuman Streamer v2 - Data Structure")
    print("=" * 60)
    
    try:
        # Load normalization parameters
        with open("data/processed_v2/normalization_params.json", 'r') as f:
            norm_params = json.load(f)
        
        feature_columns = norm_params['feature_columns']
        mean_values = norm_params['mean']
        std_values = norm_params['std']
        
        print(f"📊 DATA OVERVIEW")
        print(f"   Total features: {len(feature_columns)}")
        print(f"   Frames per sequence: {norm_params['target_frames']}")
        print(f"   Data type: Float32 (normalized)")
        print()
        
        # Show feature categories
        print("🏷️  FEATURE CATEGORIES")
        categories = {}
        for col in feature_columns:
            if 'position' in col:
                category = 'Position (x, y, z coordinates)'
            elif 'velocity' in col:
                category = 'Velocity (movement speed)'
            elif 'acceleration' in col:
                category = 'Acceleration (movement changes)'
            elif any(rot in col for rot in ['flexion', 'rotation', 'tilt']):
                category = 'Rotation (joint angles)'
            else:
                category = 'Other'
            
            categories[category] = categories.get(category, 0) + 1
        
        for cat, count in sorted(categories.items()):
            print(f"   {cat}: {count} features")
        print()
        
        # Show body parts
        print("🦴 BODY PARTS TRACKED")
        body_parts = {}
        for col in feature_columns:
            if 'Pelvis' in col:
                body_parts['Pelvis'] = body_parts.get('Pelvis', 0) + 1
            elif 'Chest' in col or 'Thorax' in col:
                body_parts['Chest/Thorax'] = body_parts.get('Chest/Thorax', 0) + 1
            elif 'Head' in col or 'Neck' in col:
                body_parts['Head/Neck'] = body_parts.get('Head/Neck', 0) + 1
            elif 'Shoulder' in col or 'Scapula' in col or 'UpperArm' in col:
                body_parts['Shoulder/Arm'] = body_parts.get('Shoulder/Arm', 0) + 1
            elif 'ForeArm' in col or 'Wrist' in col or 'Hand' in col:
                body_parts['Forearm/Hand'] = body_parts.get('Forearm/Hand', 0) + 1
            elif 'Digit' in col:
                body_parts['Fingers'] = body_parts.get('Fingers', 0) + 1
        
        for part, count in sorted(body_parts.items()):
            print(f"   {part}: {count} features")
        print()
        
        # Show sample features with their values
        print("📋 SAMPLE FEATURES (with typical values)")
        print("   Format: /mh/[feature_name] -> [normalized_value]")
        print()
        
        # Show first 15 features as examples
        for i in range(min(15, len(feature_columns))):
            col = feature_columns[i]
            mean_val = mean_values[i]
            std_val = std_values[i]
            
            # Show what a typical normalized value might look like
            # (normalized values are typically between -3 and +3)
            sample_normalized = np.random.normal(0, 1)  # Typical normalized value
            sample_denormalized = sample_normalized * std_val + mean_val
            
            print(f"   {i+1:2d}. /mh/{col}")
            print(f"       Normalized: {sample_normalized:.3f}")
            print(f"       Denormalized: {sample_denormalized:.3f}")
            print()
        
        if len(feature_columns) > 15:
            print(f"   ... and {len(feature_columns) - 15} more features")
            print()
        
        # Show special control messages
        print("🎮 CONTROL MESSAGES")
        print("   /mh/frame -> [frame_number] (0-59)")
        print("   /mh/mode -> [movement_mode] (BASELINE, TURNING_LEFT, TURNING_RIGHT)")
        print()
        
        # Show data flow
        print("🔄 DATA FLOW")
        print("   1. Load baseline/turn sequences (60 frames each)")
        print("   2. Stream frames at configured FPS (default: 30 FPS)")
        print("   3. Each frame sends 864 feature values + 2 control values")
        print("   4. Total: ~866 OSC messages per frame")
        print("   5. At 30 FPS: ~25,980 messages per second")
        print()
        
        # Show example OSC message format
        print("📡 OSC MESSAGE FORMAT")
        print("   Address: /mh/[feature_name]")
        print("   Value: float (32-bit)")
        print("   Example: /mh/Pelvis_position_x -> 0.123")
        print("   Example: /mh/LeftShoulder_flexion -> -0.456")
        print("   Example: /mh/frame -> 15")
        print("   Example: /mh/mode -> BASELINE")
        print()
        
        # Show what Unreal Engine would receive
        print("🎯 WHAT UNREAL ENGINE RECEIVES")
        print("   • Real-time bone positions (x, y, z coordinates)")
        print("   • Joint rotations (flexion, rotation, tilt angles)")
        print("   • Movement velocities and accelerations")
        print("   • Frame timing information")
        print("   • Current movement mode")
        print("   • All data normalized and ready for animation")
        print()
        
        print("💡 USAGE IN UNREAL ENGINE")
        print("   • Map OSC addresses to bone transforms")
        print("   • Apply denormalization if needed")
        print("   • Use frame info for timing")
        print("   • Use mode info for animation blending")
        
    except Exception as e:
        print(f"Error loading data structure: {e}")

def show_sample_sequence():
    """Show a sample of what one frame looks like"""
    print("\n" + "=" * 60)
    print("SAMPLE FRAME DATA")
    print("=" * 60)
    
    try:
        # Load a sample baseline sequence
        baseline_data = np.load("data/processed_v2/baseline_data.npy")
        sample_frame = baseline_data[0, 0, :]  # First frame of first sample
        
        print(f"Sample frame shape: {sample_frame.shape}")
        print(f"Data type: {sample_frame.dtype}")
        print(f"Value range: [{sample_frame.min():.3f}, {sample_frame.max():.3f}]")
        print()
        
        print("First 20 values in this frame:")
        for i in range(min(20, len(sample_frame))):
            print(f"   Feature {i+1:3d}: {sample_frame[i]:8.3f}")
        
        if len(sample_frame) > 20:
            print(f"   ... and {len(sample_frame) - 20} more values")
        
    except Exception as e:
        print(f"Error loading sample data: {e}")

if __name__ == "__main__":
    show_data_structure()
    show_sample_sequence()
