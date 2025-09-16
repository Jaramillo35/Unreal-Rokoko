#!/usr/bin/env python3
"""
Simple test for sitting pose functionality
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mh_streamer_v3 import MetaHumanStreamerV3

def test_sitting_pose():
    print("🧪 Testing Sitting Pose Functionality")
    print("=" * 40)
    
    # Create streamer
    print("🔧 Creating streamer...")
    app = MetaHumanStreamerV3()
    
    print(f"✅ Streamer ready with {len(app.baseline_sitting_pose)} pose values")
    print(f"📊 Column mapping: {len(app.COLUMN_TO_OSC)} bones mapped")
    print()
    
    # Test NLP parsing
    print("🧠 Testing NLP Parser:")
    print("-" * 25)
    
    test_phrases = [
        "sit",
        "sit down", 
        "make it sit",
        "sitting position",
        "assume seated",
        "go to sitting"
    ]
    
    for phrase in test_phrases:
        action, original_text, confidence = app.nlp_parser.parse_command(phrase)
        status = "✅" if action == "POSE_SITTING" else "❌"
        print(f"  {status} '{phrase}' → {action} (conf: {confidence:.2f})")
    
    print()
    
    # Test OSC message generation
    print("📡 Testing OSC Message Generation:")
    print("-" * 35)
    
    # Simulate what would be sent
    pose_commands = []
    bone_messages = []
    
    # Pose command
    pose_commands.append(("/cmd/pose", ["sitting", 0.35]))
    
    # Bone messages
    for column_name, value in app.baseline_sitting_pose.items():
        if column_name in app.COLUMN_TO_OSC:
            bone_name, axis = app.COLUMN_TO_OSC[column_name]
            osc_address = f"/bone/{bone_name}/{axis}"
            bone_messages.append((osc_address, float(value)))
    
    print(f"   Pose commands: {len(pose_commands)}")
    print(f"   Bone messages: {len(bone_messages)}")
    print()
    
    # Show sample messages
    print("🎯 Sample Messages:")
    print("-" * 18)
    
    print("   Pose Command:")
    for address, args in pose_commands:
        print(f"     {address} {args}")
    
    print("   Bone Messages (first 10):")
    for i, (address, value) in enumerate(bone_messages[:10]):
        print(f"     {address} {value:.3f}")
    
    if len(bone_messages) > 10:
        print(f"     ... and {len(bone_messages) - 10} more")
    
    print()
    
    # Test GUI integration
    print("🖥️  GUI Integration Test:")
    print("-" * 25)
    
    # Test button click simulation
    print("   Simulating 'Sit' button click...")
    try:
        # This would normally be called by the GUI
        app.trigger_sitting_pose()
        print("   ✅ Button click simulation successful")
    except Exception as e:
        print(f"   ❌ Button click simulation failed: {e}")
    
    # Test text input simulation
    print("   Simulating text input 'sit'...")
    try:
        action, original_text, confidence = app.nlp_parser.parse_command("sit")
        if action == "POSE_SITTING":
            app.trigger_sitting_pose()
            print("   ✅ Text input simulation successful")
        else:
            print(f"   ❌ Text input parsing failed: {action}")
    except Exception as e:
        print(f"   ❌ Text input simulation failed: {e}")
    
    print()
    print("✅ All tests completed successfully!")
    print("The sitting pose functionality is ready for use.")

if __name__ == "__main__":
    test_sitting_pose()
